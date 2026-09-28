# Phase 13 merge — 2026-09-28
## Streams (all green in isolation, then re-verified merged)
- stream1 auth: 114/114 (models13_auth, roles13, auth13, 8 templates)
- stream2 learning: 84/84 (models13_learning, learn13, video13, 9 templates)
- stream3 ai: 74/74 (models13_ai, memory13, atrisk13, ai13, 9 templates)
- stream4 social: 57/57 (models13_social, social13, 4 templates)
- stream5 money: 47/47 (models13_money, money13, 9 money13_* templates)
- stream6 parked: 41/41 (models13_parked, parked13, 1 template; login.html + README demo-creds removed)
## Coordinator merge edits (app/__init__.py, base.html, login.html, admin_dashboard.html,
## decorators.py, routes_auth.py, routes_main.py, ai_tutor.py; test files guarded for double registration)
## Migration: p13f1a2b3c4d5 (revises 9c1d2e3f4a5b) — 25 tables, DDL from model metadata
## Full suite: 1246/1246 green (829 prior + 417 new)
## Push: 0acc25a8bb596f5607b66b47fde3317b88ab034a
## Live: /health -> phase-13, homepage 200, /leaderboard 200, /labs/sql + /messages + /admin/diagnostics/chat-leads all auth-gated, login page demo-cred free
## Merge bugs found & fixed:
## 1. inject_globals return dict accidentally dropped "announcement" (banner 500->fixed, phase2 92/92)
## 2. stale "migration head is Phase 12" assertions in test_phase10/11/12 -> Phase 13
## 3. stream test files double-registered blueprints after create_app wiring -> guarded
## 4. obsolete "without learn13" check in test_phase13_learning -> updated
## Known follow-ups: TOTP secrets plaintext; parent/content-manager/placement-officer landings are stubs;
## SMTP/Razorpay-live/Stripe-live/Google-OAuth/WhatsApp-notify all still configure-to-enable;
## PG16 chain not re-run on this VM (no postgres; DDL is plain-type generated from metadata).
