"""Sayyed EdVantage LMS — data models."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db

# ---------------------------------------------------------------- roles
ROLE_ADMIN = "admin"
ROLE_FACULTY = "faculty"
ROLE_STUDENT = "student"
ROLE_MANAGER = "manager"
ROLE_COUNSELLOR = "counsellor"  # Phase 4: admissions/CRM
ROLES = (ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, ROLE_MANAGER, ROLE_COUNSELLOR)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    is_active = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20), default="")  # Phase 3: WhatsApp notifications
    referral_code = db.Column(db.String(20), unique=True, nullable=True,
                              index=True)  # Phase 3: my referral code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship("Enrollment", backref="user", cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    # -- permission helpers ------------------------------------------------
    def is_admin(self):
        return self.role == ROLE_ADMIN

    def is_manager(self):
        return self.role == ROLE_MANAGER

    def can_manage_users(self):
        return self.role == ROLE_ADMIN

    def can_manage_content(self):
        return self.role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_FACULTY)

    def can_manage_course(self, course):
        if self.role in (ROLE_ADMIN, ROLE_MANAGER):
            return True
        return self.role == ROLE_FACULTY and course.instructor_id == self.id


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    short_desc = db.Column(db.String(300), default="")
    description = db.Column(db.Text, default="")  # rich text (HTML)
    fee = db.Column(db.Integer, nullable=False, default=0)  # INR, excl. GST
    is_bonus = db.Column(db.Boolean, default=False)  # value-added / free courses
    banner = db.Column(db.String(160), default="")  # filename under static/img/banners
    theme = db.Column(db.String(40), default="blue")  # accent theme key
    instructor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    instructor = db.relationship("User", foreign_keys=[instructor_id])
    modules = db.relationship("Module", backref="course", cascade="all, delete-orphan",
                              order_by="Module.position")
    assignments = db.relationship("Assignment", backref="course", cascade="all, delete-orphan")
    recordings = db.relationship("Recording", backref="course", cascade="all, delete-orphan")

    @property
    def lessons(self):
        return [l for m in self.modules for l in m.lessons]

    @property
    def quizzes(self):
        return [q for m in self.modules for q in m.quizzes]

    @property
    def average_rating(self):
        from sqlalchemy import func
        from . import db as _db
        avg, n = _db.session.query(func.avg(Review.rating),
                                   func.count(Review.id))\
            .filter(Review.course_id == self.id).first()
        return (round(float(avg), 1) if avg else 0.0), int(n)


class Module(db.Model):
    __tablename__ = "modules"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    position = db.Column(db.Integer, default=0)

    lessons = db.relationship("Lesson", backref="module", cascade="all, delete-orphan",
                              order_by="Lesson.position")
    quizzes = db.relationship("Quiz", backref="module", cascade="all, delete-orphan")


class Lesson(db.Model):
    __tablename__ = "lessons"
    KIND_TEXT = "text"
    KIND_VIDEO = "video"
    KIND_PDF = "pdf"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    position = db.Column(db.Integer, default=0)
    kind = db.Column(db.String(10), default=KIND_TEXT)  # text | video | pdf
    body = db.Column(db.Text, default="")  # rich text / HTML for text lessons
    video_url = db.Column(db.String(500), default="")  # embeddable URL
    pdf_file = db.Column(db.String(260), default="")  # stored filename in uploads/
    available_after_days = db.Column(db.Integer, default=0)  # drip: unlock N days after enrollment

    def unlock_date(self, enrolled_at):
        from datetime import timedelta
        return enrolled_at + timedelta(days=self.available_after_days or 0)


class Recording(db.Model):
    """Saved recorded live-class sessions, per course."""
    __tablename__ = "recordings"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    video_url = db.Column(db.String(500), default="")
    duration_min = db.Column(db.Integer, default=0)
    recorded_on = db.Column(db.Date, nullable=True)


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    status = db.Column(db.String(20), default=STATUS_PENDING)
    paid = db.Column(db.Boolean, default=False)
    amount_paid = db.Column(db.Integer, default=0)  # INR actually paid
    coupon_code = db.Column(db.String(40), default="")
    razorpay_order_id = db.Column(db.String(80), default="")
    razorpay_payment_id = db.Column(db.String(80), default="")
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref="enrollments")
    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_enrollment"),)

    def progress(self):
        lessons = self.course.lessons
        if not lessons:
            return 0
        done = LessonProgress.query.filter(
            LessonProgress.user_id == self.user_id,
            LessonProgress.lesson_id.in_([l.id for l in lessons]),
        ).count()
        return round(100 * done / len(lessons))


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress"),)


class Quiz(db.Model):
    __tablename__ = "quizzes"
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    pass_percent = db.Column(db.Integer, default=60)

    questions = db.relationship("Question", backref="quiz", cascade="all, delete-orphan",
                                order_by="Question.position")


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300), default="")
    option_b = db.Column(db.String(300), default="")
    option_c = db.Column(db.String(300), default="")
    option_d = db.Column(db.String(300), default="")
    correct = db.Column(db.String(1), default="A")  # A|B|C|D
    position = db.Column(db.Integer, default=0)


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz = db.relationship("Quiz", backref="attempts")

    @property
    def percent(self):
        return round(100 * self.score / self.total) if self.total else 0


class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.Date, nullable=True)
    max_marks = db.Column(db.Integer, default=100)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship("Submission", backref="assignment",
                                  cascade="all, delete-orphan")


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_path = db.Column(db.String(260), default="")  # stored filename in uploads/
    note = db.Column(db.Text, default="")
    grade = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    graded_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="submissions")
    __table_args__ = (db.UniqueConstraint("assignment_id", "user_id", name="uq_submission"),)


class Coupon(db.Model):
    __tablename__ = "coupons"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    percent_off = db.Column(db.Integer, default=10)
    active = db.Column(db.Boolean, default=True)
    max_uses = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def discount_for(self, fee):
        if not self.active:
            return 0
        if self.max_uses and self.used_count >= self.max_uses:
            return 0
        return fee * self.percent_off // 100


class Certificate(db.Model):
    __tablename__ = "certificates"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="certificates")
    course = db.relationship("Course", backref="certificates")
    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_certificate"),)


# ---------------------------------------------------------------- Phase 2
class LiveSession(db.Model):
    """Scheduled Jitsi live class for a course."""
    __tablename__ = "live_sessions"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    starts_at = db.Column(db.DateTime, nullable=False)
    duration_min = db.Column(db.Integer, default=60)
    room_name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    recording_url = db.Column(db.String(500), default="")
    sent_reminder = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref(
        "live_sessions", cascade="all, delete-orphan",
        order_by="LiveSession.starts_at"))

    @property
    def ends_at(self):
        from datetime import timedelta
        return self.starts_at + timedelta(minutes=self.duration_min or 60)

    @property
    def join_url(self):
        return f"https://meet.jit.si/{self.room_name}"

    def is_joinable(self, now=None):
        """Joinable from 15 min before start until the session ends."""
        from datetime import timedelta
        now = now or datetime.utcnow()
        return self.starts_at - timedelta(minutes=15) <= now <= self.ends_at

    def is_upcoming(self, now=None):
        now = now or datetime.utcnow()
        return now <= self.ends_at


class Discussion(db.Model):
    __tablename__ = "discussions"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref(
        "discussions", cascade="all, delete-orphan"))
    user = db.relationship("User")
    replies = db.relationship("DiscussionReply", backref="discussion",
                              cascade="all, delete-orphan",
                              order_by="DiscussionReply.created_at")


class DiscussionReply(db.Model):
    __tablename__ = "discussion_replies"
    id = db.Column(db.Integer, primary_key=True)
    discussion_id = db.Column(db.Integer, db.ForeignKey("discussions.id"),
                              nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class Review(db.Model):
    """One rating + text review per user per course (enrolled students only)."""
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1..5
    text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref(
        "reviews", cascade="all, delete-orphan"))
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_review"),)


class Wishlist(db.Model):
    __tablename__ = "wishlist"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course")
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_wishlist"),)


class Announcement(db.Model):
    """Site-wide banner shown on all pages while active."""
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmailSettings(db.Model):
    """Single-row SMTP configuration (id=1)."""
    __tablename__ = "email_settings"
    id = db.Column(db.Integer, primary_key=True)
    smtp_host = db.Column(db.String(160), default="")
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(160), default="")
    smtp_pass = db.Column(db.String(255), default="")
    from_email = db.Column(db.String(160), default="")
    from_name = db.Column(db.String(120), default="Sayyed EdVantage LMS")
    enabled = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        row = cls.query.get(1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row


# ---------------------------------------------------------------- Phase 3
class ReferralSettings(db.Model):
    """Single-row referral program config (id=1)."""
    __tablename__ = "referral_settings"
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    reward_percent = db.Column(db.Integer, default=10)  # discount % on auto-coupon
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        row = cls.query.get(1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row


class ReferralClick(db.Model):
    """One row per (referral code, visitor IP) — duplicate clicks are deduped."""
    __tablename__ = "referral_clicks"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    ip_hash = db.Column(db.String(64), nullable=False)
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("code", "ip_hash", name="uq_click"),)


class Referral(db.Model):
    """Referrer -> referred user attribution. One row per referred user."""
    __tablename__ = "referrals"
    STATUS_SIGNED_UP = "signed_up"
    STATUS_ENROLLED = "enrolled"
    STATUS_REWARDED = "rewarded"
    STATUS_INVALID = "invalid"

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default=STATUS_SIGNED_UP)
    coupon_code = db.Column(db.String(40), default="")  # reward coupon issued
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rewarded_at = db.Column(db.DateTime, nullable=True)

    referrer = db.relationship("User", foreign_keys=[referrer_id])
    referred = db.relationship("User", foreign_keys=[referred_id])
    __table_args__ = (db.UniqueConstraint("referred_id", name="uq_referred"),)


class Job(db.Model):
    """Job board posting (admin/manager). Employer portal deferred to Phase 7."""
    __tablename__ = "jobs"
    TYPE_JOB = "job"
    TYPE_INTERNSHIP = "internship"
    TYPE_APPRENTICESHIP = "apprenticeship"
    TYPES = (TYPE_JOB, TYPE_INTERNSHIP, TYPE_APPRENTICESHIP)

    APPLY_INTERNAL = "internal"
    APPLY_EXTERNAL = "external"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    company = db.Column(db.String(160), nullable=False, default="")
    type = db.Column(db.String(20), default=TYPE_JOB)
    location = db.Column(db.String(160), default="")
    remote = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, default="")
    skills = db.Column(db.String(300), default="")
    deadline = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)
    apply_mode = db.Column(db.String(20), default=APPLY_INTERNAL)
    external_url = db.Column(db.String(500), default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship("JobApplication", backref="job",
                                   cascade="all, delete-orphan",
                                   order_by="JobApplication.applied_at.desc()")

    def is_open(self, today=None):
        from datetime import date
        today = today or date.today()
        if not self.active:
            return False
        return self.deadline is None or self.deadline >= today


class JobApplication(db.Model):
    """Student application to a job. Status pipeline."""
    __tablename__ = "job_applications"
    STATUS_APPLIED = "applied"
    STATUS_SHORTLISTED = "shortlisted"
    STATUS_INTERVIEWED = "interviewed"
    STATUS_OFFERED = "offered"
    STATUS_PLACED = "placed"
    STATUS_REJECTED = "rejected"
    STATUSES = (STATUS_APPLIED, STATUS_SHORTLISTED, STATUS_INTERVIEWED,
                STATUS_OFFERED, STATUS_PLACED, STATUS_REJECTED)

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cover_note = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default=STATUS_APPLIED)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("job_id", "user_id", name="uq_application"),)


class WhatsAppSettings(db.Model):
    """Single-row WhatsApp Cloud API config (id=1). Ships DISABLED."""
    __tablename__ = "whatsapp_settings"
    id = db.Column(db.Integer, primary_key=True)
    phone_number_id = db.Column(db.String(60), default="")
    access_token = db.Column(db.String(255), default="")  # never rendered/logged
    enabled = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        row = cls.query.get(1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row


# ---------------------------------------------------------------- Phase 4: Admissions & CRM
class Lead(db.Model):
    """LMS-internal CRM lead (separate from the standalone CRM service)."""
    __tablename__ = "leads"

    STATUS_NEW = "new"
    STATUS_CONTACTED = "contacted"
    STATUS_QUALIFIED = "qualified"
    STATUS_COUNSELLING = "counselling"
    STATUS_INTERESTED = "interested"
    STATUS_PAYMENT_PENDING = "payment_pending"
    STATUS_ADMITTED = "admitted"
    STATUS_ENROLLED = "enrolled"
    PIPELINE = (STATUS_NEW, STATUS_CONTACTED, STATUS_QUALIFIED,
                STATUS_COUNSELLING, STATUS_INTERESTED, STATUS_PAYMENT_PENDING,
                STATUS_ADMITTED, STATUS_ENROLLED)
    LABELS = {STATUS_NEW: "New", STATUS_CONTACTED: "Contacted",
              STATUS_QUALIFIED: "Qualified", STATUS_COUNSELLING: "Counselling",
              STATUS_INTERESTED: "Interested",
              STATUS_PAYMENT_PENDING: "Payment Pending",
              STATUS_ADMITTED: "Admitted", STATUS_ENROLLED: "Enrolled"}

    SOURCE_WEBSITE = "website"
    SOURCE_WHATSAPP = "whatsapp"
    SOURCE_INSTAGRAM = "instagram"
    SOURCE_FACEBOOK = "facebook"
    SOURCE_REFERRAL = "referral"
    SOURCE_CHAT = "chat"
    SOURCE_MANUAL = "manual"
    SOURCES = (SOURCE_WEBSITE, SOURCE_WHATSAPP, SOURCE_INSTAGRAM,
               SOURCE_FACEBOOK, SOURCE_REFERRAL, SOURCE_CHAT, SOURCE_MANUAL)

    SCORE_HOT = "hot"
    SCORE_WARM = "warm"
    SCORE_COLD = "cold"
    SCORES = (SCORE_HOT, SCORE_WARM, SCORE_COLD)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="")
    phone = db.Column(db.String(20), nullable=False, default="", index=True)
    email = db.Column(db.String(160), default="")
    source = db.Column(db.String(20), default=SOURCE_WEBSITE)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    status = db.Column(db.String(20), default=STATUS_NEW, index=True)
    score = db.Column(db.String(10), default=SCORE_COLD, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    follow_up_date = db.Column(db.Date, nullable=True, index=True)
    converted_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                 nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    course = db.relationship("Course")
    assignee = db.relationship("User", foreign_keys=[assigned_to])
    converted_user = db.relationship("User", foreign_keys=[converted_user_id])
    activities = db.relationship("LeadActivity", backref="lead",
                                 cascade="all, delete-orphan",
                                 order_by="LeadActivity.created_at.desc()")

    @property
    def status_label(self):
        return self.LABELS.get(self.status, self.status)

    def log(self, kind, text, actor_id=None):
        act = LeadActivity(lead_id=self.id, kind=kind, text=text,
                           actor_id=actor_id)
        db.session.add(act)
        return act


class LeadActivity(db.Model):
    """Timeline entry on a lead: status change, note, follow-up, system."""
    __tablename__ = "lead_activities"
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    kind = db.Column(db.String(20), default="note")  # note|status|followup|system
    text = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship("User")


class ApplicationSettings(db.Model):
    """Single-row config for the public application form (id=1)."""
    __tablename__ = "application_settings"
    id = db.Column(db.Integer, primary_key=True)
    enable_education = db.Column(db.Boolean, default=True)
    enable_batch_timing = db.Column(db.Boolean, default=True)
    enable_document = db.Column(db.Boolean, default=True)
    intro_text = db.Column(db.Text, default="Apply for admission to Sayyed EdVantage courses.")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        row = cls.query.get(1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row


class Application(db.Model):
    """Admission application submitted via the public form."""
    __tablename__ = "applications"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False, default="")
    email = db.Column(db.String(160), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    education = db.Column(db.String(200), default="")
    batch_timing = db.Column(db.String(120), default="")
    document_path = db.Column(db.String(260), default="")
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    reject_reason = db.Column(db.Text, default="")
    created_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course")
    created_user = db.relationship("User", foreign_keys=[created_user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


class Batch(db.Model):
    """A batch/cohort of students for a course."""
    __tablename__ = "batches"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    schedule_text = db.Column(db.String(200), default="")
    start_date = db.Column(db.Date, nullable=True)
    capacity = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref(
        "batches", cascade="all, delete-orphan"))
    faculty = db.relationship("User", foreign_keys=[faculty_id])
    members = db.relationship("BatchMember", backref="batch",
                              cascade="all, delete-orphan",
                              order_by="BatchMember.added_at")


class BatchMember(db.Model):
    __tablename__ = "batch_members"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("batch_id", "user_id",
                                         name="uq_batch_member"),)


class OnboardingTask(db.Model):
    """Checkable onboarding item per student."""
    __tablename__ = "onboarding_tasks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    key = db.Column(db.String(40), nullable=False)
    done = db.Column(db.Boolean, default=False)
    done_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint("user_id", "key", name="uq_onboard"),)


class ChatConversation(db.Model):
    """AI sales-agent conversation (anonymous visitors allowed)."""
    __tablename__ = "chat_conversations"
    id = db.Column(db.String(36), primary_key=True)  # uuid hex
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True)
    ip_hash = db.Column(db.String(64), default="")
    fee_asks = db.Column(db.Integer, default=0)  # counts fee questions (intent)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    lead = db.relationship("Lead")
    messages = db.relationship("ChatMessage", backref="conversation",
                               cascade="all, delete-orphan",
                               order_by="ChatMessage.created_at")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(36),
                               db.ForeignKey("chat_conversations.id"),
                               nullable=False)
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    text = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AISettings(db.Model):
    """Single-row AI sales-agent config (id=1)."""
    __tablename__ = "ai_settings"
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    model = db.Column(db.String(60), default="gpt-4o-mini")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        row = cls.query.get(1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row
