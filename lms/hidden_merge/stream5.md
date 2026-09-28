# Stream 5 (Money + International) — 47/47 green
Files: app/models13_money.py, app/money13.py (money13_bp), 9 templates (money13_*), test_phase13_money.py
Modified: requirements.txt (+stripe==15.6.1, pip-installed), courses.html + course_detail.html (price display), ops_finance.html (overdue widget), course_detail.html + dashboard.html + manage_course.html + ops_attendance_mark.html (timezone display)
Tables:
- installment_plans_13: id PK, course_id INT FK courses.id NOT NULL idx, name VARCHAR(120), num_installments INT, amounts JSON, due_days JSON, active BOOL default True idx, created_by INT FK users.id NULL, created_at DateTime
- student_installments_13: id PK, user_id INT FK users.id NOT NULL idx, plan_id INT FK installment_plans_13.id NOT NULL idx, course_id INT FK courses.id NOT NULL idx, installment_no INT, amount_inr INT, due_date DATE idx, status VARCHAR(16) default 'pending' idx, paid_at DateTime NULL, payment_ref VARCHAR(120) default ''
- fx_rates_13: id PK, code VARCHAR(8) UNIQUE NOT NULL idx, rate_to_inr FLOAT, symbol VARCHAR(12), updated_at DateTime, updated_by INT FK users.id NULL
- locale_prefs_13: id PK, user_id INT FK users.id UNIQUE NOT NULL idx, timezone VARCHAR(64) default 'Asia/Kolkata', updated_at DateTime
Blueprint: from .money13 import money13_bp; app.register_blueprint(money13_bp)
IMPORTANT: templates call display_price()/to_user_tz() via bp context processor — registration must land same deploy.
Settings (AppSetting): STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_TEST_MODE default "1", CURRENCY_DISPLAY default "INR"
Stripe refs stored in Enrollment.razorpay_payment_id prefixed stripe_.
Nav snippets: base.html: billing (money13.billing); admin: money13.stripe_settings, money13.installment_plans, money13.fx_rates; profile: money13.timezone_settings; checkout.html: stripe button w/ stripe_configured; enroll/course_detail: money13.choose_plan link when plans exist.
Caveats: template prefix collision mid-run (another stream) — used money13_*; verify template ownership at merge. dashboard countdown data-starts untouched deliberately. zoneinfo Asia/Dubai abbrev cosmetic.
