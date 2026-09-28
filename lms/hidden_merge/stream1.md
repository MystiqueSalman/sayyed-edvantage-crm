# Stream 1 (Auth) — 114/114 green
Files: app/models13_auth.py, app/roles13.py, app/auth13.py (auth13_bp), 8 templates (p13_forgot_password, p13_reset_password, p13_otp_login, p13_mfa_setup, p13_mfa_backup_codes, p13_mfa_verify, p13_mfa_disable, p13_oauth_settings.html), test_phase13_auth.py
Modified: app/routes_auth.py (MFA gate in login POST, google_oauth_configured in login GET), app/routes_admin.py (EXTENDED_ROLES in user create/role change), app/operations.py (PERMISSION_MODULES += progress; 5 new roles defaults; has_permission shortcut admin+super_admin; ensure_permission_defaults seeds new roles), requirements.txt (+pyotp==2.10.0)
Tables:
- p13_password_reset_tokens: id PK, user_id INT FK users.id NOT NULL idx, token_hash String(64) NOT NULL UNIQUE idx, expires_at DateTime NOT NULL, used BOOL default False, created_at DateTime
- p13_email_otps: id PK, email String(120) NOT NULL idx, code_hash String(64) NOT NULL, expires_at DateTime NOT NULL, attempts INT default 0, consumed BOOL default 0, created_at DateTime
- p13_user_security: id PK, user_id INT FK users.id NOT NULL UNIQUE idx, totp_secret String(64) NOT NULL, mfa_enabled BOOL default False, backup_codes JSON default [], created_at DateTime
- p13_parent_links: id PK, parent_user_id INT FK users.id NOT NULL idx, student_user_id INT FK users.id NOT NULL idx, created_at DateTime, UniqueConstraint(parent_user_id, student_user_id)
Roles: parent, placement_officer, finance_officer, content_manager, super_admin (app/roles13.py EXTENDED_ROLES)
Blueprint: from .auth13 import auth13_bp; app.register_blueprint(auth13_bp)
Login.html snippet (coordinator applies): Google button w/ google_oauth_configured conditional + otp/forgot links
MFA nav snippet: <a href="{{ url_for('auth13.mfa_setup') }}">Two-factor auth</a> (clean the t() weirdness)
Settings (AppSetting): GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_OAUTH_ENABLED. Email via Phase 2 EmailSettings/app/emailer.py.
Caveats: TOTP secret plaintext (flagged follow-up); new roles fall through to student dashboard landing; money13 dashboard 500 until all blueprints registered (merge fixes); phase9 transient failures were concurrency artifacts.
