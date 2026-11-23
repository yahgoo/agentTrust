export const DATA = {
  "generated_at": "2026-11-23T01:45:35+00:00",
  "source": "agenttrust.db (real demo DB, live query) + briefing.json",
  "policies": [
    {
      "policy_id": "P-EVID",
      "name": "Evidence",
      "rule_text": "Customer-facing technical claims need a supporting evidence record.",
      "check_type": "evidence_required",
      "parameter": "every claim must match a verified evidence row",
      "decision_on_violation": "block",
      "active": 1
    },
    {
      "policy_id": "P-FIN",
      "name": "Financial authority",
      "rule_text": "Quotations above SGD 5,000 require owner approval.",
      "check_type": "amount_threshold",
      "parameter": "threshold_sgd=5000",
      "decision_on_violation": "requires_approval",
      "active": 1
    },
    {
      "policy_id": "P-PRIV",
      "name": "Data privacy",
      "rule_text": "Never expose another customer's confidential information.",
      "check_type": "forbidden_reference",
      "parameter": "referenced_customer_ids must contain only the recipient; draft must not contain another customer's name, company, email, or confidential field values",
      "decision_on_violation": "block",
      "active": 1
    }
  ],
  "customers": [
    {
      "customer_id": "C-001",
      "name": "Aria Tan",
      "company": "Novacraft Pte Ltd",
      "classification": "client-confidential"
    },
    {
      "customer_id": "C-002",
      "name": "Ben Lim",
      "company": "Orchid Retail Pte Ltd",
      "classification": "client-confidential"
    }
  ],
  "leads": [
    {
      "lead_id": "L-001",
      "source": "hashmeta_crm",
      "customer_id": "C-001",
      "enquiry_text": "Hi, I'm interested in your standard package. What does setup involve and how long does it take?",
      "received_at": "2026-11-22T09:00:00+08:00",
      "status": "new"
    }
  ],
  "evidence": [
    {
      "evidence_id": "EV-001",
      "claim": "Standard setup is completed within 5 business days.",
      "source": "Internal delivery playbook v2 (fictional fixture)",
      "verified": 1
    }
  ],
  "requests": [
    {
      "request_id": "AR-A",
      "agent_id": "sales-agent",
      "lead_id": "L-001",
      "customer_id": "C-001",
      "action_type": "send_reply",
      "draft_text": "Hi Aria, thanks for your enquiry about the standard package. Setup includes configuration, data import and a walkthrough session with you. Standard setup is completed within 5 business days. As previously quoted, the standard package is SGD 3,200. Happy to answer any other questions. — Sum",
      "amount_sgd": null,
      "referenced_customer_ids": "[\"C-001\"]",
      "claims": "[\"Standard setup is completed within 5 business days.\"]",
      "status": "sent_simulated",
      "created_at": "2026-11-22T05:35:36+00:00",
      "gate": {
        "decision": "allow",
        "policy_evaluated": "P-PRIV,P-FIN,P-EVID",
        "explanation": "All three policies passed. Reply uses only the recipient's own data, no amount above the limit, and every technical claim has evidence.",
        "event_id": "AEV-AR-A-01"
      }
    },
    {
      "request_id": "AR-B",
      "agent_id": "sales-agent",
      "lead_id": "L-001",
      "customer_id": "C-001",
      "action_type": "send_reply",
      "draft_text": "Hi Aria, thanks for your enquiry about the standard package. Standard setup is completed within 5 business days. For comparison, another client, Ben Lim at Orchid Retail Pte Ltd (ben.lim@example.com), pays SGD 7,500 for the premium package on net-60 payment terms — so the standard package at SGD 3,200 is great value. — Sum",
      "amount_sgd": null,
      "referenced_customer_ids": "[\"C-001\", \"C-002\"]",
      "claims": "[\"Standard setup is completed within 5 business days.\"]",
      "status": "blocked",
      "created_at": "2026-11-22T05:35:41+00:00",
      "gate": {
        "decision": "block",
        "policy_evaluated": "P-PRIV",
        "explanation": "Draft includes confidential records of Ben Lim (C-002). Data privacy policy forbids sharing one customer's data with another.",
        "event_id": "AEV-AR-B-01"
      }
    },
    {
      "request_id": "AR-C",
      "agent_id": "sales-agent",
      "lead_id": "L-001",
      "customer_id": "C-001",
      "action_type": "send_quotation",
      "draft_text": "Quotation for Novacraft Pte Ltd: premium package implementation including configuration, data import, walkthrough session and 30 days of support. Total: SGD 8,000. Valid for 30 days. — Sum",
      "amount_sgd": 8000.0,
      "referenced_customer_ids": "[\"C-001\"]",
      "claims": "[]",
      "status": "awaiting_owner_approval",
      "created_at": "2026-11-22T05:35:41+00:00",
      "gate": {
        "decision": "requires_approval",
        "policy_evaluated": "P-FIN",
        "explanation": "Quote of SGD 8,000 exceeds the SGD 5,000 limit. Held for owner approval; not sent.",
        "event_id": "AEV-AR-C-01"
      }
    }
  ],
  "audit_events": [
    {
      "event_id": "AEV-AR-A-01",
      "request_id": "AR-A",
      "agent_id": "sales-agent",
      "requested_action": "send_reply",
      "data_classification": "client-confidential",
      "policy_evaluated": "P-PRIV,P-FIN,P-EVID",
      "decision": "allow",
      "explanation": "All three policies passed. Reply uses only the recipient's own data, no amount above the limit, and every technical claim has evidence.",
      "evidence_ref": "EV-001",
      "model_used": "none (deterministic rule engine)",
      "token_usage": 0,
      "created_at": "2026-11-22T05:35:36+00:00"
    },
    {
      "event_id": "AEV-AR-B-01",
      "request_id": "AR-B",
      "agent_id": "sales-agent",
      "requested_action": "send_reply",
      "data_classification": "client-confidential",
      "policy_evaluated": "P-PRIV",
      "decision": "block",
      "explanation": "Draft includes confidential records of Ben Lim (C-002). Data privacy policy forbids sharing one customer's data with another.",
      "evidence_ref": "none",
      "model_used": "none (deterministic rule engine)",
      "token_usage": 0,
      "created_at": "2026-11-22T05:35:41+00:00"
    },
    {
      "event_id": "AEV-AR-C-01",
      "request_id": "AR-C",
      "agent_id": "sales-agent",
      "requested_action": "send_quotation",
      "data_classification": "financial",
      "policy_evaluated": "P-FIN",
      "decision": "requires_approval",
      "explanation": "Quote of SGD 8,000 exceeds the SGD 5,000 limit. Held for owner approval; not sent.",
      "evidence_ref": "none",
      "model_used": "none (deterministic rule engine)",
      "token_usage": 0,
      "created_at": "2026-11-22T05:35:41+00:00"
    }
  ],
  "briefing": {
    "date": "2026-11-22",
    "generated_at": "2026-11-22T10:36:29+00:00",
    "source": "data/agenttrust.db / audit_events (live query, not hard-coded)",
    "text": "Today, 3 agent actions were processed. 1 were approved, 1 were blocked for privacy violations, and 1 require your approval. No unauthorized financial transactions were completed.",
    "counts": {
      "processed": 3,
      "approved": 1,
      "blocked_privacy": 1,
      "awaiting_approval": 1
    },
    "checks": {
      "sent_simulated_without_allow_or_approval": [],
      "completed_quotations_without_owner_approval": [],
      "integrity_ok": true,
      "note_non_privacy_blocks_today": 0
    }
  }
} as const;
