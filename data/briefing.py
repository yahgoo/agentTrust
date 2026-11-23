#!/usr/bin/env python3
"""AgentTrust daily briefing — computed LIVE from audit_events. Fictional demo data.

Reads the REAL agenttrust.db read-only, counts today's audit decisions, runs the
sent_simulated integrity check, and writes dashboard/briefing.json for the
founder dashboard's "Generate today's briefing" section. Never hard-codes numbers.
"""
import datetime as dt, json, sqlite3, sys
from pathlib import Path

DB   = Path(__file__).resolve().parent / "agenttrust.db"
OUT  = Path(__file__).resolve().parent / "dashboard" / "briefing.json"
WORD = ("Today, {n} agent actions were processed. {a} were approved, "
        "{b} were blocked for privacy violations, and {c} require your approval. "
        "No unauthorized financial transactions were completed.")

def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    today = dt.date.today().isoformat()
    q = lambda sql, *a: con.execute(sql, a).fetchone()[0]

    n = q("SELECT COUNT(*) FROM audit_events WHERE date(created_at) = ?", today)
    a = q("""SELECT COUNT(*) FROM audit_events
             WHERE date(created_at)=? AND decision='allow'""", today)
    b = q("""SELECT COUNT(*) FROM audit_events
             WHERE date(created_at)=? AND decision='block'
               AND policy_evaluated='P-PRIV'""", today)
    c = q("""SELECT COUNT(*) FROM audit_events
            WHERE date(created_at)=? AND decision='requires_approval'""", today)
    other_blocks = n - a - b - c - q(
        """SELECT COUNT(*) FROM audit_events WHERE date(created_at)=?
           AND decision='approved_by_owner'""", today)

    # Integrity check: every sent_simulated request was allowed (or owner-approved)
    offenders = con.execute("""
        SELECT r.request_id FROM action_requests r
        WHERE r.status='sent_simulated'
          AND NOT EXISTS (SELECT 1 FROM audit_events e
                          WHERE e.request_id = r.request_id
                            AND e.decision IN ('allow','approved_by_owner'))""").fetchall()
    # Financial check: no quotation completed (sent_simulated) without owner approval
    unauth_fin = con.execute("""
        SELECT r.request_id FROM action_requests r
        WHERE r.action_type='send_quotation' AND r.status='sent_simulated'
          AND NOT EXISTS (SELECT 1 FROM audit_events e
                          WHERE e.request_id=r.request_id
                            AND e.decision='approved_by_owner')""").fetchall()

    financial_claim_true = not unauth_fin
    text = WORD.format(n=n, a=a, b=b, c=c)
    if not financial_claim_true:
        text = ("Today, {n} agent actions were processed. {a} were approved, {b} were "
                "blocked for privacy violations, and {c} require your approval. WARNING: "
                "{f} completed quotation(s) lack a recorded owner approval.").format(
                n=n, a=a, b=b, c=c, f=len(unauth_fin))

    briefing = {
        "date": today,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "data/agenttrust.db / audit_events (live query, not hard-coded)",
        "text": text,
        "counts": {"processed": n, "approved": a, "blocked_privacy": b,
                   "awaiting_approval": c},
        "checks": {
            "sent_simulated_without_allow_or_approval": [r[0] for r in offenders],
            "completed_quotations_without_owner_approval": [r[0] for r in unauth_fin],
            "integrity_ok": not offenders and not unauth_fin,
            "note_non_privacy_blocks_today": other_blocks,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(briefing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(briefing, indent=2, ensure_ascii=False))
    con.close()
    return 0 if briefing["checks"]["integrity_ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
