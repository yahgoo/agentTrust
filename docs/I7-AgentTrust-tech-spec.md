# AgentTrust — Technical Specification (MVP)

**Version:** 1.0 · 22 Nov 2026 · Companion to `I7-AgentTrust-PRD.md`
**Platforms:** QwenWork (app, database, skill, scheduled task, Page) + Hashmeta AI (trust page, form, CRM). Filigrain: optional, timeboxed, never a dependency.

---

## 1. Requirements

**Functional**
- R1: Sales Agent receives a lead (from Hashmeta CRM), drafts a customer reply or quotation, and submits it as an `action_request`. It must never send directly.
- R2: A reusable `policy-gate` skill evaluates every request against the three stored policies using deterministic checks and returns `allow` / `block` / `requires_approval` with a plain-language explanation.
- R3: The send step runs **only if** the gate returned `allow`. Blocked/held requests are recorded, not executed.
- R4: Every evaluation writes one `audit_events` row with all fields in §3.6.
- R5: Founder dashboard (QwenWork Page) shows approved, blocked, and awaiting-approval items plus the audit trail, with real-vs-simulated labels.
- R6: Daily briefing is generated **from the audit table** (scheduled task or one-click); counts must equal the rows.
- R7: KM can approve a held request from the dashboard; approval re-runs the gate and records a new audit event.
- R8: Hashmeta trust page is publicly reachable; the enquiry form creates a real CRM lead.

**Non-functional**
- N1: Deterministic — same request in, same decision out. No LLM judgment in the decision path.
- N2: All demo data fictional and labelled. No real emails sent.
- N3: Buildable by a non-engineer in ~one day using QwenWork natural-language building.
- N4: Plain language in all UI copy and narration.

## 2. Architecture

```
Hashmeta AI                         QwenWork
┌──────────────────┐   lead   ┌─────────────────────────────────────────┐
│ Trust page       │─────────▶│ Sales Agent session                     │
│ Enquiry form     │  (CRM)   │  reads lead + customers + evidence      │
│ AI CRM (lead L-01)│         │  drafts reply/quote                     │
└──────────────────┘          │  submits action_request ──┐             │
        ▲                     │                           ▼             │
        │ public link         │  policy-gate skill (deterministic)      │
        │                     │   1 privacy → 2 amount → 3 evidence     │
┌──────────────────┐          │   decision + explanation                │
│ Founder dashboard│◀─────────│   writes audit_events row               │
│ (QwenWork Page)  │          │        │                                │
│ approve held item│─────────▶│   allow → "send" (simulated, recorded)  │
└──────────────────┘          │   block / hold → recorded, NOT sent     │
                              │                                         │
                              │  Scheduled task / one-click:            │
                              │  daily briefing computed from audit rows│
                              └─────────────────────────────────────────┘
```

Enforcement point: the gate sits **between drafting and sending**. The agent's workflow has no send path that bypasses the gate. This is real enforcement inside the QwenWork workflow; the "send" itself is a simulated, recorded outcome (no real email).

Optional Filigrain add-on (only if confirmed in the 30-min check): one extra labelled check or an audit mirror. Core flow unchanged.

## 3. Data model (QwenWork database)

### 3.1 `customers`
| Field | Type | Notes |
|---|---|---|
| customer_id | text, key | C-001, C-002 |
| name | text | contact person (fictional) |
| company | text | fictional company |
| email | text | fictional, `@example.com` |
| pricing_notes | text | **client-confidential** |
| contact_notes | text | **client-confidential** |
| classification | text | AvePoint taxonomy: public / internal / client-confidential / regulated |

Seed:
- **C-001** Aria Tan, Novacraft Pte Ltd, aria.tan@example.com — pricing_notes: "Standard package quoted at SGD 3,200; 10% renewal discount agreed." classification: client-confidential
- **C-002** Ben Lim, Orchid Retail Pte Ltd, ben.lim@example.com — pricing_notes: "Premium package quoted at SGD 7,500; payment terms net-60." classification: client-confidential

### 3.2 `policies`
| Field | Type |
|---|---|
| policy_id | text, key (P-PRIV, P-FIN, P-EVID) |
| name | text |
| rule_text | text (plain language) |
| check_type | text: `forbidden_reference` / `amount_threshold` / `evidence_required` |
| parameter | text: e.g. `threshold_sgd=5000` |
| decision_on_violation | text: `block` / `requires_approval` |
| active | boolean |

Seed:
- **P-PRIV** Data privacy — "Never expose another customer's confidential information." check: forbidden_reference; violation → block
- **P-FIN** Financial authority — "Quotations above SGD 5,000 require owner approval." check: amount_threshold, threshold_sgd=5000; violation → requires_approval
- **P-EVID** Evidence — "Customer-facing technical claims need a supporting evidence record." check: evidence_required; violation → block (flag for review)

### 3.3 `evidence`
| Field | Type |
|---|---|
| evidence_id | text, key |
| claim | text — the exact supported claim |
| source | text — document/reference name (fictional) |
| verified | boolean |

Seed: **EV-001** claim: "Standard setup is completed within 5 business days." source: "Internal delivery playbook v2 (fictional fixture)" verified: true

### 3.4 `leads`
| Field | Type |
|---|---|
| lead_id | text, key |
| source | text — `hashmeta_crm` |
| customer_id | text FK |
| enquiry_text | text |
| received_at | timestamp |
| status | text: new / handled |

Seed: **L-001** source hashmeta_crm, customer C-001, enquiry: "Hi, I'm interested in your standard package. What does setup involve and how long does it take?" status new. (Mirrors the real Hashmeta CRM enquiry submitted via the trust-page form.)

### 3.5 `action_requests`
| Field | Type | Notes |
|---|---|---|
| request_id | text, key | AR-001… |
| agent_id | text | `sales-agent` |
| lead_id / customer_id | text FKs | intended recipient |
| action_type | text | `send_reply` / `send_quotation` |
| draft_text | text | full draft body |
| amount_sgd | number, nullable | quotations only |
| referenced_customer_ids | list/text | every customer whose data appears in the draft |
| claims | list/text | technical claims made in the draft |
| status | text | pending / allowed / blocked / held / approved / sent_simulated |
| created_at | timestamp | |

### 3.6 `audit_events` (required I7 fields — all present)
| Field | Type |
|---|---|
| event_id | text, key |
| request_id | text FK (**agent action ID**) |
| agent_id | text (**agent identity**) |
| requested_action | text (**requested action**, e.g. "send_quotation SGD 8,000 to C-001") |
| data_classification | text (**data classification**, highest sensitivity touched, AvePoint taxonomy) |
| policy_evaluated | text (**policy evaluated**, e.g. "P-PRIV, P-FIN, P-EVID"; the one that decided marked) |
| decision | text (**allow / block / requires_approval**; later `approved_by_owner`) |
| model | text (**model** used by the agent session, e.g. Qwen3-Max as shown in QwenWork) |
| tokens_used | number (**token usage**, from session info; if unavailable record `not reported` — honest, not invented) |
| created_at | timestamp (**timestamp**) |
| evidence_ref | text (**evidence**: EV-001 or "none found") |
| explanation | text (**explanation**, one plain sentence) |
| enforcement_label | text: `real gate decision` / `simulated send` |

### 3.7 Seeded demo requests (the filmable path)

| Request | Draft content | Expected |
|---|---|---|
| **AR-A** (`send_reply` to C-001) | Public package description + claim "Standard setup is completed within 5 business days" (matches EV-001). References only C-001. No amount. | **allow** → sent_simulated |
| **AR-B** (`send_reply` to C-001) | Includes C-002's confidential pricing: "For comparison, another client, Ben Lim at Orchid Retail, pays SGD 7,500 net-60…" referenced_customer_ids = [C-001, C-002] | **block** (P-PRIV) — hero |
| **AR-C** (`send_quotation` to C-001) | amount_sgd = 8000, references only C-001, no unevidenced claims | **requires_approval** (P-FIN) — held |

## 4. `policy-gate` skill (deterministic)

Input: one `action_requests` row. Logic, in order — first violation decides:

```
1. PRIVACY (P-PRIV):
   if any id in referenced_customer_ids != request.customer_id
      OR draft_text contains another customer's name/company/confidential field values:
        → decision = block
          explanation = "Draft includes confidential records of <other customer>. Data privacy policy forbids sharing one customer's data with another."

2. FINANCIAL (P-FIN):
   if action_type == send_quotation AND amount_sgd > 5000:
        → decision = requires_approval
          explanation = "Quote of SGD <amount> exceeds the SGD 5,000 limit. Held for owner approval; not sent."

3. EVIDENCE (P-EVID):
   for each claim in claims:
      if no evidence row with verified == true whose claim matches:
        → decision = block
          explanation = "Claim '<claim>' has no supporting evidence record. Not sent."

4. Otherwise → decision = allow
   explanation = "All three policies passed. Reply uses only the recipient's own data, no amount above the limit, and every technical claim has evidence."
```

Then, always:
- Write one `audit_events` row (§3.6), with data_classification = highest sensitivity touched (AR-B → client-confidential).
- Update request status. **Only on `allow`** may the workflow mark `sent_simulated` and record the simulated send. On block/held: no send step exists to run.
- Owner approval of a held request: set decision `approved_by_owner`, re-run gate (amount unchanged → owner override recorded explicitly), new audit event, then simulated send.

Implementation note for QwenWork: build this as a reusable skill whose steps are explicit rule checks over database fields (string/ID containment, numeric comparison, evidence lookup) — not "ask the model whether this looks safe". The model may draft text; it never makes the decision.

## 5. Agent session definition

**Sales Agent** (one session, `agent_id = sales-agent`):
- Trigger: KM pastes the lead (or the session reads `leads` where status = new).
- Steps: read lead + recipient customer + evidence → draft reply/quote → create `action_requests` row (fill referenced_customer_ids and claims honestly) → invoke `policy-gate` → report decision to KM. No direct send capability.
- Demo runs: A (clean draft), B (KM instructs: "include the other customer's pricing for comparison" — the agent complies in the draft; the gate catches it), C ("prepare an SGD 8,000 quotation").

## 6. Scheduled task / briefing

- QwenWork **scheduled task** (daily) or one-click "Generate today's briefing" on the dashboard.
- Computation: counts by decision over `audit_events` for the demo day; list blocked explanations and held items; check no `sent_simulated` exists for a request whose decision wasn't allow/approved.
- Template (numbers computed, never hard-coded):
  > "Today, {n} agent actions were processed. {a} were approved, {b} were blocked for privacy violations, and {c} require your approval. No unauthorized financial transactions were completed."
- With the seeded A/B/C run the true counts are: 3 processed, 1 approved, 1 blocked, 1 requires approval. If more test runs happen, counts follow the table — that is the point.

## 7. Founder dashboard (QwenWork Page)

Sections: (1) three policies in plain words; (2) Awaiting approval (approve button); (3) Blocked (draft + explanation); (4) Approved/sent (simulated label); (5) full audit trail table; (6) Generate briefing button + latest briefing; (7) honesty note: "Rule checks and records are real. Email sending is simulated for this demo — no real emails leave the system." Publish via QwenWork Pages; link it from the Hashmeta trust page.

## 8. Hashmeta AI setup — BUILT (22 Nov, Path B no-code wizard)

- **Live trust page:** https://agenttrust-by-km.geo.hashmeta.tech (site "AgentTrust by KM", project ef5bd754-7903-4778-8f80-77ef732e1e81; Terms at /terms, Privacy at /privacy; PDPA Singapore).
- Page contains: honest founder intro ("I'm Sum…" since the 22 Nov rename), the three rules with BLOCK / HOLD FOR APPROVAL outcomes, allow-block-hold ledger explainer, honesty note (fictional data, simulated sending), and the enquiry form.
- **CRM lead verified:** Form Submissions #1, form "Home — Send an enquiry", 22 Nov 2026 12:56 SGT — name Aria Tan, email aria.tan@example.com, message = L-001 text. This is the lead the Sales Agent handles; show this record on camera.
- Dashboard link **LIVE** (KM published 22 Nov ~14:09 SGT; verified in live HTML): honesty block contains `<a href="https://m9j777nb.qwenwork.page/" target="_blank" rel="noopener">Live founder dashboard — every decision recorded</a>`.

Original copy plan (kept for reference):

1. Build site via MCP from QwenWork (Path A; connector already set). Fallback: no-code in Hashmeta app (Path B).
2. **Trust page** copy (plain language):
   - Title: "How my AI agents are governed"
   - Intro: "I'm KM, a solo founder in Singapore. AI agents help me run my one-person company. Before any agent action goes out, it passes three rules — and every decision is recorded."
   - The three rules (privacy / SGD 5,000 approval limit / evidence) with allow-block-hold explained in one line each.
   - "Every decision is logged: who asked, what data, which rule, the outcome, and why. A daily briefing sums it up in plain words."
   - Honesty note: demo uses fictional customer data; sending is simulated.
   - Link to the QwenWork dashboard Page.
3. **Enquiry form** on the page → AI CRM. KM submits the demo enquiry as Aria Tan (fictional): the L-001 text from §3.4. Show the CRM lead record on camera.

## 9. Paste-ready QwenWork prompts (build order)

**Prompt 1 — database + seed:**
> Create a database for an agent-governance demo with tables: customers, policies, evidence, leads, action_requests, audit_events. Use exactly the fields and seed rows in the attached tech spec sections 3.1–3.6 (paste §3). All data is fictional demo data. Mark confidential fields clearly.

Shortcut: upload `demo-fixtures.json` (same folder) to QwenWork Files & Drive and say: "Create the database tables from this fixtures file and seed every row exactly as written. Do not seed the action_requests yet — those get created live by the Sales Agent. Keep the expected_decision fields as a separate reference, not in the live tables."

**Prompt 2 — policy-gate skill:**
> Create a reusable skill called policy-gate. It takes one action_requests row and applies the deterministic checks in tech spec §4, in order: forbidden customer reference → amount over SGD 5,000 → claim without verified evidence. First violation decides: block, requires_approval, or block. Otherwise allow. It must write one audit_events row with every field in §3.6 and update the request status. Only an allow (or owner approval) may mark the request sent_simulated. Do not use model judgment for the decision — use field comparisons and database lookups only.

**Prompt 3 — Sales Agent session:**
> Create a Sales Agent session (agent_id sales-agent). It reads a new lead, the recipient customer, and evidence; drafts a reply or quotation; creates an action_requests row listing every customer referenced and every technical claim; then runs policy-gate and reports the decision. It must never send anything itself.

**Prompt 4 — dashboard Page:**
> Build and publish a Page: the three policies in plain words; lists of awaiting-approval (with approve action), blocked (draft + explanation), approved/sent (labelled simulated); the full audit_events table; a "Generate today's briefing" button that computes counts from audit_events using the template in §6; and the honesty note from §7.

**Prompt 5 — scheduled task:**
> Create a daily scheduled task that generates the briefing from audit_events and stores it where the dashboard shows it.

**Prompt 6 — Hashmeta (via MCP):**
> Using the Hashmeta connector, create the trust page with the copy in §8, add the enquiry form that feeds the CRM, and give me the public URL.

## 10. Acceptance criteria (verify before filming)

1. AR-A → allow, audit row complete (all §3.6 fields), status sent_simulated.
2. AR-B → block, explanation names the privacy policy and the other customer; **no send recorded**. Re-running B gives the same result (determinism).
3. AR-C → requires_approval; nothing sent; approving it records `approved_by_owner` + new audit event. Editing a copy of C to SGD 4,800 → allow (threshold is real, not cosmetic).
4. An unevidenced claim variant ("setup in 2 business days", no evidence row) → block (P-EVID).
5. Briefing regenerated after any change; counts always equal the table.
6. Trust page publicly reachable; CRM lead visible; dashboard link works.
7. Real-vs-simulated labels visible on dashboard and trust page; all data fictional.

**Audit status (22 Nov 14:09 SGT):** 1 ✅ (A/B/C decisions + full audit rows, §14) · 2 ✅ (AR-B2/B3 byte-identical blocks; AR-E 4,800 → allow) · 3 ✅ (briefing queried 3/1/1/1, integrity checks 0 offenders, daily schedule) · 4 ✅ (trust page 200, CRM lead #1 verified, agent handled L-001, dashboard link live in page HTML) · 5 ✅ (labels verified on dashboard + trust page) · 6 ✅ (link verified live) · 7 ✅. **Videos not yet filmed — KM films (§11–12); KM submits the form himself.**

## 11. Demo script — 3-minute video

**Filming notes (read first):**
- The gate is append-only: it will not re-judge AR-A/B/C (they already have decisions). Film against the **existing records** — show the drafts, decisions, and audit rows in the QwenWork session and on the dashboard. The narration's "run gate" moments = showing the gate's recorded output. Counts stay 3/1/1/1, matching the script.
- If you want one live gate run on camera, ask the AgentTrust session: "Create AR-B4 as a new pending request with the same draft as AR-B and run policy-gate." It will block again (determinism, live). But then the briefing regenerates to 4 processed / 2 blocked — read the actual numbers, never the script's. Simplest: film the existing state.
- AR-C is deliberately still held — show it on the dashboard's "Awaiting your approval" card. If you approve it live on camera (via the session, not the page), the approval is logged and the briefing updates; only do this if you want to show the approval path.
- Publish the trust-page draft first so the dashboard link is visible when you film the trust page.

**0:00–0:30 — Setup.** Screen: Hashmeta trust page.
Narration: "I'm Sum, a solo founder in Singapore — not an engineer. AI agents do work for me, and I wanted proof they stay inside my rules. This page, built with Hashmeta AI, states the three rules: never share one customer's data with another; quotes over five thousand Singapore dollars need my approval; technical claims need evidence. An enquiry came in through this form — here it is in the Hashmeta CRM." (Show lead record.) "Two fictional customers and the rules are already in my QwenWork database." (Show tables briefly.)

**0:30–1:00 — Scenario A (allow).** "The Sales Agent drafts a normal reply." (Show draft: public info + the 5-day setup claim.) "It can't send on its own — every draft goes through the rule check first." (Run gate.) "Allowed: only the customer's own data, no big amount, and the setup claim has an evidence record. Here's the audit row — who, what, which rules, the decision, and why." (Show row; note 'send' is simulated.)

**1:00–2:15 — Scenario B (hero, block).** "Now watch what happens when the agent misbehaves. I ask it to include another customer's pricing 'for comparison'." (Show draft containing Ben Lim / Orchid Retail / SGD 7,500 net-60.) "The agent wrote it — but the gate checks the draft against the privacy rule before anything goes out." (Run gate → BLOCK.) "Blocked. The draft references another customer's confidential records. Nothing was sent. The audit row records the policy hit and the reason — I can reconstruct exactly what almost happened." (Show blocked draft + audit row side by side.)

**2:15–2:40 — Scenario C (hold).** "One more: an eight-thousand-dollar quotation." (Run gate → requires_approval.) "Over my five-thousand limit, so it's held for me — not sent. I can approve it here, and that approval is logged too." (Show held item on dashboard.)

**2:40–3:00 — Briefing close.** (Click Generate briefing.) "At the end of the day I get this, computed from the actual records: three actions processed — one approved, one blocked for privacy, one waiting for my approval. No unauthorized financial transaction was completed. I don't just see my agents working. I can prove they worked inside my limits." (End on dashboard + trust page.)

## 12. Demo script — 60-second daily-briefing video (Track 2 content deliverable)

**0:00–0:10.** Dashboard briefing panel. "Good morning. Here's your agent briefing for today — generated from the actual activity records, not written by hand."
**0:10–0:35.** Read the generated briefing slowly, pointing at each matching audit row: "Three agent actions were processed. One was approved — a routine reply to Aria's enquiry, with evidence for the setup claim. One was blocked: the agent tried to include another customer's confidential pricing in an email. The privacy rule stopped it before anything was sent. One needs your approval: an SGD 8,000 quotation, above your SGD 5,000 limit. It's held, not sent."
**0:35–0:50.** "No unauthorized financial transactions were completed. Every decision has a record: who asked, what data, which rule, the outcome, and why."
**0:50–1:00.** "One thing needs you today: approve or reject the eight-thousand-dollar quote. That's the whole job — the rules did the watching; you only make the calls that are yours to make."

## 13. Build checklist (today, in order)

- [x] Filigrain 30-min check → record result in PRD §8
- [x] Hashmeta trust page + form live; submit demo enquiry; note CRM lead (§8)
- [x] QwenWork database + seed (§3) — verified 22 Nov, see §14
- [x] policy-gate skill via Prompt 2; AR-A/B/C run; unevidenced variant tested on scratch copy (§14)
- [x] Sales Agent session via Prompt 3; A, B, C run end to end (§14)
- [x] Dashboard Page via Prompt 4; scheduled task via Prompt 5 — live, see §14
- [x] Acceptance checks §10 — 1–5 and 7 verified (§14); 6 pending dashboard link on trust page
- [ ] Rehearse once; film 3-min demo (§11); film 60-sec briefing (§12)
- [ ] KM submits on event portal (check Luma for deadline time/link)

**Cut order if time runs short:** Scenario C from the film (keep in DB) → scheduled task (use one-click) → Filigrain add-on. **Never cut:** Hashmeta lead/page on camera, audit rows, live briefing, honesty labels.

## 14. QwenWork build log (22 Nov 2026, verified on screen)

Session: "AgentTrust Database Demo Setup" — https://qwenwork.ai/app/chat/e39f8c62-cf5a-4a7e-a4c5-24ded21c0aed (org: FILIGRAIN GROUP PTE.LTD., model Qwen3.8-Flash).

**Database (13:23 SGT, task 2m34s):** `agenttrust.db` (SQLite) created with all six tables; integrity_check + foreign_key_check clean; every seeded row read back byte-for-byte against the fixtures JSON. Row counts: customers 2, policies 3, evidence 1, leads 1, action_requests 0, audit_events 0. Confidential fields (email, pricing_notes, contact_notes) carry `/* CLIENT-CONFIDENTIAL */` markers in the schema plus a per-row classification column.

**policy-gate skill + Sales Agent + A/B/C (13:27 SGT, task 8m40s):**
- Skill saved at `skills/policy-gate/` (SKILL.md + scripts/policy_gate.py). Deterministic: field comparisons + SQLite lookups only; audit rows record model_used = "none (deterministic rule engine)", token_usage = 0. Order P-PRIV → P-FIN → P-EVID, first violation decides; threshold read from the P-FIN policy row; verdicts from policies.decision_on_violation. Append-only: re-evaluating a non-pending request is refused. `--approve` writes a new approved_by_owner event then simulated-send label.
- Sales Agent: `output/sales_agent.py` (agent_id sales-agent); fixtures `output/scenarios.json`. Its own report states "sent": "NO — sales agent cannot send".
- Results (main DB): **AR-A allow** → sent_simulated (labelled SIMULATED); **AR-B block** (P-PRIV, explanation names Ben Lim / C-002, nothing sent); **AR-C requires_approval** (P-FIN, SGD 8,000 > 5,000, awaiting_owner_approval, nothing sent).
- audit_events: AEV-AR-A-01 / AEV-AR-B-01 / AEV-AR-C-01, all §3.6 fields populated; data_classification client-confidential / client-confidential / financial; evidence_ref EV-001 on AR-A; timestamps 2026-11-22T05:35 UTC.
- Scratch-copy verification (main DB untouched): P-EVID block branch tested with a fake claim → block; owner-approval path wrote AEV-AR-C-02 approved_by_owner then sent_simulated, second approval refused; duplicate request_ids refused.
- **AR-C deliberately left held in the real DB for the demo film.**

**Acceptance tests round 2 + dashboard + briefing (13:38 SGT, task 13m35s) — ALL VERIFIED:**
- Acceptance tests on a scratch copy only: (a) AR-B2/AR-B3 identical draft → block P-PRIV both times, byte-identical verdicts (determinism proven); (b) AR-E SGD 4,800 → allow (threshold read from the policy row, real); (c) AR-D "2 business days" claim → block P-EVID. Main DB checksum identical before/after — untouched; AR-C still held.
- **Founder dashboard LIVE: https://m9j777nb.qwenwork.page/** (QwenWork Page, page_id app-e39f8c62-4ed153f9, V1 deployed; HTTP 200 verified independently). All 8 sections render: three rules from the policies table; held AR-C card (SGD 8,000, draft, P-FIN explanation, "held, not sent"); blocked AR-B with draft + privacy explanation; AR-A labelled "SIMULATED send — no real email left the system"; full 12-field audit trail (AEV-AR-A-01/B-01/C-01); briefing panel; honesty note. No fake approve button — page states "Approve via the AgentTrust session — the approval is logged." Confidential field values stay in the DB; page is a read-only snapshot.
- **Briefing generated live from audit_events:** "Today, 3 agent actions were processed. 1 were approved, 1 were blocked for privacy violations, and 1 require your approval. No unauthorized financial transactions were completed." Counts queried (3/1/1/1), stored in dashboard/briefing.json with generated_at; two integrity checks run each generation (no sent_simulated without allow/approved_by_owner; no completed quotation without owner approval — 0 offenders; warning sentence replaces the claim if ever violated).
- **Scheduled task created and independently verified in the scheduler UI** (qwenwork.ai/app/schedules): "AgentTrust daily briefing refresh", **Daily at 09:00, next run in ~19 hours** (23 Nov). Task prompt: recompute briefing from audit_events read-only, regenerate snapshot, typecheck/test, republish page_id app-e39f8c62-4ed153f9, report counts. Hard rules: never write to agenttrust.db, never approve/re-evaluate requests, never touch the policy-gate skill; report a skipped run rather than inventing replacements.
- Files: agenttrust.db (main), briefing.py, gen_page_data.py, skills/policy-gate/, output/sales_agent.py, output/scenarios.json.
- Dashboard link added to the Hashmeta trust page honesty block (KM approved via question): `<a href="https://m9j777nb.qwenwork.page/">Live founder dashboard — every decision recorded</a>`. Draft saved 14:03 SGT; **KM clicked Publish ~14:09 SGT; link verified live in the page HTML.**
## 15. Dashboard redesign V3 (22 Nov ~18:48 SGT, presentation-only)

Redesigned the founder dashboard for a non-technical audience via the QwenWork session (task 8m6s, live as V3 on page_id app-e39f8c62-4ed153f9). Logic, rules, data, gate, audit rows and the 09:00 scheduled task untouched; DB checksum 0cb1977f... identical before/after; AR-C still held.

New structure (verified live): H1 "Is my AI agent behaving?" → briefing sentence with client-side grammar fix ("1 was approved") → count cards Sent 1 / Blocked 1 / Needs you 1 → "Needs your decision" (held AR-C) → "The three rules" in plain words with grey P-* tags → "Activity" timeline (SGT times, e.g. "22 Nov, 1:35 PM SGT"; badges green "Sent (demo — email not really sent)" / red "Blocked" / amber "Waiting for you") → "Blocked" section with Ben Lim / Orchid Retail Pte Ltd / ben.lim@example.com / SGD 7,500 highlighted red on light-red + caption → "Allowed (demo, email not really sent)" → collapsed "Show technical details" = original 12-column audit table unchanged → honesty note. No jargon (audit_events/threshold_sgd/model_used etc.) in default view. Phone viewport 390px: no horizontal scroll.

**#6 Approve/Reject buttons NOT built** — static snapshot page cannot append audit rows without a new backend (guardrail: no custom backend); page keeps read-only note "Approve via the AgentTrust session — the approval is logged." Approval path remains the session `--approve` command.

Video-script note: §11 narration references dashboard labels — use the rename list (Awaiting your approval→Needs your decision; ALLOWED stamp→Sent (demo — email not really sent); Approved & sent section→Allowed (demo, email not really sent); Full audit trail→Activity + Show technical details; briefing sentence now reads "1 was approved, 1 was blocked for privacy, and 1 requires your approval").

V4 (22 Nov ~18:48 SGT, task 2m58s, verified live): three presentation fixes — briefing sentence now "1 was sent" (client-side wording, count still from briefing.counts, briefing.py untouched; note: the WARNING-variant fallback sentence still says "approved"); held-card heading now "A quote for Aria Tan (Novacraft Pte Ltd) — SGD 8,000" with company joined from the stored customers row via the existing pipeline (no hard-code, gen_page_data.py byte-identical); Blocked section moved directly under "Needs your decision", above "The three rules". Section order: glance card → Needs your decision → Blocked → The three rules → Activity → Allowed (demo…) → honesty note. Checksum 0cb1977f… unchanged, AR-C still held, counters 1/1/1, phone 390px no h-scroll.

## 16. Founder rename KM → Sum (22 Nov, ~19:30 SGT, V5)

Presentation/text only — gate, policies, audit_events, scheduled task and AR-C untouched; DB checksum unchanged. Trust-page rename PUBLISHED and verified live. One follow-up click remains for KM: console → Publish Center → "Publish 1 to the live site" (queued Site-info change: meta author + keywords "KM Sum" → "Sum (KM Sum)"; the agent's click was blocked by the permission classifier and was not bypassed).

**Hashmeta trust page (published as V5):**
- Hero: "I'm KM, a solo founder in Singapore" → "I'm Sum, …"; "A personal project by KM Sum, Singapore." → "A personal project by Sum, Singapore."
- Honesty sign: "— KM Sum, Singapore" → "— Sum (KM Sum), Singapore".
- JSON-LD schema provider: "KM Sum" → "Sum (KM Sum)".
- Home META description: "KM's AI agents…" → "Sum's AI agents…".
- Site Information: default meta title "How KM's AI Agents Are Governed" → "How Sum's…"; default meta description + keywords + SITE AUTHOR "KM Sum" → "Sum (KM Sum)".

**Deliberately left as KM (with reason):** site name "AgentTrust by KM" (header brand, footer, browser-tab title, og:site_name, JSON-LD org/website name all derive from it; renaming risks regenerating the URL slug `agenttrust-by-km` which must not change); Terms/Privacy lines "operated by AgentTrust by KM" (same brand string); stored draft signatures "— KM" in DB audit rows and demo-fixtures.json (append-only history — not rewritten); internal planning-doc actor labels ("KM films", "KM submits", build-log entries, notes addressed to KM); URL `agenttrust-by-km.geo.hashmeta.tech`.

**Dashboard:** no visible "— KM" outside stored draft text (verified: bundle contains exactly 3 KM hits, all inside frozen draft strings) → unchanged, not republished.

**Video scripts updated to match live copy:** script-3min.md + adal-brief.md narration/captions/on-screen title cards ("I'm Sum…", end card "Sum (KM Sum), Singapore"); spec §11 narration; PRD intro "Sum (KM Sum)".

## 17. Trust-page tidy + dashboard draft-signature rename (22 Nov ~20:00–20:30 SGT)

**Trust page tidy (content/layout only; URL, form→CRM, honesty facts, 3 rules unchanged):** removed viewport-stretch padding (per-block `padding-block: clamp(32px,6vw,64px); min-height:0`, body line-height 1.5); merged "The three rules" + "What happens to every action" into one section (3 cards, outcome badges BLOCK / HOLD FOR APPROVAL / BLOCK, "Pass all three → ALLOW, it goes out."); deleted repeated lead-ins, the log bullet list, the AGENTTRUST eyebrow and "One page, readable in under two minutes."; hero second button "See it working live" → dashboard; new "How it works" 4-step strip; footer line "Built with QwenWork and Hashmeta." Section order live: Hero → The three rules → How it works → Honesty note → Send an enquiry. Word count 384 → 315. Follow-up fix: hero secondary button label was invisible on dark background (`--btn-secondary-fg` = link color) → scoped override `.page-block-hero .btn-secondary { color: hsl(var(--primary-foreground)); border-color: … }`. Published (KM clicks ~19:55 and ~20:2x); verified live at 1280×800 + 390×844 headless screenshots; form still posts to `/api/form-submissions` (not submitted).

**Brand rename completed:** site name → "AgentTrust by Sum"; KM clicked "Publish 3" (~19:42) — live title/og:site_name/header/footer/schema all "AgentTrust by Sum", 0 "AgentTrust by KM" left; URL unchanged (domain is an independent Verified record).

**Dashboard "— KM" → "— Sum" at the source (KM instruction 20:2x, executed by QwenWork agent, V5 same URL):** `action_requests.draft_text` rows AR-A/AR-B/AR-C (substring only; ids/amounts/statuses/timestamps byte-identical), `output/scenarios.json` 3×, `src/data.ts` regenerated. `audit_events` contained 0 signature matches → append-only history never touched. AR-A sent_simulated, AR-B blocked (P-PRIV), AR-C still awaiting_owner_approval (P-FIN); counters 1/1/1. DB checksum legitimately changed 0cb1977f… → 52163a0ddb022a5d7bfd9ec0d49c89d8. Verified independently from live: bundle `index-DNETFxjO.js` contains "— Sum" ×3, "KM" ×0. Local `demo-fixtures.json` updated 5× (incl. scratch scenarios AR-D/AR-E).
