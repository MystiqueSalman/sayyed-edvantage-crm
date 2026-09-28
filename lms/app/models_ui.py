"""UI14 — homepage/student-dashboard redesign support models.

Testimonial + Partner are admin-managed content for the redesigned public
homepage (testimonial carousel, partner logo strip). Site-wide knobs
(hero video URL, contact details, custom stats) reuse the existing
AppSetting key/value store — see _ensure_ui_seeds() below.
"""
from datetime import datetime

from . import db


class Testimonial(db.Model):
    __tablename__ = "testimonials"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(160), default="")      # e.g. "Data Science Student"
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    photo_url = db.Column(db.String(255), default="")
    is_sample = db.Column(db.Boolean, default=False)  # True = clearly-marked sample
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Partner(db.Model):
    __tablename__ = "partners"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    logo_url = db.Column(db.String(255), default="")
    website = db.Column(db.String(255), default="")
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------- site settings keys
SITE_KEYS = [
    "site.hero_video_url",
    "site.contact_phone",
    "site.contact_email",
    "site.stat1_value", "site.stat1_label",
    "site.stat2_value", "site.stat2_label",
    "site.stat3_value", "site.stat3_label",
]

SITE_DEFAULTS = {
    "site.contact_phone": "+91 7977877884",
    "site.contact_email": "sayyededvantage@gmail.com",
}


def _ensure_ui_seeds():
    """Seed UI14 content idempotently. Never breaks startup.

    - Inserts ONE clearly-marked sample testimonial when the table is
      empty, so the homepage carousel has something to render.
    - Partners are seeded with NOTHING (empty on purpose — admin adds real
      partners).
    - Site-setting defaults live in AppSetting; defaults are only *read*
      (never written), so admin edits are never clobbered.
    """
    try:
        from sqlalchemy import inspect as _inspect
        if "testimonials" not in _inspect(db.engine).get_table_names():
            return  # migration hasn't run yet (e.g. mid `flask db upgrade`)
        if Testimonial.query.count() == 0:
            db.session.add(Testimonial(
                name="Sample Student",
                role="Sample — replace in admin",
                text=("This is a sample testimonial. Add real student stories "
                      "in Admin → Testimonials."),
                rating=5,
                is_sample=True,
                active=True,
                sort_order=0,
            ))
            db.session.commit()
    except Exception:
        db.session.rollback()
