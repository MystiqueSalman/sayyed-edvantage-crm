"""Sayyed EdVantage LMS — data models."""
from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import db

# ---------------------------------------------------------------- roles
ROLE_ADMIN = "admin"
ROLE_FACULTY = "faculty"
ROLE_STUDENT = "student"
ROLE_MANAGER = "manager"
ROLE_COUNSELLOR = "counsellor"  # Phase 4: admissions/CRM
ROLE_EMPLOYER = "employer"  # Phase 7: employer portal (job postings)
ROLES = (ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT, ROLE_MANAGER, ROLE_COUNSELLOR,
         ROLE_EMPLOYER)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    is_active = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20), default="")  # Phase 3: WhatsApp notifications
    company = db.Column(db.String(160), default="")  # Phase 7: employer company
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
    ai_tutor_enabled = db.Column(db.Boolean, default=True)  # Phase 5: per-course tutor toggle
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

    def project_performance(self):
        """Phase 6: evaluated project score summary for course analytics."""
        projects = Project.query.filter_by(course_id=self.course_id,
                                           is_active=True).all()
        if not projects:
            return None
        subs = {s.project_id: s for s in ProjectSubmission.query.filter_by(
            user_id=self.user_id).all()}
        evaluated = [subs[p.id] for p in projects
                     if p.id in subs and subs[p.id].status == "evaluated"]
        avg = (round(sum(s.percent for s in evaluated) / len(evaluated), 1)
               if evaluated else None)
        return {"total": len(projects), "submitted": len(subs),
                "evaluated": len(evaluated), "avg_percent": avg}


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
    # Phase 6 — exam settings (§5.3)
    time_limit_min = db.Column(db.Integer, default=0)  # 0 = no limit
    shuffle_questions = db.Column(db.Boolean, default=False)
    shuffle_options = db.Column(db.Boolean, default=False)
    negative_marking = db.Column(db.Float, default=0.0)  # e.g. 0.25 per wrong MCQ
    max_attempts = db.Column(db.Integer, default=0)  # 0 = unlimited
    score_policy = db.Column(db.String(10), default="best")  # best|latest

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
    correct = db.Column(db.String(1), default="A")  # A|B|C|D (mcq_single)
    position = db.Column(db.Integer, default=0)
    # Optional tag linking the question to the lesson it tests, so the AI
    # tutor / weak-topic analysis can point students back to the material.
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=True)
    # Phase 6 — question types & bank (§5.1, §5.2)
    # qtype: mcq_single | mcq_multiple | true_false | fill_blank | matching | descriptive
    qtype = db.Column(db.String(20), default="mcq_single")
    difficulty = db.Column(db.String(10), default="medium")  # easy|medium|hard
    topic = db.Column(db.String(120), default="")
    skills = db.Column(db.String(200), default="")  # comma-separated tags
    marks = db.Column(db.Float, default=1.0)
    is_active = db.Column(db.Boolean, default=True)  # bank deactivation
    # Structured answer payload (JSON) for non-mcq_single types:
    #  mcq_multiple: {"correct": ["A","C"]}
    #  true_false:   {"correct": "true"}        (display via option_a/b)
    #  fill_blank:   {"accepted": ["ans1","ans2"]}
    #  matching:     {"pairs": [["l1","r1"],["l2","r2"]]}
    #  descriptive:  {"model_answer": "..."}     (faculty guidance, optional)
    answer_data = db.Column(db.Text, default="")

    lesson = db.relationship("Lesson")

    @property
    def answer(self):
        """Parsed answer_data dict (never raises)."""
        import json
        try:
            data = json.loads(self.answer_data or "")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @property
    def qtype_label(self):
        return {
            "mcq_single": "MCQ (single answer)",
            "mcq_multiple": "MCQ (multiple answers)",
            "true_false": "True / False",
            "fill_blank": "Fill in the blank",
            "matching": "Matching",
            "descriptive": "Descriptive",
        }.get(self.qtype, self.qtype)

    @property
    def options(self):
        """[(letter, text)] for choice-based types."""
        return [("A", self.option_a or ""), ("B", self.option_b or ""),
                ("C", self.option_c or ""), ("D", self.option_d or "")]


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Float, default=0.0)  # Float: partial credit / negative marking
    total = db.Column(db.Float, default=0.0)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)  # submitted at
    # Phase 6 — exam mode (§5.3)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)  # NULL = in progress
    question_order = db.Column(db.Text, default="[]")  # JSON [question_id...]
    time_expired = db.Column(db.Boolean, default=False)  # auto-submitted by timer
    pending_review = db.Column(db.Boolean, default=False)  # descriptive answers awaiting faculty grading

    quiz = db.relationship("Quiz", backref="attempts")
    user = db.relationship("User", backref="quiz_attempts")

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    @property
    def question_ids_in_order(self):
        import json
        try:
            ids = json.loads(self.question_order or "[]")
            return [int(i) for i in ids if isinstance(i, int)]
        except Exception:
            return []

    @property
    def percent(self):
        return round(100 * (self.score or 0) / self.total) if self.total else 0


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


class Project(db.Model):
    """Phase 6 — project brief posted by faculty per course (§5.5)."""
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    skills = db.Column(db.String(200), default="")  # comma-separated
    deadline = db.Column(db.Date, nullable=True)
    max_marks = db.Column(db.Integer, default=100)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref="projects")
    submissions = db.relationship("ProjectSubmission", backref="project",
                                  cascade="all, delete-orphan")

    @property
    def is_overdue(self):
        return bool(self.deadline and self.deadline < date.today())


class ProjectSubmission(db.Model):
    """Phase 6 — student project submission + faculty evaluation (§5.5)."""
    __tablename__ = "project_submissions"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_url = db.Column(db.String(300), default="")  # GitHub / live link
    file_path = db.Column(db.String(260), default="")  # stored file in uploads/
    notes = db.Column(db.Text, default="")
    # submitted → under_review → evaluated
    status = db.Column(db.String(20), default="submitted")
    marks = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    evaluated_at = db.Column(db.DateTime, nullable=True)
    evaluated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    user = db.relationship("User", foreign_keys="ProjectSubmission.user_id",
                             backref="project_submissions")
    evaluator = db.relationship("User",
                                foreign_keys="ProjectSubmission.evaluated_by")
    __table_args__ = (db.UniqueConstraint("project_id", "user_id",
                                         name="uq_project_submission"),)

    @property
    def percent(self):
        if self.marks is None or not self.project.max_marks:
            return None
        return round(100 * self.marks / self.project.max_marks)


class Coupon(db.Model):
    __tablename__ = "coupons"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    percent_off = db.Column(db.Integer, default=10)
    active = db.Column(db.Boolean, default=True)
    max_uses = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, default=0)
    valid_from = db.Column(db.Date, nullable=True)   # Phase 5: live offer window
    valid_until = db.Column(db.Date, nullable=True)  # Phase 5: live offer window
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_live(self):
        """A coupon the AI may actually quote: active, in date window, uses left."""
        from datetime import date
        if not self.active:
            return False
        today = date.today()
        if self.valid_from and self.valid_from > today:
            return False
        if self.valid_until and self.valid_until < today:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        return True

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
    employer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Phase 7: employer-posted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employer = db.relationship("User", foreign_keys=[employer_id])

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
    employer_note = db.Column(db.Text, default="")  # Phase 7: private employer notes
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
    """Single-row AI config (id=1): sales agent + Phase 5 AI tutor."""
    __tablename__ = "ai_settings"
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    model = db.Column(db.String(60), default="gpt-4o-mini")
    tutor_enabled = db.Column(db.Boolean, default=True)   # Phase 5: AI tutor on/off
    tutor_daily_limit = db.Column(db.Integer, default=30)  # Phase 5: Qs per student/day
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


# ============================================================ Phase 5: AI learning layer

class AITutorExchange(db.Model):
    """Q&A history between an enrolled student and the AI tutor (per course).

    The tutor reads recent exchanges for conversational continuity
    ("you asked about X earlier").
    """
    __tablename__ = "ai_tutor_exchanges"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False, default="")
    cited_lesson_ids = db.Column(db.Text, default="[]")  # JSON list of lesson ids
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AILearningMemory(db.Model):
    """Per-student-per-course learning memory for the AI tutor.

    Weak topics are derived from quiz answers; preferences/summary give the
    tutor continuity. The student can view and clear this at any time.
    """
    __tablename__ = "ai_learning_memory"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    weak_topics = db.Column(db.Text, default="[]")   # JSON: [{lesson_id, misses}]
    preferences = db.Column(db.Text, default="{}")   # JSON dict
    summary = db.Column(db.Text, default="")         # rolling tutor notes
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "course_id",
                                          name="uq_ai_memory"),)


class QuizAnswer(db.Model):
    """Per-question result inside a quiz attempt (powers weak-topic analysis)."""
    __tablename__ = "quiz_answers"
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id"),
                           nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"),
                            nullable=False)
    # Raw student response. mcq_single/true_false: "A".."D"; mcq_multiple:
    # "A,C"; fill_blank: free text; matching: JSON {"left1":"rightX",...};
    # descriptive: free text; "" = skipped.
    chosen = db.Column(db.Text, default="")
    is_correct = db.Column(db.Boolean, default=False)
    # Phase 6 — richer grading (§5.1)
    marks_awarded = db.Column(db.Float, default=0.0)
    needs_review = db.Column(db.Boolean, default=False)  # descriptive, ungraded
    feedback = db.Column(db.Text, default="")  # faculty feedback (descriptive)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    attempt = db.relationship("QuizAttempt", backref=db.backref(
        "answers", cascade="all, delete-orphan"))
    question = db.relationship("Question")


class StudyPlan(db.Model):
    """A dated study plan for one student + course (regenerable)."""
    __tablename__ = "study_plans"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    hours_per_day = db.Column(db.Float, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course")
    items = db.relationship("StudyPlanItem", backref="plan",
                            cascade="all, delete-orphan",
                            order_by="StudyPlanItem.planned_date")
    __table_args__ = (db.UniqueConstraint("user_id", "course_id",
                                          name="uq_study_plan"),)


class StudyPlanItem(db.Model):
    """One planned lesson on one date."""
    __tablename__ = "study_plan_items"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("study_plans.id"),
                        nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"),
                          nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    done = db.Column(db.Boolean, default=False)

    lesson = db.relationship("Lesson")


# ---------------------------------------------------------------- Phase 7: career & placements
class Resume(db.Model):
    """Student resume: editable sections + verified items pulled live.

    Only items backed by real records (enrollments, certificates, evaluated
    projects) are marked verified. Nothing is ever invented.
    """
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                       unique=True)
    headline = db.Column(db.String(160), default="")  # e.g. "Aspiring Data Analyst"
    summary = db.Column(db.Text, default="")
    skills_text = db.Column(db.Text, default="")  # self-added, comma-separated
    experience_json = db.Column(db.Text, default="[]")  # [{title, org, period, details}]
    education_json = db.Column(db.Text, default="[]")  # [{degree, school, year}]
    links_json = db.Column(db.Text, default="{}")  # {github, linkedin, website}
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("resume", uselist=False))

    def experience(self):
        try:
            import json
            return json.loads(self.experience_json or "[]")
        except Exception:
            return []

    def education(self):
        try:
            import json
            return json.loads(self.education_json or "[]")
        except Exception:
            return []

    def links(self):
        try:
            import json
            d = json.loads(self.links_json or "{}")
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def is_complete(self):
        """Counts toward placement readiness: summary + skills + headline."""
        return bool((self.summary or "").strip() and
                    (self.skills_text or "").strip() and
                    (self.headline or "").strip())


class Portfolio(db.Model):
    """Public shareable portfolio page for a student."""
    __tablename__ = "portfolios"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                       unique=True)
    code = db.Column(db.String(24), unique=True, nullable=False, index=True)
    is_public = db.Column(db.Boolean, default=False)
    headline = db.Column(db.String(160), default="")
    about = db.Column(db.Text, default="")
    show_resume = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("portfolio", uselist=False))

    @staticmethod
    def new_code():
        import secrets
        return secrets.token_urlsafe(12)[:16]


class MockInterview(db.Model):
    """One AI mock-interview session for a student."""
    __tablename__ = "mock_interviews"
    STATUS_ACTIVE = "in_progress"
    STATUS_DONE = "completed"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    target_role = db.Column(db.String(160), default="")
    status = db.Column(db.String(20), default=STATUS_ACTIVE)
    score = db.Column(db.Float, nullable=True)  # 0-100 overall, set on completion
    weak_areas = db.Column(db.Text, default="")
    questions_total = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="mock_interviews")
    course = db.relationship("Course")
    qas = db.relationship("MockInterviewQA", backref="session",
                          cascade="all, delete-orphan",
                          order_by="MockInterviewQA.position")

    def answered_count(self):
        return sum(1 for q in self.qas if (q.answer or "").strip())


class MockInterviewQA(db.Model):
    """One question/answer/feedback turn inside a mock interview."""
    __tablename__ = "mock_interview_qas"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("mock_interviews.id"),
                          nullable=False)
    position = db.Column(db.Integer, default=0)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, default="")
    feedback = db.Column(db.Text, default="")
    score = db.Column(db.Float, nullable=True)  # 0-10 per answer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReadinessWeights(db.Model):
    """Single-row (id=1) admin-configurable placement-readiness weights.

    Weights are percentages; they should sum to 100 (normalized if not).
    """
    __tablename__ = "readiness_weights"
    id = db.Column(db.Integer, primary_key=True)
    w_completion = db.Column(db.Float, default=25.0)
    w_quiz = db.Column(db.Float, default=20.0)
    w_projects = db.Column(db.Float, default=15.0)
    w_resume = db.Column(db.Float, default=10.0)
    w_interviews = db.Column(db.Float, default=15.0)
    w_certificates = db.Column(db.Float, default=15.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        row = db.session.get(cls, 1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row

    def as_dict(self):
        return {"completion": self.w_completion, "quiz": self.w_quiz,
                "projects": self.w_projects, "resume": self.w_resume,
                "interviews": self.w_interviews,
                "certificates": self.w_certificates}


# --------------------------------------------------------------------------
# Phase 8 — Gamification & engagement (§15)
# --------------------------------------------------------------------------
class PointSetting(db.Model):
    """Admin-configurable point values per activity (§15.2)."""
    __tablename__ = "point_settings"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(40), unique=True, nullable=False, index=True)
    points = db.Column(db.Integer, default=0)
    label = db.Column(db.String(120), default="")
    counts_for_streak = db.Column(db.Boolean, default=True)


class PointTransaction(db.Model):
    """Audit ledger: every point award, recomputable (§15.2).

    (user_id, action, ref_type, ref_id) is unique so the same activity is
    never double-awarded.
    """
    __tablename__ = "point_transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                       index=True)
    action = db.Column(db.String(40), nullable=False, index=True)
    ref_type = db.Column(db.String(40), default="")
    ref_id = db.Column(db.String(60), default="")
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref="point_transactions")
    __table_args__ = (db.UniqueConstraint(
        "user_id", "action", "ref_type", "ref_id",
        name="uq_point_txn"),)


class GameProfile(db.Model):
    """Denormalized per-student gamification state (§15.2, §15.3)."""
    __tablename__ = "game_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True,
                       nullable=False, index=True)
    points_total = db.Column(db.Integer, default=0)
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_active_date = db.Column(db.Date, nullable=True)

    user = db.relationship("User", backref=db.backref(
        "game_profile", uselist=False, cascade="all, delete-orphan"))


class Badge(db.Model):
    """Badge definition: auto-awarded by the criteria engine (§15.1)."""
    __tablename__ = "badges"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(16), default="🏅")
    description = db.Column(db.String(200), default="")
    criterion = db.Column(db.String(40), nullable=False, index=True)
    threshold = db.Column(db.Float, default=1.0)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                         nullable=True)  # NULL = platform-wide
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # seeded, criteria fixed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course")

    @property
    def scope_label(self):
        return self.course.title if self.course else "Platform-wide"


class UserBadge(db.Model):
    """A badge earned by a student (§15.1)."""
    __tablename__ = "user_badges"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                       index=True)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id"),
                        nullable=False)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="user_badges")
    badge = db.relationship("Badge", backref="awards")
    __table_args__ = (db.UniqueConstraint("user_id", "badge_id",
                                         name="uq_user_badge"),)


class Challenge(db.Model):
    """Time-boxed learning challenge created by faculty/admin (§15.5)."""
    __tablename__ = "challenges"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    criterion = db.Column(db.String(40), nullable=False)  # lessons|quiz_score|points|project|course
    target_json = db.Column(db.Text, default="{}")  # params e.g. {"count": 5}
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"),
                         nullable=True)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=True)
    reward_points = db.Column(db.Integer, default=50)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"),
                          nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course")

    @property
    def target(self):
        import json as _json
        try:
            return _json.loads(self.target_json or "{}")
        except Exception:
            return {}

    @property
    def target_label(self):
        t = self.target
        if self.criterion == "lessons":
            return f"Complete {t.get('count', 0)} lessons"
        if self.criterion == "quiz_score":
            return f"Score {t.get('percent', 0)}%+ on a quiz"
        if self.criterion == "points":
            return f"Earn {t.get('points', 0)} points"
        if self.criterion == "project":
            return "Get a project evaluated"
        if self.criterion == "course":
            return "Complete the course"
        return "Complete the challenge"

    @property
    def is_live(self):
        from datetime import datetime as _dt
        now = _dt.utcnow()
        if not self.is_active or self.starts_at > now:
            return False
        return not self.ends_at or self.ends_at >= now


class ChallengeEnrollment(db.Model):
    """A student's opt-in to a challenge + live progress (§15.5)."""
    __tablename__ = "challenge_enrollments"
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"),
                            nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False,
                       index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress = db.Column(db.Float, default=0.0)  # 0..100
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    challenge = db.relationship("Challenge", backref="enrollments")
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("challenge_id", "user_id",
                                         name="uq_challenge_enroll"),)


class GamificationSetting(db.Model):
    """Single-row (id=1) gamification flags (§15)."""
    __tablename__ = "gamification_settings"
    id = db.Column(db.Integer, primary_key=True)
    backfill_done = db.Column(db.Boolean, default=False)

    @classmethod
    def get(cls):
        row = db.session.get(cls, 1)
        if not row:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row
