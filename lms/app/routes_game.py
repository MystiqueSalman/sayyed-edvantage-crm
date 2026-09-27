"""Phase 8 — student-facing gamification pages (§15).

Achievements hub, challenges list/detail + opt-in. Registered as game_bp.
"""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from . import db
from .decorators import role_required
from .models import (Badge, Challenge, ChallengeEnrollment, UserBadge)

game_bp = Blueprint("game", __name__)

student_only = role_required("student")


def _game_context(user_id):
    from .gamification import get_profile, update_challenges
    profile = get_profile(user_id)
    update_challenges(user_id)  # refresh live progress
    db.session.commit()
    badges = (UserBadge.query.filter_by(user_id=user_id)
              .order_by(UserBadge.awarded_at.desc()).all())
    enrollments = (ChallengeEnrollment.query.filter_by(user_id=user_id)
                   .join(Challenge)
                   .order_by(ChallengeEnrollment.joined_at.desc()).all())
    return {"profile": profile, "badges": badges,
            "enrollments": enrollments}


@game_bp.route("/achievements")
@student_only
def achievements():
    ctx = _game_context(current_user.id)
    return render_template("achievements.html", **ctx)


@game_bp.route("/challenges")
@student_only
def challenge_list():
    from .gamification import update_challenges
    update_challenges(current_user.id)
    db.session.commit()
    live = Challenge.query.filter_by(is_active=True).all()
    live = [c for c in live if c.is_live]
    mine = {e.challenge_id: e for e in ChallengeEnrollment.query.filter_by(
        user_id=current_user.id).all()}
    past = Challenge.query.filter_by(is_active=True).all()
    past = [c for c in past if not c.is_live]
    return render_template("challenges.html", live=live, mine=mine,
                           past=past)


@game_bp.route("/challenges/<int:challenge_id>")
@student_only
def challenge_detail(challenge_id):
    from .gamification import update_challenges
    ch = Challenge.query.get_or_404(challenge_id)
    update_challenges(current_user.id)
    db.session.commit()
    mine = ChallengeEnrollment.query.filter_by(
        challenge_id=ch.id, user_id=current_user.id).first()
    participants = (ChallengeEnrollment.query
                    .filter_by(challenge_id=ch.id)
                    .order_by(ChallengeEnrollment.progress.desc()).all())
    winners = [e for e in participants if e.completed]
    return render_template("challenge_detail.html", ch=ch, mine=mine,
                           participants=participants, winners=winners)


@game_bp.route("/challenges/<int:challenge_id>/join", methods=["POST"])
@student_only
def challenge_join(challenge_id):
    ch = Challenge.query.get_or_404(challenge_id)
    if not ch.is_live:
        flash("This challenge is no longer open.", "warning")
        return redirect(url_for("game.challenge_detail",
                                challenge_id=ch.id))
    existing = ChallengeEnrollment.query.filter_by(
        challenge_id=ch.id, user_id=current_user.id).first()
    if not existing:
        db.session.add(ChallengeEnrollment(challenge_id=ch.id,
                                           user_id=current_user.id))
        db.session.commit()
        flash(f"You're in! 🎯 {ch.title}", "success")
    return redirect(url_for("game.challenge_detail", challenge_id=ch.id))
