---
name: policy-gate
description: Deterministic pre-action policy gate for the AgentTrust agent-governance demo database (fictional data). Use when an agent draft in the agenttrust.db action_requests table must be checked before any (simulated) send, when a held (awaiting_owner_approval) request needs owner approval, or when audit_events rows / request statuses need to be written by the governance layer. Applies P-PRIV, P-FIN, P-EVID in fixed order using field comparisons and SQLite lookups only — never model judgment. Never sends anything; sending is only ever simulated via status labels.
---

# policy-gate

Deterministic enforcement layer for the AgentTrust demo. Input is one `pending`
`action_requests` row identified by `request_id`; policies, customers, and evidence
are read from the same SQLite DB.

## Commands

```bash
# Evaluate a pending request (writes 1 audit event, updates status):
python3 scripts/policy_gate.py --db <path>/agenttrust.db --request AR-A

# Record owner approval of a held request (writes a NEW audit event, simulated send):
python3 scripts/policy_gate.py --db <path>/agenttrust.db --request AR-C --approve --by owner
```

Prints a JSON report: `decision`, `policy_evaluated`, `explanation`,
`request_status`, `event_id`, `trace` (ordered rule/check/result), and any
further violations observed after the deciding one.

## Contract (do not alter — demo determinism depends on it)

- Checks are field comparisons and DB lookups ONLY. No LLM, no network, no model
  judgment on content beyond exact string matching.
- Fixed rule order; the FIRST violation decides:
  1. **P-PRIV** (`forbidden_reference`) → `block`: any id in
     `referenced_customer_ids` differs from the request's `customer_id`, OR
     `draft_text` contains another customer's name, company, email,
     pricing_notes, or contact_notes as an exact substring.
  2. **P-FIN** (`amount_threshold`) → `requires_approval`: `action_type =
     send_quotation` AND `amount_sgd >` threshold parsed from the policy's own
     `parameter` (`threshold_sgd=5000`).
  3. **P-EVID** (`evidence_required`) → `block`: some string in `claims` has no
     `evidence` row with that exact `claim` AND `verified = 1`.
  4. Otherwise → `allow`.
- Only policies with `active = 1` run; if a policy row's `check_type` no longer
  matches the code, the gate raises instead of guessing.
- Every run appends exactly ONE `audit_events` row with ALL fields filled:
  `event_id` = `AEV-<request_id>-NN` (sequence per request),
  `data_classification` = highest tier touched (`client-confidential` floor for
  any customer reference; `financial` for a quotation with an amount),
  `policy_evaluated` = deciding id(s) (on allow: `P-PRIV,P-FIN,P-EVID`),
  `evidence_ref` = verified evidence ids on allow else `none`,
  `model_used` = `none (deterministic rule engine)`, `token_usage` = 0.
- `audit_events` is append-only. The gate never edits or deletes prior rows and
  refuses to re-evaluate a request whose status is no longer `pending`.
- Status map: `allow → sent_simulated`, `requires_approval →
  awaiting_owner_approval`, `block → blocked`.
- **Sending is always SIMULATED.** An `allow` only relabels the request
  `sent_simulated`; no email is composed, transmitted, or connected to anything.
  Reports must keep saying so. On `block`/`requires_approval` nothing happens.
- Owner approval (`--approve`): valid only on `awaiting_owner_approval`; appends a
  new event with `decision = approved_by_owner` citing the holding policy, then
  sets status `sent_simulated` (still simulated).
- All data is fictional demo data; verdicts are simulated governance, not real
  interception. Label outputs accordingly.