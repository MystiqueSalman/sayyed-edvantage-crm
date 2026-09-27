# Sayyed EdVantage LMS — Phase 1 (MVP)

A custom Learning Management System for **Sayyed EdVantage** (Mumbai) — live-class-ready
ed-tech platform with 4 roles, 7 paid courses + free bonus courses, quizzes, assignments,
certificates, coupons and Razorpay payments (stub mode included).

**Stack:** Python 3.12 · Flask 3 · Flask-SQLAlchemy · Flask-Login · SQLite (switchable to
Postgres via `DATABASE_URL`) · reportlab (PDF certificates) · gunicorn.

## Quick start (local)

```bash
cd lms
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env        # optional; defaults work out of the box
./venv/bin/python seed.py   # creates demo users + 7 courses + bonus content
./venv/bin/python run.py    # http://localhost:5000
```

## Demo accounts (seeded)

| Role    | Email                | Password   |
|---------|----------------------|------------|
| Admin   | admin@sayyed.in      | admin123   |
| Manager | manager@sayyed.in    | manager123 |
| Faculty | faculty@sayyed.in    | faculty123 |
| Student | student@sayyed.in    | student123 |

Manager can view/edit all content & records but **not** users, coupons or instructor
assignment. Faculty manages only courses where they are the assigned instructor.

## Environment variables

| Var | Purpose | Default |
|-----|---------|---------|
| `SECRET_KEY` | Flask sessions | `dev-secret-change-me` |
| `DATABASE_URL` | Postgres URL (empty = SQLite) | SQLite `instance/lms.db` |
| `SQLITE_PATH` | Custom SQLite file path | `instance/lms.db` |
| `UPLOAD_DIR` | Assignment submissions, lesson PDFs, certificates | `./uploads` |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Live payments (empty = **stub/test mode**) | stub mode |
| `PORT` | Server port (Railway injects this) | `5000` |
| `APP_BASE_URL` | Public base URL | `http://localhost:5000` |

**Payments:** with no Razorpay keys the app runs in stub mode — checkout creates a fake
order and "Pay" completes instantly so the whole enrollment flow works end-to-end.
Add real keys to take live UPI/card payments (signature verification included).

## Deploy on Railway

1. Push this folder to a GitHub repo (or connect the existing monorepo).
2. Railway → New Project → Deploy from GitHub → select the repo.
3. Add a **Volume** mounted at `/app/data` (SQLite + uploads persist across deploys).
4. Set variables: `SECRET_KEY` (generate one), `DATABASE_URL` empty (or add Postgres
   plugin and set it), `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` when ready.
5. Deploy — the Dockerfile runs `gunicorn` on Railway's `$PORT`.
6. After first deploy, run the seed once: Railway → service → Settings → deploy hook,
   or temporarily run `python seed.py` via the Railway CLI against the volume.

> The Dockerfile sets `SQLITE_PATH=/app/data/lms.db` and `UPLOAD_DIR=/app/data/uploads`
> so everything persists on the mounted volume.

## Project layout

```
lms/
  app/
    __init__.py        # app factory, config, blueprints, error pages
    models.py          # User, Course, Module, Lesson, Recording, Enrollment,
                       # LessonProgress, Quiz, Question, QuizAttempt,
                       # Assignment, Submission, Coupon, Certificate
    routes_auth.py     # login / logout / register
    routes_main.py     # landing, catalog, course detail, recordings,
                       # enroll + Razorpay/stub checkout
    routes_student.py  # dashboard, lessons, quizzes, assignment submit, certificates
    routes_faculty.py  # faculty dashboard
    routes_manage.py   # shared content CRUD (admin/manager/faculty, per-course perms)
    routes_admin.py    # admin dashboard, users, courses, coupons, enrollments
    payments.py        # Razorpay wrapper (live + stub)
    pdfcert.py         # reportlab certificate generator
    decorators.py      # role_required helpers
    templates/         # Jinja2 (dark 3D gold/blue theme)
    static/css/style.css
    static/img/banners/  # AI-generated course-themed banners
  seed.py              # idempotent seed: users, courses, quizzes, assignments, coupons
  run.py               # WSGI entry (gunicorn run:app)
  requirements.txt
  Dockerfile           # Railway-ready, honors $PORT
  .env.example
```

## Phase 2 roadmap (structure is ready)

- **Live classes** — embed Jitsi (`https://meet.jit.si/<room>`) per course; store
  recordings in `Recording` (already supported).
- **Drip scheduling** — add `available_from` on Module/Lesson + gate in `lesson()` route.
- **Email automation** — hook enrollment/quiz events; add a mailer module.
- **Discussion community** — new `Post`/`Reply` models per course.
- **Advanced analytics** — aggregate `QuizAttempt`/`LessonProgress` per cohort.
- **Mobile app** — the Jinja views are responsive; wrap with a PWA manifest or API layer.
- **Migrations** — adopt Alembic/Flask-Migrate (currently `db.create_all()`).
