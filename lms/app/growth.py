"""Referral & Earn business logic (Phase 3, brief §14).

- Every user gets a unique referral code + shareable /r/<code> link.
- Clicks are deduped per (code, visitor IP).
- Signup attribution happens at registration via the se_ref cookie.
- When a referred user completes their FIRST paid enrollment, the referrer
  is auto-issued a discount coupon (percent from ReferralSettings).
- Fraud controls: no self-referral, one referral row per referred user,
  one reward per referred user, admin validate/invalidate.
"""
import hashlib
import secrets
import string
from datetime import datetime

from flask import request

from . import db
from .models import Coupon, Enrollment, Referral, ReferralClick, ReferralSettings

CODE_ALPHABET = string.ascii_uppercase + string.digits
REF_COOKIE = "se_ref"


def _new_code(prefix="SE", length=6):
    for _ in range(20):
        code = prefix + "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
        return code
    raise RuntimeError("could not generate unique code")


def get_or_create_referral_code(user):
    """Return the user's referral code, generating one if missing."""
    if user.referral_code:
        return user.referral_code
    for _ in range(20):
        code = _new_code()
        if not user.__class__.query.filter_by(referral_code=code).first():
            user.referral_code = code
            db.session.commit()
            return code
    raise RuntimeError("could not generate unique referral code")


def record_click(code, ip=None):
    """Record a referral-link click. Duplicate (code, IP) clicks are ignored."""
    from .models import User
    if not code or not User.query.filter_by(referral_code=code.upper()).first():
        return False
    code = code.upper()
    ip = ip or (request.remote_addr if request else "") or ""
    ip_hash = hashlib.sha256(f"{code}:{ip}".encode()).hexdigest()
    if ReferralClick.query.filter_by(code=code, ip_hash=ip_hash).first():
        return False  # duplicate click — deduped
    db.session.add(ReferralClick(code=code, ip_hash=ip_hash))
    db.session.commit()
    return True


def attribute_signup(user, code):
    """Attribute a new signup to a referrer. Returns the Referral or None.

    Guards: program enabled, code valid, no self-referral, one row per user.
    """
    settings = ReferralSettings.get()
    if not settings.enabled or not code:
        return None
    from .models import User
    referrer = User.query.filter_by(referral_code=code.upper()).first()
    if not referrer or referrer.id == user.id:
        return None  # unknown code or self-referral
    if Referral.query.filter_by(referred_id=user.id).first():
        return None  # already attributed
    ref = Referral(referrer_id=referrer.id, referred_id=user.id,
                   code=referrer.referral_code)
    db.session.add(ref)
    db.session.commit()
    return ref


def _has_paid_enrollment(user_id):
    return (Enrollment.query.filter(
        Enrollment.user_id == user_id,
        Enrollment.paid.is_(True),
        Enrollment.amount_paid > 0,
        Enrollment.status.in_([Enrollment.STATUS_ACTIVE,
                               Enrollment.STATUS_COMPLETED])).count())


def maybe_reward_referral(user):
    """Issue the referrer's reward coupon on the referred user's FIRST paid
    enrollment. Idempotent: one reward per referred user, ever.

    Returns the Coupon issued, or None.
    """
    ref = (Referral.query.filter_by(referred_id=user.id)
           .filter(Referral.status.in_([Referral.STATUS_SIGNED_UP,
                                        Referral.STATUS_ENROLLED])).first())
    if not ref:
        return None
    settings = ReferralSettings.get()
    if not settings.enabled:
        return None
    if _has_paid_enrollment(user.id) != 1:
        # mark enrolled (but not yet rewarded) once they have any paid enrollment
        if ref.status == Referral.STATUS_SIGNED_UP and _has_paid_enrollment(user.id) >= 1:
            ref.status = Referral.STATUS_ENROLLED
            db.session.commit()
        return None
    # First paid enrollment -> issue reward coupon to the referrer
    for _ in range(20):
        code = "REF-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if not Coupon.query.filter_by(code=code).first():
            break
    else:
        return None
    coupon = Coupon(code=code,
                    percent_off=max(1, min(100, settings.reward_percent or 10)),
                    active=True, max_uses=1, used_count=0)
    db.session.add(coupon)
    ref.status = Referral.STATUS_REWARDED
    ref.coupon_code = code
    ref.rewarded_at = datetime.utcnow()
    db.session.commit()
    return coupon


def referrer_stats(referrer_id):
    """Dashboard numbers for one referrer."""
    refs = Referral.query.filter_by(referrer_id=referrer_id).all()
    codes = {r.code for r in refs}
    clicks = 0
    if codes:
        clicks = ReferralClick.query.filter(ReferralClick.code.in_(codes)).count()
    return {
        "clicks": clicks,
        "signups": len(refs),
        "enrollments": len([r for r in refs if r.status in
                            (Referral.STATUS_ENROLLED, Referral.STATUS_REWARDED)]),
        "rewards": len([r for r in refs if r.status == Referral.STATUS_REWARDED]),
        "referrals": sorted(refs, key=lambda r: r.created_at, reverse=True),
    }
