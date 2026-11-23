#!/usr/bin/env python3
"""Regenerate the founder dashboard's data snapshot src/data.ts from the REAL,
read-only agenttrust.db + the live-computed dashboard/briefing.json.
Fictional demo data. Main DB is opened read-only; nothing is ever written to it.

Usage: python3 gen_page_data.py <repo_path>
"""
import datetime as dt, json, sqlite3, sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "data"
DB = OUTPUT / "agenttrust.db"
BRIEFING = OUTPUT / "dashboard" / "briefing.json"
AUDIT_ORDER = "ORDER BY created_at, event_id"

def main():
    repo = Path(sys.argv[1]).resolve()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    def q(sql, *a):
        cur = con.execute(sql, a)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "agenttrust.db (real demo DB, live query) + briefing.json",
        "policies": q("SELECT * FROM policies ORDER BY policy_id"),
        "customers": q("SELECT customer_id, name, company, classification FROM customers "
                       "ORDER BY customer_id"),
        "leads": q("SELECT lead_id, source, customer_id, enquiry_text, received_at, status "
                   "FROM leads ORDER BY lead_id"),
        "evidence": q("SELECT * FROM evidence ORDER BY evidence_id"),
        "requests": q("SELECT * FROM action_requests ORDER BY request_id"),
        "audit_events": q(f"SELECT * FROM audit_events {AUDIT_ORDER}"),
    }
    con.close()

    latest = {}
    for e in data["audit_events"]:
        latest[e["request_id"]] = e  # last row per request wins (chronological)
    for r in data["requests"]:
        g = latest.get(r["request_id"], {})
        r["gate"] = {k: g.get(k) for k in ("decision", "policy_evaluated",
                                           "explanation", "event_id")} or None

    if BRIEFING.exists():
        data["briefing"] = json.loads(BRIEFING.read_text(encoding="utf-8"))
    else:
        data["briefing"] = None

    ts = ("export const DATA = " + json.dumps(data, indent=2, ensure_ascii=False)
          + " as const;\n")
    (repo / "src" / "data.ts").write_text(ts, encoding="utf-8")
    print(f"wrote {repo/'src/data.ts'}: {len(data['requests'])} requests, "
          f"{len(data['audit_events'])} audit rows, "
          f"briefing {'present' if data['briefing'] else 'MISSING'}")

if __name__ == "__main__":
    main()
