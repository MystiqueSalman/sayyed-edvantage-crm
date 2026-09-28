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

Manager can view/edit all content & records but **not** users, coupons or instructor
assignment. Faculty manages only courses where they are the assigned instructor.

## Environment variables

| Var | Purpose | Default |
|-----|---------|---------|
| `SECRET_KEY` | Flask sessions **and** TOTP MFA secret encryption key derivation. **Required**: the app refuses to start without it (fail-closed; TOTP secrets are never stored plaintext). Generate a long random string. | *(none — startup error if missing)* |
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

## Phase 10 — Platform hardening (Postgres, API, backups, monitoring)

### Postgres readiness

The app is Postgres-safe: `DATABASE_URL` (accepting `postgres://` or
`postgresql://`) activates Postgres, otherwise it stays on SQLite — the
live deploy keeps working unchanged. All SQLAlchemy usage is portable
(no `datetime('now')`, `strftime()` in SQL, `AUTOINCREMENT`, backticks,
or `PRAGMA` anywhere; migrations use `sa.func.now()` / portable DDL).
The Phase 10 migration (`e10a3f2b8c4d`) runs on both dialects, and
startup `create_all()` + `_ensure_schema_patches()` keeps zero-step
deploys working on either backend.

**Attach Postgres on Railway (when ready):**

1. Railway → project → **+ New → Database → PostgreSQL**.
2. In the LMS service → **Variables** → add `DATABASE_URL` and click
   **Insert → Reference → Postgres → DATABASE_URL** (or paste the
   `postgres://…` connection string).
3. Redeploy. On boot the app runs `create_all()` + schema patches, so
   all tables/columns are created automatically — no manual migration
   step. (Optionally run `flask db upgrade` once for the Alembic
   version stamp.)
4. Migrate existing SQLite data with any standard dump/load tool before
   pointing traffic at Postgres; keep the SQLite file as a rollback
   copy.
5. Notes: SQLite-only features are skipped on Postgres — automated
   `.db` backups (use the Postgres provider's backups instead) and
   one-click restore.

To verify Postgres locally: set
`DATABASE_URL=postgresql://user:pass@localhost:5432/lms` and run
`flask db upgrade` from a blank database — the full chain must reach
head (`e10a3f2b8c4d`) with no errors.

### Backups & recovery (SQLite)

- **Automated:** a daily scheduler (same pattern as the live-class
  reminder thread; disable with `LMS_SCHEDULER=off`) creates a
  timestamped full snapshot under `<data>/backups/` whenever none
  exists in the last 24h. Retention is configurable (default 7) at
  **Admin → Backups**.
- **Manual:** **Admin → Backups → Create Backup Now**; backups are
  downloadable from the same page.
- **Recovery procedure:**
  1. Download the newest good backup (or confirm it on disk).
  2. **Admin → Backups** → pick the backup → type `RESTORE` in the
     confirmation box → **Restore Database**.
  3. The live `lms.db` is atomically replaced; a `backup.restore`
     audit-log entry is written into the restored database.
  4. Reload the admin dashboard and spot-check courses, users and
     enrollments before resuming normal use.
- The scheduler and one-click restore are SQLite-only by design.

### Monitoring

- `GET /health` — JSON with `status`, DB connectivity check, disk-free
  check and uptime (503 when degraded).
- **Admin → Monitoring** — request/error counters per endpoint, recent
  5xx errors, and a tail of the application log (`<data>/logs/app.log`).

### REST API & webhooks

- `GET /api/v1/...` — versioned JSON API with API-key auth (admin
  issues keys at **Admin → API Keys**; keys are stored as SHA-256
  hashes), per-key scopes and per-key rate limits (default 300/min,
  `429` + `Retry-After`). Docs: **/developers**.
- **Admin → Webhooks** — subscribe URLs to `enrollment.created`,
  `payment.completed`, `course.completed`, `certificate.issued`,
  `lead.created`, `quiz.submitted`. Payloads are HMAC-SHA256 signed
  (`X-SE-Signature`); failed deliveries retry 3× with backoff and are
  logged under **📋 Deliveries**.

### Notification center & templates

- Every user gets **/notifications** (bell 🔔 with unread count in the
  navbar). Notifications are generated from real events: enrollment,
  quiz/assignment graded, certificate issued, live-class reminder,
  badge earned, challenge won, application status change.
- **Admin → Templates** — manage `{{variable}}` message templates
  (email / WhatsApp / notification channels) with live preview;
  templates already used are deactivated, never hard-deleted.

### SEO

- Per-course meta title/description (editable on the course edit page),
  canonical URLs, Open Graph tags and JSON-LD `Course` structured data
  on course pages; `/sitemap.xml` + `/robots.txt`.
