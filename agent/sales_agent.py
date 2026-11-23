#!/usr/bin/env python3
"""Sales Agent demo flow for AgentTrust (fictional data only).

The sales agent may READ lead/customer/evidence rows and WRITE a pending
action_requests row plus its own provenance trace. It may never send: only
policy-gate may advance a request to sent_simulated, and even that is simulated.

Usage:
  python3 sales_agent.py --db agenttrust.db --scenario AR-A [--gate scripts/policy_gate.py]
"""
import argparse
import datetime as dt
import json
import sqlite3
import subprocess
import sys

AGENT_ID = "sales-agent"


def read_row(con, sql, args=()):
    cur = con.execute(sql, args)
    row = cur.fetchone()
    return None if row is None else dict(zip([c[0] for c in cur.description], row))


def read_rows(con, sql, args=()):
    cur = con.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def draft_reply(lead, customer, evidence_rows, picked):
    """Compose the draft and honestly report which customer rows it relies on and
    which technical claims it makes. Composition is fixed demo copy; the honesty of
    referenced_customer_ids and claims is what the gate then verifies."""
    if customer["classification"] != "client-confidential":
        raise RuntimeError("unexpected classification on customer record")
    verified = [e["claim"] for e in evidence_rows if e["verified"]]
    return {
        "action_type": picked["action_type"],
        "draft_text": picked["draft_text"],
        "amount_sgd": picked["amount_sgd"],
        "referenced_customer_ids": picked["referenced_customer_ids"],
        "claims": picked["claims"],
        "_verified_claims_available": verified,
    }


def main():
    ap = argparse.ArgumentParser(description="AgentTrust sales-agent scenario runner (demo).")
    ap.add_argument("--db", required=True)
    ap.add_argument("--scenario", required=True, help="request_id to draft and submit")
    ap.add_argument("--gate", required=True, help="path to policy-gate scripts/policy_gate.py")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    fixtures = json.loads((__import__("pathlib").Path(__file__).resolve().parent
                           / "scenarios.json").read_text(encoding="utf-8"))
    picked = next((s for s in fixtures["scenarios"] if s["request_id"] == args.scenario), None)
    if picked is None:
        sys.exit(f"sales-agent: unknown scenario {args.scenario}")
    if read_row(con, "SELECT 1 AS ok FROM action_requests WHERE request_id = ?",
                (picked["request_id"],)):
        sys.exit(f"sales-agent: request {picked['request_id']} already exists - "
                 "demo data is not overwritten.")

    lead = read_row(con, "SELECT * FROM leads WHERE lead_id = ?", (picked["lead_id"],))
    customer = read_row(con, "SELECT * FROM customers WHERE customer_id = ?",
                        (lead["customer_id"],))
    evidence_rows = read_rows(con, "SELECT * FROM evidence ORDER BY evidence_id")
    if lead["customer_id"] != picked["customer_id"]:
        sys.exit("sales-agent: scenario customer does not match the lead owner")

    draft = draft_reply(lead, customer, evidence_rows, picked)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    with con:
        con.execute(
            "INSERT INTO action_requests (request_id, agent_id, lead_id, customer_id, "
            "action_type, draft_text, amount_sgd, referenced_customer_ids, claims, "
            "status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (picked["request_id"], AGENT_ID, lead["lead_id"], lead["customer_id"],
             draft["action_type"], draft["draft_text"], draft["amount_sgd"],
             json.dumps(draft["referenced_customer_ids"]), json.dumps(draft["claims"]),
             "pending", now))

    report = read_row(con, "SELECT request_id, agent_id, action_type, status "
                           "FROM action_requests WHERE request_id = ?",
                      (picked["request_id"],))
    print(json.dumps({"sales_agent": report,
                      "draft_claims": draft["claims"],
                      "draft_references": draft["referenced_customer_ids"],
                      "sent": "NO - sales agent cannot send; handing to policy-gate"},
                     indent=2))

    res = subprocess.run([sys.executable, args.gate, "--db", args.db,
                          "--request", picked["request_id"], "--now", now],
                         capture_output=True, text=True)
    print(res.stdout, end="")
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
