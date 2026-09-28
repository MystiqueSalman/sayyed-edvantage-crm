"""Phase 13 Stream 5 — Money + International.

One Blueprint (money13_bp): Stripe payments, installment plans, multi-currency
display, and timezone support. Fully additive — no existing routes, models or
templates are modified by this module (template edits are listed in the
handoff report for the coordinator).

Settings reuse the Phase-10 AppSetting key/value table:
  STRIPE_PUBLISHABLE_KEY / STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET /
  STRIPE_TEST_MODE ("1"/"0", default "1") / CURRENCY_DISPLAY (default "INR").
"""
from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, flash, g, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from . import db
from .decorators import admin_required
from .models import AppSetting, Course, Enrollment, User
from .models13_money import (FxRate13, InstallmentPlan13, LocalePrefs13,
                             StudentInstallment13)

money13_bp = Blueprint("money13", __name__)

DEFAULT_TZ = "Asia/Kolkata"
CURRENCIES = ("INR", "USD", "EUR", "GBP", "AED")

# Built-in fallback estimates (used only when no FxRate13 row exists).
_FALLBACK_RATES = {
    "USD": (83.5, "$"),
    "EUR": (90.0, "\u20ac"),
    "GBP": (105.0, "\u00a3"),
    "AED": (22.7, "AED "),
    "INR": (1.0, "\u20b9"),
}

TIMEZONE_CHOICES = [
    "Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Asia/Tokyo",
    "Australia/Sydney", "Europe/London", "Europe/Berlin", "Europe/Paris",
    "Africa/Cairo", "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "America/Toronto", "America/Sao_Paulo",
    "Pacific/Auckland", "UTC",
]


# ============================================================ settings helpers

def get_setting(key, default=""):
    return AppSetting.get(key, default)


def stripe_configured():
    """Stripe is usable only when both keys are saved in settings."""
    return bool(get_setting("STRIPE_PUBLISHABLE_KEY", "").strip()
                and get_setting("STRIPE_SECRET_KEY", "").strip())


def stripe_test_mode():
    return get_setting("STRIPE_TEST_MODE", "1") == "1"


def currency_display():
    code = (get_setting("CURRENCY_DISPLAY", "INR") or "INR").strip().upper()
    return code if code in CURRENCIES else "INR"


def _stripe():
    """Stripe SDK bound to the saved secret key, or None if unavailable."""
    try:
        import stripe as _s
    except ImportError:
        return None
    secret = get_setting("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        return None
    _s.api_key = secret
    return _s


# ============================================================ multi-currency display

def _fx_rows():
    if not hasattr(g, "_p13_fx"):
        try:
            rows = FxRate13.query.all()
        except Exception:
            rows = []
        g._p13_fx = {r.code: r for r in rows}
    return g._p13_fx


def _fx_rate_for(code):
    row = _fx_rows().get(code)
    if row and row.rate_to_inr and row.rate_to_inr > 0:
        return row.rate_to_inr, row.symbol or code
    fb = _FALLBACK_RATES.get(code)
    return fb if fb else (None, "")


def _fmt_foreign(code, symbol, value):
    rounded = int(round(value))
    if code == "AED":
        return f"AED {rounded:,}"
    return f"{symbol}{rounded:,}"


def display_price(inr):
    """Convert an INR amount for DISPLAY only.

    Returns {"primary": "₹50,000", "secondary": "≈ $599"} — secondary is ""
    when the display currency is INR or no rate is available. The converted
    figure is always prefixed with ≈ and is never exact; checkout always
    charges INR.
    """
    inr = int(inr or 0)
    primary = "\u20b9" + "{:,}".format(inr)
    code = currency_display()
    if code == "INR":
        return {"primary": primary, "secondary": ""}
    rate, symbol = _fx_rate_for(code)
    if not rate:
        return {"primary": primary, "secondary": ""}
    secondary = "\u2248 " + _fmt_foreign(code, symbol, inr / rate)
    return {"primary": primary, "secondary": secondary}


# ============================================================ timezone support

try:
    from zoneinfo import ZoneInfo, available_timezones
except Exception:  # pragma: no cover - very old Pythons
    ZoneInfo = None

    def available_timezones():  # noqa: F811
        return set()


def valid_timezone(name):
    """True iff `name` is a real IANA timezone."""
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    if ZoneInfo is None:
        return name in TIMEZONE_CHOICES
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def user_timezone(user=None):
    """Resolve the display timezone for a user (or user-like / tz string)."""
    if isinstance(user, str) and valid_timezone(user):
        return user
    uid = None
    try:
        if user is not None and getattr(user, "is_authenticated", False):
            uid = getattr(user, "id", None)
    except Exception:
        uid = None
    if uid:
        try:
            prefs = LocalePrefs13.query.filter_by(user_id=uid).first()
            if prefs and valid_timezone(prefs.timezone):
                return prefs.timezone
        except Exception:
            pass
    return DEFAULT_TZ


def to_user_tz(dt, user=None):
    """Convert a stored datetime to the viewer's timezone.

    Stored datetimes are naive wall-clock times entered in IST
    (Asia/Kolkata) — e.g. live-class times typed by an admin — so a naive
    value is first assumed to be Asia/Kolkata, then converted. Aware values
    are converted directly. Returns None for None.
    """
    if dt is None:
        return None
    tzname = user_timezone(user)
    if ZoneInfo is None:  # pragma: no cover
        return dt
    tz = ZoneInfo(tzname)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
    return dt.astimezone(tz)


def get_locale_prefs(user_id):
    prefs = LocalePrefs13.query.filter_by(user_id=user_id).first()
    if not prefs:
        prefs = LocalePrefs13(user_id=user_id, timezone=DEFAULT_TZ)
        db.session.add(prefs)
        db.session.commit()
    return prefs


# ============================================================ installments

def refresh_overdue():
    """Flip pending installments past their due date to overdue."""
    today = datetime.utcnow().date()
    n = (StudentInstallment13.query
         .filter(StudentInstallment13.status == StudentInstallment13.STATUS_PENDING,
                 StudentInstallment13.due_date < today)
         .update({StudentInstallment13.status: StudentInstallment13.STATUS_OVERDUE},
                 synchronize_session=False))
    if n:
        db.session.commit()
    return n


def generate_installment_schedule(user_id, plan, start_date=None):
    """Create the per-installment rows for an enrollment on `plan`."""
    start = start_date or datetime.utcnow().date()
    amounts = plan.amounts or []
    due_days = plan.due_days or []
    rows = []
    for i in range(int(plan.num_installments or 0)):
        try:
            amt = int(amounts[i]) if i < len(amounts) else 0
        except (TypeError, ValueError):
            amt = 0
        try:
            dd = int(due_days[i]) if i < len(due_days) else 0
        except (TypeError, ValueError):
            dd = 0
        rows.append(StudentInstallment13(
            user_id=user_id, plan_id=plan.id, course_id=plan.course_id,
            installment_no=i + 1, amount_inr=max(0, amt),
            due_date=start + timedelta(days=max(0, dd)),
            status=StudentInstallment13.STATUS_PENDING))
    db.session.add_all(rows)
    db.session.commit()
    return rows


def student_schedule(user_id, course_id):
    return (StudentInstallment13.query
            .filter_by(user_id=user_id, course_id=course_id)
            .order_by(StudentInstallment13.installment_no).all())


def next_unpaid_installment(user_id, course_id):
    return (StudentInstallment13.query
            .filter(StudentInstallment13.user_id == user_id,
                    StudentInstallment13.course_id == course_id,
                    StudentInstallment13.status.in_(
                        [StudentInstallment13.STATUS_PENDING,
                         StudentInstallment13.STATUS_OVERDUE]))
            .order_by(StudentInstallment13.installment_no).first())


def overdue_summary(limit=50):
    rows = (StudentInstallment13.query
            .filter_by(status=StudentInstallment13.STATUS_OVERDUE)
            .order_by(StudentInstallment13.due_date).all())
    out = []
    for r in rows[:limit]:
        out.append({
            "id": r.id,
            "student": r.user.name if r.user else f"user {r.user_id}",
            "email": r.user.email if r.user else "",
            "course": r.course.title if r.course else f"course {r.course_id}",
            "installment_no": r.installment_no,
            "amount_inr": r.amount_inr,
            "due_date": r.due_date,
        })
    return {"count": len(rows), "rows": out}


# ============================================================ payment finalization
# Mirrors the Phase-3 Razorpay success block in routes_main.payment_confirm
# so Stripe completions record payments + enrollments identically.

def finalize_enrollment_payment(enrollment, payment_ref, notify=True):
    """Mark an enrollment paid/active after a successful gateway payment.

    Mirrors the Phase-3 Razorpay success block (routes_main.payment_confirm):
    the payable amount is already recorded on the pending enrollment, so this
    only flips state + runs the notification/attribution fan-out.
    """
    user = User.query.get(enrollment.user_id)
    enrollment.paid = True
    enrollment.status = Enrollment.STATUS_ACTIVE
    # Reuse the existing payment-ref column so the finance history keeps
    # working; Stripe refs are prefixed to stay distinguishable.
    enrollment.razorpay_payment_id = payment_ref
    if enrollment.coupon_code:
        from .models import Coupon
        coupon = Coupon.query.filter_by(code=enrollment.coupon_code).first()
        if coupon:
            coupon.used_count += 1
    db.session.commit()
    if not notify or user is None:
        return
    try:
        from . import hardening as _H
        _H.emit_enrollment(user, enrollment, payment_completed=True)
    except Exception:
        pass  # events must never break payment confirmation
    try:
        from .emailer import send_enrollment_email
        send_enrollment_email(user, enrollment)
    except Exception:
        pass
    try:
        from .growth import maybe_reward_referral
        from .whatsapp import (send_enrollment_whatsapp,
                               send_payment_receipt_whatsapp)
        maybe_reward_referral(user)
        send_enrollment_whatsapp(user, enrollment)
        send_payment_receipt_whatsapp(user, enrollment)
    except Exception:
        pass  # growth/WhatsApp must never break payment confirmation
    try:
        from .marketing import attribute_enrollment, record_affiliate_earning
        attribute_enrollment(enrollment)
        db.session.commit()
        record_affiliate_earning(enrollment)
    except Exception:
        pass  # attribution must never break payment confirmation


def mark_installment_paid(inst, payment_ref, notify_first=True):
    """Record an installment as paid; first installment activates enrollment."""
    if inst.status == StudentInstallment13.STATUS_PAID:
        return False
    inst.status = StudentInstallment13.STATUS_PAID
    inst.paid_at = datetime.utcnow()
    inst.payment_ref = payment_ref or ""
    enrollment = (Enrollment.query
                  .filter_by(user_id=inst.user_id, course_id=inst.course_id)
                  .first())
    if enrollment:
        enrollment.amount_paid = ((enrollment.amount_paid or 0)
                                  + inst.amount_inr)
        db.session.commit()
    if enrollment and inst.installment_no == 1 and not enrollment.paid:
        finalize_enrollment_payment(enrollment, payment_ref,
                                    notify=notify_first)
    return True

# ============================================================ Stripe checkout

def _stripe_urls(enrollment_id):
    return {
        "success": url_for("money13.stripe_success",
                           enrollment_id=enrollment_id, _external=True)
                   + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel": url_for("money13.stripe_cancel",
                          enrollment_id=enrollment_id, _external=True),
    }


def _get_or_create_pending_enrollment(user, course):
    """Mirror of the enroll-confirm block (full fee, no coupon)."""
    existing = Enrollment.query.filter_by(
        user_id=user.id, course_id=course.id).first()
    if existing and existing.status != Enrollment.STATUS_PENDING:
        return existing, False
    if existing:
        db.session.delete(existing)
        db.session.flush()
    enrollment = Enrollment(
        user_id=user.id, course_id=course.id,
        status=Enrollment.STATUS_PENDING, paid=False,
        amount_paid=course.fee or 0, coupon_code="")
    db.session.add(enrollment)
    db.session.commit()
    return enrollment, True


def _create_stripe_session(enrollment, amount_inr, metadata):
    s = _stripe()
    if s is None:
        raise RuntimeError("Stripe is not configured.")
    urls = _stripe_urls(enrollment.id)
    metadata = dict(metadata or {})
    metadata.update({
        "enrollment_id": str(enrollment.id),
        "user_id": str(enrollment.user_id),
        "course_id": str(enrollment.course_id),
        "test_mode": "1" if stripe_test_mode() else "0",
    })
    session = s.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "inr",
                "unit_amount": int(amount_inr) * 100,
                "product_data": {"name": (enrollment.course.title
                                          if enrollment.course
                                          else "Course fee")},
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=urls["success"],
        cancel_url=urls["cancel"],
        metadata=metadata,
    )
    return session


@money13_bp.route("/pay/stripe/course/<int:course_id>",
                  methods=["GET", "POST"])
@login_required
def stripe_pay_course(course_id):
    """Start a Stripe payment for a course (creates a pending enrollment)."""
    course = Course.query.get_or_404(course_id)
    enrollment, _ = _get_or_create_pending_enrollment(current_user, course)
    return redirect(url_for("money13.stripe_pay_enrollment",
                            enrollment_id=enrollment.id))


@money13_bp.route("/pay/stripe/enrollment/<int:enrollment_id>",
                  methods=["GET", "POST"])
@login_required
def stripe_pay_enrollment(enrollment_id):
    """Stripe checkout page for a pending enrollment."""
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.user_id != current_user.id:
        abort(403)
    if enrollment.status != Enrollment.STATUS_PENDING:
        flash("This enrollment is already paid.", "info")
        return redirect(url_for("student.dashboard"))
    if not stripe_configured():
        flash("Stripe payments are not configured yet. "
              "Please use the standard checkout.", "warning")
        return redirect(url_for("main.checkout", enrollment_id=enrollment.id))

    schedule = student_schedule(current_user.id, enrollment.course_id)
    plans = (InstallmentPlan13.query
             .filter_by(course_id=enrollment.course_id, active=True).all())

    if request.method == "POST":
        choice = (request.form.get("plan_choice") or "full").strip()
        inst = None
        amount = enrollment.amount_paid or 0
        metadata = {}
        if choice.startswith("plan:") and not schedule:
            plan = InstallmentPlan13.query.get(int(choice.split(":")[1]))
            if plan and plan.course_id == enrollment.course_id and plan.active:
                schedule = generate_installment_schedule(
                    current_user.id, plan)
        if schedule:
            inst = next_unpaid_installment(current_user.id,
                                           enrollment.course_id)
            if inst is None:
                flash("All installments are already paid.", "info")
                return redirect(url_for("money13.billing"))
            amount = inst.amount_inr
            metadata["installment_id"] = str(inst.id)
        if amount <= 0:
            flash("Nothing to pay.", "warning")
            return redirect(url_for("money13.billing"))
        try:
            session = _create_stripe_session(enrollment, amount, metadata)
        except Exception as exc:  # noqa: BLE001 - surface gateway errors
            flash(f"Stripe error: {exc}", "danger")
            return redirect(url_for("money13.stripe_pay_enrollment",
                                    enrollment_id=enrollment.id))
        return redirect(session.url, code=303)

    inst = next_unpaid_installment(current_user.id, enrollment.course_id)
    return render_template(
        "money13_stripe_checkout.html", enrollment=enrollment,
        schedule=schedule, plans=plans, next_installment=inst,
        test_mode=stripe_test_mode(),
        publishable_key=get_setting("STRIPE_PUBLISHABLE_KEY", ""))


@money13_bp.route("/pay/stripe/success/<int:enrollment_id>")
@login_required
def stripe_success(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.user_id != current_user.id:
        abort(403)
    return render_template("money13_stripe_result.html", enrollment=enrollment,
                           test_mode=stripe_test_mode(), cancelled=False)


@money13_bp.route("/pay/stripe/cancel/<int:enrollment_id>")
@login_required
def stripe_cancel(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.user_id != current_user.id:
        abort(403)
    return render_template("money13_stripe_result.html", enrollment=enrollment,
                           test_mode=stripe_test_mode(), cancelled=True)


@money13_bp.route("/webhooks/stripe", methods=["POST"])
def stripe_webhook():
    """Stripe webhook: verify signature, complete checkout sessions."""
    s = _stripe()
    secret = get_setting("STRIPE_WEBHOOK_SECRET", "").strip()
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    if s is None or not secret:
        return jsonify({"error": "stripe not configured"}), 400
    try:
        event = s.Webhook.construct_event(payload, sig, secret)
    except Exception:
        return jsonify({"error": "invalid signature"}), 400
    if event.get("type") == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])
    return jsonify({"received": True}), 200


def _handle_checkout_completed(sess):
    meta = sess.get("metadata") or {}
    enrollment_id = meta.get("enrollment_id")
    if not enrollment_id:
        return
    enrollment = Enrollment.query.get(int(enrollment_id))
    if enrollment is None:
        return
    payment_ref = ("stripe_" + str(sess.get("payment_intent") or sess.get("id")))
    installment_id = meta.get("installment_id")
    if installment_id:
        inst = StudentInstallment13.query.get(int(installment_id))
        if inst is None or inst.status == StudentInstallment13.STATUS_PAID:
            return  # idempotent: already handled
        mark_installment_paid(inst, payment_ref, notify_first=True)
        return
    if enrollment.paid:
        return  # idempotent: already handled
    # amount_total is informational here: the payable INR amount was already
    # recorded on the pending enrollment (same as the Razorpay flow).
    finalize_enrollment_payment(enrollment, payment_ref, notify=True)


# ============================================================ Stripe admin settings

@money13_bp.route("/admin/payments/stripe", methods=["GET", "POST"])
@admin_required
def stripe_settings():
    if request.method == "POST":
        pub = request.form.get("publishable_key", "").strip()
        sec = request.form.get("secret_key", "").strip()
        wh = request.form.get("webhook_secret", "").strip()
        # Only overwrite secrets when a new value is typed (never echo back).
        if pub:
            AppSetting.set("STRIPE_PUBLISHABLE_KEY", pub)
        if sec:
            AppSetting.set("STRIPE_SECRET_KEY", sec)
        if wh:
            AppSetting.set("STRIPE_WEBHOOK_SECRET", wh)
        AppSetting.set("STRIPE_TEST_MODE",
                       "1" if request.form.get("test_mode") else "0")
        flash("Stripe settings saved.", "success")
        return redirect(url_for("money13.stripe_settings"))
    return render_template(
        "money13_stripe_settings.html",
        configured=stripe_configured(),
        test_mode=stripe_test_mode(),
        publishable_key=get_setting("STRIPE_PUBLISHABLE_KEY", ""),
        webhook_url=url_for("money13.stripe_webhook", _external=True))


# ============================================================ installment plan admin CRUD

def _parse_csv_ints(value, expect=None):
    parts = [p.strip() for p in (value or "").split(",") if p.strip()]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if expect is not None and len(nums) != expect:
        return None
    return nums


@money13_bp.route("/admin/installment-plans")
@admin_required
def installment_plans():
    plans = (InstallmentPlan13.query
             .order_by(InstallmentPlan13.course_id,
                       InstallmentPlan13.id).all())
    return render_template("money13_installment_plans.html", plans=plans)


@money13_bp.route("/admin/installment-plans/new", methods=["GET", "POST"])
@admin_required
def installment_plan_new():
    return _installment_plan_form(None)


@money13_bp.route("/admin/installment-plans/<int:plan_id>/edit",
                  methods=["GET", "POST"])
@admin_required
def installment_plan_edit(plan_id):
    plan = InstallmentPlan13.query.get_or_404(plan_id)
    return _installment_plan_form(plan)


def _installment_plan_form(plan):
    courses = Course.query.order_by(Course.title).all()
    if request.method == "POST":
        try:
            num = max(1, min(24, int(request.form.get("num_installments") or 1)))
        except ValueError:
            num = 1
        amounts = _parse_csv_ints(request.form.get("amounts"), expect=num)
        due_days = _parse_csv_ints(request.form.get("due_days"), expect=num)
        course_id = request.form.get("course_id", type=int)
        name = request.form.get("name", "").strip()
        course = Course.query.get(course_id) if course_id else None
        if not course or not name or amounts is None or due_days is None:
            flash("Fill every field: course, name, and exactly "
                  f"{num} comma-separated amounts and due-days.", "danger")
            return render_template("money13_installment_plan_form.html",
                                   plan=plan, courses=courses)
        if plan is None:
            plan = InstallmentPlan13(created_by=current_user.id)
            db.session.add(plan)
        plan.course_id = course.id
        plan.name = name
        plan.num_installments = num
        plan.amounts = amounts
        plan.due_days = due_days
        plan.active = bool(request.form.get("active"))
        db.session.commit()
        flash("Installment plan saved.", "success")
        return redirect(url_for("money13.installment_plans"))
    return render_template("money13_installment_plan_form.html",
                           plan=plan, courses=courses)


@money13_bp.route("/admin/installment-plans/<int:plan_id>/toggle",
                  methods=["POST"])
@admin_required
def installment_plan_toggle(plan_id):
    plan = InstallmentPlan13.query.get_or_404(plan_id)
    plan.active = not plan.active
    db.session.commit()
    flash(f"Plan {'activated' if plan.active else 'deactivated'}.", "success")
    return redirect(url_for("money13.installment_plans"))


@money13_bp.route("/admin/installment-plans/<int:plan_id>/delete",
                  methods=["POST"])
@admin_required
def installment_plan_delete(plan_id):
    plan = InstallmentPlan13.query.get_or_404(plan_id)
    db.session.delete(plan)
    db.session.commit()
    flash("Installment plan deleted.", "success")
    return redirect(url_for("money13.installment_plans"))


@money13_bp.route("/admin/installments/<int:inst_id>/mark-paid",
                  methods=["POST"])
@admin_required
def installment_mark_paid(inst_id):
    inst = StudentInstallment13.query.get_or_404(inst_id)
    ref = request.form.get("payment_ref", "").strip() or "manual:admin"
    mark_installment_paid(inst, f"manual:{ref}", notify_first=False)
    flash(f"Installment #{inst.installment_no} marked paid.", "success")
    return redirect(request.referrer or url_for("money13.installment_plans"))


# ============================================================ FX rates admin

def seed_fx_rates(admin_id=None):
    """Insert estimate rows when the table is empty (idempotent)."""
    if FxRate13.query.count():
        return
    for code, (rate, symbol) in sorted(_FALLBACK_RATES.items()):
        db.session.add(FxRate13(code=code, rate_to_inr=rate, symbol=symbol,
                                updated_by=admin_id))
    db.session.commit()


@money13_bp.route("/admin/fx-rates", methods=["GET", "POST"])
@admin_required
def fx_rates():
    seed_fx_rates(getattr(current_user, "id", None))
    if request.method == "POST":
        disp = (request.form.get("currency_display") or "INR").strip().upper()
        if disp in CURRENCIES:
            AppSetting.set("CURRENCY_DISPLAY", disp)
        for rate in FxRate13.query.all():
            raw = request.form.get(f"rate_{rate.code}", "").strip()
            sym = request.form.get(f"symbol_{rate.code}", "").strip()
            try:
                val = float(raw)
                if val > 0:
                    rate.rate_to_inr = val
            except ValueError:
                pass
            if sym:
                rate.symbol = sym[:12]
            rate.updated_by = current_user.id
        db.session.commit()
        flash("Currency settings saved.", "success")
        return redirect(url_for("money13.fx_rates"))
    rates = FxRate13.query.order_by(FxRate13.code).all()
    return render_template("money13_fx_rates.html", rates=rates,
                           display=currency_display(),
                           currencies=CURRENCIES)


# ============================================================ student billing

@money13_bp.route("/billing/installments")
@login_required
def billing():
    refresh_overdue()
    rows = (StudentInstallment13.query
            .filter_by(user_id=current_user.id)
            .order_by(StudentInstallment13.due_date,
                      StudentInstallment13.installment_no).all())
    return render_template("money13_installments.html", rows=rows,
                           stripe_ok=stripe_configured(),
                           today=datetime.utcnow().date())


@money13_bp.route("/billing/installments/<int:inst_id>/pay", methods=["POST"])
@login_required
def installment_pay(inst_id):
    inst = StudentInstallment13.query.get_or_404(inst_id)
    if inst.user_id != current_user.id:
        abort(403)
    if inst.status == StudentInstallment13.STATUS_PAID:
        flash("This installment is already paid.", "info")
        return redirect(url_for("money13.billing"))
    if not stripe_configured():
        flash("Online payment is not configured — please contact support.",
              "warning")
        return redirect(url_for("money13.billing"))
    enrollment = (Enrollment.query
                  .filter_by(user_id=current_user.id,
                             course_id=inst.course_id).first())
    if enrollment is None or enrollment.status != Enrollment.STATUS_PENDING:
        # Ensure a pending enrollment exists for metadata/finalization.
        enrollment, _ = _get_or_create_pending_enrollment(
            current_user, inst.course)
    try:
        session = _create_stripe_session(
            enrollment, inst.amount_inr,
            {"installment_id": str(inst.id)})
    except Exception as exc:  # noqa: BLE001
        flash(f"Stripe error: {exc}", "danger")
        return redirect(url_for("money13.billing"))
    return redirect(session.url, code=303)


@money13_bp.route("/billing/choose-plan/<int:course_id>")
@login_required
def choose_plan(course_id):
    course = Course.query.get_or_404(course_id)
    plans = (InstallmentPlan13.query
             .filter_by(course_id=course.id, active=True).all())
    existing = student_schedule(current_user.id, course.id)
    return render_template("money13_choose_plan.html", course=course, plans=plans,
                           existing=existing, stripe_ok=stripe_configured())


@money13_bp.route("/billing/enroll-with-plan/<int:plan_id>", methods=["POST"])
@login_required
def enroll_with_plan(plan_id):
    plan = InstallmentPlan13.query.get_or_404(plan_id)
    if not plan.active:
        flash("This plan is no longer available.", "warning")
        return redirect(url_for("money13.choose_plan",
                                course_id=plan.course_id))
    existing = Enrollment.query.filter_by(
        user_id=current_user.id, course_id=plan.course_id).first()
    if existing and existing.status != Enrollment.STATUS_PENDING:
        flash("You are already enrolled in this course.", "info")
        return redirect(url_for("student.dashboard"))
    if existing:
        db.session.delete(existing)
        db.session.flush()
    enrollment = Enrollment(
        user_id=current_user.id, course_id=plan.course_id,
        status=Enrollment.STATUS_PENDING, paid=False, amount_paid=0,
        coupon_code="")
    db.session.add(enrollment)
    db.session.commit()
    generate_installment_schedule(current_user.id, plan)
    flash(f"Enrolled with plan “{plan.name}” — pay the first installment "
          "to activate your course.", "success")
    return redirect(url_for("money13.stripe_pay_enrollment",
                            enrollment_id=enrollment.id))


# ============================================================ timezone prefs

@money13_bp.route("/settings/timezone", methods=["GET", "POST"])
@login_required
def timezone_settings():
    prefs = get_locale_prefs(current_user.id)
    error = ""
    if request.method == "POST":
        tz = (request.form.get("timezone") or "").strip()
        if not valid_timezone(tz):
            error = f"“{tz}” is not a valid timezone."
        else:
            prefs.timezone = tz
            db.session.commit()
            flash(f"Timezone set to {tz}.", "success")
            return redirect(url_for("money13.timezone_settings"))
    return render_template("money13_timezone.html", prefs=prefs,
                           choices=TIMEZONE_CHOICES, error=error)


# ============================================================ template context
# Injects helpers app-wide + refreshes overdue flags on finance dashboard load.

@money13_bp.app_context_processor
def inject_money13():
    try:
        endpoint = request.endpoint
    except RuntimeError:
        endpoint = None  # template rendered outside a request (e.g. email)
    ctx = {
        "stripe_configured": stripe_configured(),
        "stripe_test_mode": stripe_test_mode(),
        "currency_display_code": currency_display(),
        "display_price": display_price,
        "to_user_tz": to_user_tz,
        "user_timezone": user_timezone,
    }
    if endpoint == "ops.finance":
        try:
            refresh_overdue()
            ctx["p13_overdue"] = overdue_summary()
        except Exception:
            ctx["p13_overdue"] = {"count": 0, "rows": []}
    return ctx
