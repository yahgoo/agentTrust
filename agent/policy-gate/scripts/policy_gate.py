#!/usr/bin/env python3
"""policy-gate - deterministic pre-action policy engine for the AgentTrust demo DB.

Takes exactly one action_requests row, applies the ACTIVE policies stored in the
`policies` table in fixed order (P-PRIV -> P-FIN -> P-EVID, first violation decides)
using deterministic field comparisons and database lookups only (never model
judgment). Always writes exactly ONE audit_events row (all fields) and updates the
request status once.

Status map:
  allow             -> sent_simulated   (sending is SIMULATED only; no email is sent)
  requires_approval -> awaiting_owner_approval  (nothing sent)
  block             -> blocked          (nothing sent)

Owner approval of a held request (--approve): appends a NEW audit event with
decision=approved_by_owner, then marks the request sent_simulated (still simulated).

All data is fictional demo data.

Usage:
  python3 policy_gate.py --db agenttrust.db --request AR-A [--now <iso>]
  python3 policy_gate.py --db agenttrust.db --request AR-C --approve [--by owner] [--now <iso>]
"""
import argparse
import datetime as dt
import json
import re
import sqlite3
import sys

RULE_ORDER = ("P-PRIV", "P-FIN", "P-EVID")
CONF_FIELDS = ("email", "pricing_notes", "contact_notes")

PRIVACY_EXPL = ("Draft includes confidential records of {who}. Data privacy policy "
                "forbids sharing one customer's data with another.")
FINANCIAL_EXPL = ("Quote of SGD {amount} exceeds the SGD 5,000 limit. Held for owner "
                  "approval; not sent.")
EVIDENCE_EXPL = "Claim '{claim}' has no supporting evidence record. Not sent."
ALLOW_EXPL = ("All three policies passed. Reply uses only the recipient's own data, no "
              "amount above the limit, and every technical claim has evidence.")

STATUS_FOR = {
    "allow": "sent_simulated",
    "requires_approval": "awaiting_owner_approval",
    "block": "blocked",
}


def sgd(amount):
    """Format an amount the way the draft copy does: 8000.0 -> '8,000'."""
    return f"{float(amount):,.0f}"


def read_row(con, sql, args=()):
    cur = con.execute(sql, args)
    row = cur.fetchone()
    return None if row is None else dict(zip([c[0] for c in cur.description], row))


def read_rows(con, sql, args=()):
    cur = con.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def jarr(raw):
    if raw in (None, ""):
        return []
    val = json.loads(raw)
    if not isinstance(val, list):
        raise ValueError("expected a JSON array")
    return val


def customer_label(con, cid):
    c = read_row(con, "SELECT name, customer_id FROM customers WHERE customer_id = ?", (cid,))
    return f"{c['name']} ({c['customer_id']})" if c else cid


def classification_of(con, request):
    """Highest sensitivity tier touched by this request: client-confidential is the
    floor (customer records are read), a monetary quotation is the higher tier."""
    ref_ids = set(jarr(request["referenced_customer_ids"])) | {request["customer_id"]}
    if not ref_ids:
        return "internal"
    if request["action_type"] == "send_quotation" and request["amount_sgd"] is not None:
        return "financial"
    return "client-confidential"


def check_privacy(con, request, policy):
    """P-PRIV: referenced id outside the recipient, or draft_text containing another
    customer's name, company, email, or confidential field value (exact substrings)."""
    recipient = request["customer_id"]
    for rid in jarr(request["referenced_customer_ids"]):
        if rid != recipient:
            return PRIVACY_EXPL.format(who=customer_label(con, rid))
    draft = request["draft_text"] or ""
    for cust in read_rows(con, "SELECT * FROM customers WHERE customer_id != ? "
                               "ORDER BY customer_id", (recipient,)):
        values = [cust["name"], cust["company"]] + [cust[f] for f in CONF_FIELDS]
        if any(v and v in draft for v in values):
            return PRIVACY_EXPL.format(who=f"{cust['name']} ({cust['customer_id']})")
    return None


def check_financial(con, request, policy):
    """P-FIN: threshold is read from the policy row's own `parameter` field."""
    m = re.search(r"threshold_sgd\s*=\s*([0-9.]+)", policy["parameter"])
    if not m or request["action_type"] != "send_quotation":
        return None
    if request["amount_sgd"] is None or float(request["amount_sgd"]) <= float(m.group(1)):
        return None
    return FINANCIAL_EXPL.format(amount=sgd(request["amount_sgd"]))


def check_evidence(con, request, policy):
    """P-EVID: every claim string must match an evidence row exactly, verified=1."""
    for claim in jarr(request["claims"]):
        hit = read_row(con, "SELECT 1 AS ok FROM evidence WHERE claim = ? AND verified = 1",
                       (claim,))
        if hit is None:
            return EVIDENCE_EXPL.format(claim=claim)
    return None


CHECKS = {
    "P-PRIV": ("forbidden_reference", check_privacy),
    "P-FIN": ("amount_threshold", check_financial),
    "P-EVID": ("evidence_required", check_evidence),
}


def next_event_id(con, request_id):
    seq = 1
    while read_row(con, "SELECT 1 AS ok FROM audit_events WHERE event_id = ?",
                   (f"AEV-{request_id}-{seq:02d}",)) is not None:
        seq += 1
    return f"AEV-{request_id}-{seq:02d}"


def append_audit(con, request, event_time, decision, policy_evaluated, explanation,
                 evidence_ref):
    """Append-only: never edits or deletes prior rows; always fills every field."""
    event_id = next_event_id(con, request["request_id"])
    con.execute(
        "INSERT INTO audit_events (event_id, request_id, agent_id, requested_action, "
        "data_classification, policy_evaluated, decision, explanation, evidence_ref, "
        "model_used, token_usage, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, request["request_id"], request["agent_id"], request["action_type"],
         classification_of(con, request), policy_evaluated, decision, explanation,
         evidence_ref, "none (deterministic rule engine)", 0, event_time))
    return event_id


def run_gate(con, request_id, now):
    request = read_row(con, "SELECT * FROM action_requests WHERE request_id = ?",
                       (request_id,))
    if request is None:
        sys.exit(f"policy-gate: no action_requests row with request_id={request_id}")
    if request["status"] != "pending":
        sys.exit(f"policy-gate: request {request_id} has status '{request['status']}', "
                 "not 'pending' - the gate runs once per request (audit history is "
                 "append-only and will not be rewritten).")

    active = read_rows(con, "SELECT * FROM policies WHERE active = 1")
    trace, violations = [], []
    for pid in RULE_ORDER:
        policy = next((p for p in active if p["policy_id"] == pid), None)
        if policy is None:
            trace.append({"rule": pid, "check": "policy lookup", "result": "skipped - not active"})
            continue
        expected_type, fn = CHECKS[pid]
        if policy["check_type"] != expected_type:
            raise RuntimeError(
                f"policy-gate: {pid} has check_type={policy['check_type']!r}, expected "
                f"{expected_type!r}. The policy row changed shape - refusing to guess.")
        explanation = fn(con, request, policy)
        if explanation is None:
            trace.append({"rule": pid, "check": policy["check_type"], "result": "pass"})
        else:
            trace.append({"rule": pid, "check": policy["check_type"], "result":
                          f"violation -> {policy['decision_on_violation']}"})
            violations.append({"policy_evaluated": pid,
                               "decision": policy["decision_on_violation"],
                               "explanation": explanation})

    if violations:
        first = violations[0]  # first violation decides and is the only one acted on
        decision, pol_id, explanation = (first["decision"], first["policy_evaluated"],
                                         first["explanation"])
        evidence_ref = "none"
    else:
        decision, pol_id, explanation = "allow", "P-PRIV,P-FIN,P-EVID", ALLOW_EXPL
        ids = [r["evidence_id"] for r in
               read_rows(con, "SELECT evidence_id FROM evidence WHERE verified = 1 "
                              "ORDER BY evidence_id")]
        evidence_ref = ",".join(ids) if ids else "none"

    status = STATUS_FOR[decision]
    with con:
        event_id = append_audit(con, request, now, decision, pol_id, explanation,
                                evidence_ref)
        con.execute("UPDATE action_requests SET status = ? WHERE request_id = ?",
                    (status, request_id))
    note = ("SIMULATED send marked on status only - no real email was sent"
            if decision == "allow" else "nothing was sent")
    return {"request_id": request_id, "event_id": event_id, "decision": decision,
            "policy_evaluated": pol_id, "explanation": explanation,
            "request_status": status, "note": note,
            "further_violations_observed": [v["policy_evaluated"] for v in violations[1:]],
            "trace": trace}


def approve_held(con, request_id, now, by):
    request = read_row(con, "SELECT * FROM action_requests WHERE request_id = ?",
                       (request_id,))
    if request is None:
        sys.exit(f"policy-gate: no action_requests row with request_id={request_id}")
    if request["status"] != "awaiting_owner_approval":
        sys.exit(f"policy-gate: request {request_id} has status '{request['status']}', "
                 "not 'awaiting_owner_approval' - nothing to approve.")
    held = read_row(con, "SELECT policy_evaluated FROM audit_events WHERE request_id = ? "
                         "AND decision = 'requires_approval' ORDER BY created_at DESC, "
                         "event_id DESC LIMIT 1", (request_id,))
    pol_id = held["policy_evaluated"] if held else "none"
    explanation = (f"Owner '{by}' approved the held request. Marked sent_simulated - "
                   "sending remains SIMULATED, no real email was sent.")
    with con:
        event_id = append_audit(con, request, now, "approved_by_owner", pol_id,
                                explanation, "none")
        con.execute("UPDATE action_requests SET status = 'sent_simulated' WHERE request_id = ?",
                    (request_id,))
    return {"request_id": request_id, "event_id": event_id, "decision": "approved_by_owner",
            "policy_evaluated": pol_id, "explanation": explanation,
            "request_status": "sent_simulated",
            "note": "SIMULATED send marked on status only - no real email was sent"}


def main():
    ap = argparse.ArgumentParser(description="Deterministic AgentTrust policy gate (demo).")
    ap.add_argument("--db", required=True, help="path to agenttrust.db")
    ap.add_argument("--request", required=True, help="action_requests.request_id")
    ap.add_argument("--approve", action="store_true", help="record owner approval of a held request")
    ap.add_argument("--by", default="owner", help="approver label (with --approve)")
    ap.add_argument("--now", default=None, help="ISO timestamp to record (default: current time)")
    args = ap.parse_args()

    now = args.now or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    con = sqlite3.connect(args.db)
    if args.approve:
        report = approve_held(con, args.request, now, args.by)
    else:
        report = run_gate(con, args.request, now)
    print(json.dumps(report, indent=2, sort_keys=False))


if __name__ == "__main__":
    main()
