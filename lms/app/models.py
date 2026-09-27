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
ROLES = (ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, ROLE_MANAGER)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    is_active = db.Column(db.Boolean, default=True)
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
