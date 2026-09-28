# Stream 6 (Parked fixes) — 41/41 green
Files: app/models13_parked.py (LeadCaptureLog13 + log_capture_error), app/parked13.py (parked13_bp, capture_chat_lead, GET /admin/diagnostics/chat-leads admin-only), templates admin_diagnostics_chat_leads.html, test_phase13_parked.py
Modified: app/routes_crm.py (chat lead-capture block → capture_chat_lead), app/templates/login.html (demo block removed), README.md (demo creds removed)
Root cause: bare `except: rollback` around entire capture path — any exception in post-write enrichment rolled back the lead, zero logging. Fix: validate-first, tight transaction commits lead first, enrichment can't un-create it, duplicate phones update, CHAT-LEAD logging + LeadCaptureLog13 rows.
Table lead_capture_log13: id PK, created_at DATETIME indexed default utcnow, stage VARCHAR(40), lead_email_or_phone VARCHAR(120), error TEXT, payload_summary TEXT
Blueprint: from .parked13 import parked13_bp; app.register_blueprint(parked13_bp)
Diagnostics: /admin/diagnostics/chat-leads shows 20 recent source='chat' leads + 20 recent errors.
Regressions: test_chat_fixes 43/43, test_phase4 80/80.
