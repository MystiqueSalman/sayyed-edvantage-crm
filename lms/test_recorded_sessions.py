"""Recorded Sessions tab (Live Classes page).

Covers:
  1. GET /calendar/recorded-sessions is login-required (302 for anonymous).
  2. Student sees only recordings of enrolled courses (not other courses').
  3. Faculty sees only recordings of courses they teach.
  4. Admin/manager see all recordings.
  5. Payload shape: title, course, recorded_on, watch_url (signed), thumbnail,
     notes, linked live_session title; raw video_url is NEVER in the payload.
  6. Faculty can link a recording to a live class (live_edit POST);
     a past session without a linked recording prompts to add one.
  7. recording_new with live_session_id prefill links on create; notes saved.
  8. Recording CRUD (new/delete) still works.
  9. Public /course/<slug>/recordings page still renders.
 10. /calendar page renders both tabs (Upcoming | Recorded Sessions).
 11. Alembic migration f29d3e4a5b6c applies on a fresh DB and adds the new
     columns (live_session_id, notes).
 12. _ensure_schema_patches() is idempotent.

Run: cd ~/workspace/lms && ./run_suite.sh test_recorded_sessions
"""
import os
import re
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta

os.environ["LMS_SCHEDULER"] = "off"
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_recorded_sessions.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "lms-local-test-secret-not-for-production")

sys.path.insert(0, "/home/hatch/workspace/lms")

from app import create_app, db  # noqa: E402
from app.models import (Course, Enrollment, LiveSession, Recording, User,  # noqa: E402
                        ROLE_ADMIN, ROLE_FACULTY, ROLE_STUDENT)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name +
          (f" — {extra}" if extra else ""))


app = create_app()

with app.app_context():
    stu = User(name="RS Student", email="rsstu@example.com", role=ROLE_STUDENT)
    stu.set_password("pw-rs-stu")
    fac1 = User(name="RS Faculty 1", email="rsfac1@example.com",
                role=ROLE_FACULTY)
    fac1.set_password("pw-rs-fac1")
    fac2 = User(name="RS Faculty 2", email="rsfac2@example.com",
                role=ROLE_FACULTY)
    fac2.set_password("pw-rs-fac2")
    adm = User(name="RS Admin", email="rsadm@example.com", role=ROLE_ADMIN)
    adm.set_password("pw-rs-adm")
    db.session.add_all([stu, fac1, fac2, adm])
    db.session.flush()

    course_a = Course(title="RS Course A", slug="rs-course-a", fee=50000,
                      short_desc="A", instructor_id=fac1.id)
    course_b = Course(title="RS Course B", slug="rs-course-b", fee=60000,
                      short_desc="B", instructor_id=fac2.id)
    db.session.add_all([course_a, course_b])
    db.session.flush()

    db.session.add(Enrollment(user_id=stu.id, course_id=course_a.id,
                              status="active", paid=True))
    rec_a1 = Recording(course_id=course_a.id, title="A1: Live Class 3",
                       video_url="https://www.youtube.com/embed/abc123XYZ",
                       duration_min=60, recorded_on=date(2026, 9, 25),
                       notes="Slides: https://example.com/slides-a1")
    rec_a2 = Recording(course_id=course_a.id, title="A2: Doubt Session",
                       video_url="", duration_min=45,
                       recorded_on=date(2026, 9, 20))
    rec_b1 = Recording(course_id=course_b.id, title="B1: Live Class 1",
                       video_url="https://example.com/vid.mp4",
                       duration_min=50, recorded_on=date(2026, 9, 22))
    db.session.add_all([rec_a1, rec_a2, rec_b1])
    past_sess = LiveSession(
        course_id=course_a.id, title="A Live Class 3",
        starts_at=datetime.utcnow() - timedelta(days=4),
        duration_min=60, room_name="se-rs-test-room-1")
    db.session.add(past_sess)
    db.session.commit()
    SESS_ID = past_sess.id
    REC_A1 = rec_a1.id
    REC_B1 = rec_b1.id
    COURSE_A_ID = course_a.id

client = app.test_client()


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


# ================================================== 1. auth required
r = client.get("/calendar/recorded-sessions")
check("anonymous -> redirect to login", r.status_code in (301, 302, 303),
      f"status={r.status_code}")

stu_c, code = login_as("rsstu@example.com", "pw-rs-stu")
check("student login accepted", code in (302, 303), f"status={code}")

# ================================================== 2. student scoping
r = stu_c.get("/calendar/recorded-sessions")
check("student endpoint 200", r.status_code == 200, f"status={r.status_code}")
items = r.get_json() or []
titles = [i["title"] for i in items]
check("student sees enrolled-course recordings",
      "A1: Live Class 3" in titles and "A2: Doubt Session" in titles,
      f"titles={titles}")
check("student does NOT see other course recordings",
      "B1: Live Class 1" not in titles, f"titles={titles}")

a1 = next(i for i in items if i["title"] == "A1: Live Class 3")
check("payload: course name", a1["course"] == "RS Course A",
      f"course={a1['course']!r}")
check("payload: recorded_on iso", a1["recorded_on"] == "2026-09-25",
      f"recorded_on={a1['recorded_on']!r}")
check("payload: signed watch_url (no raw video_url)",
      a1["watch_url"].startswith("/rec/") and "video_url" not in a1,
      f"watch_url={a1['watch_url']!r} keys={sorted(a1.keys())}")
check("payload: youtube thumbnail derived",
      a1["thumbnail"] == "https://img.youtube.com/vi/abc123XYZ/hqdefault.jpg",
      f"thumbnail={a1['thumbnail']!r}")
check("payload: notes", a1["notes"] == "Slides: https://example.com/slides-a1",
      f"notes={a1['notes']!r}")
check("payload: duration", a1["duration_min"] == 60)
a2 = next(i for i in items if i["title"] == "A2: Doubt Session")
check("payload: recording without video has empty watch_url",
      a2["watch_url"] == "" and a2["has_video"] is False,
      f"watch_url={a2['watch_url']!r}")
check("payload: non-youtube video -> no thumbnail", a2["thumbnail"] == "",
      f"thumbnail={a2['thumbnail']!r}")

# ================================================== 3. faculty scoping
fac1_c, _ = login_as("rsfac1@example.com", "pw-rs-fac1")
ftitles = [i["title"] for i in (fac1_c.get(
    "/calendar/recorded-sessions").get_json() or [])]
check("faculty sees managed-course recordings",
      "A1: Live Class 3" in ftitles, f"titles={ftitles}")
check("faculty does NOT see unmanaged-course recordings",
      "B1: Live Class 1" not in ftitles, f"titles={ftitles}")

fac2_c, _ = login_as("rsfac2@example.com", "pw-rs-fac2")
f2titles = [i["title"] for i in (fac2_c.get(
    "/calendar/recorded-sessions").get_json() or [])]
check("faculty2 sees only their course recordings", f2titles == ["B1: Live Class 1"],
      f"titles={f2titles}")

# ================================================== 4. admin sees all
adm_c, _ = login_as("rsadm@example.com", "pw-rs-adm")
atitles = [i["title"] for i in (adm_c.get(
    "/calendar/recorded-sessions").get_json() or [])]
check("admin sees all recordings", len(atitles) == 3, f"titles={atitles}")

# ================================================== 5. calendar page sections (no tab bar)
# (2026-09-29: month-grid calendar removed, then the tab bar removed;
#  page shows ONE hash-routed section at a time: Upcoming list |
#  Recorded batch list | Materials, server-rendered.)
cal = stu_c.get("/calendar")
cal_html = cal.get_data(as_text=True)
check("/calendar 200", cal.status_code == 200, f"status={cal.status_code}")
check("no tab bar markup",
      'rs-tabs' not in cal_html and 'data-tab=' not in cal_html)
check("upcoming section", 'id="sec-upcoming"' in cal_html)
check("recorded section container", 'id="sec-recorded"' in cal_html)
check("no calendar grid markup", 'id="grid"' not in cal_html)
check("materials tab still lazy-loads", "loadMaterials" in cal_html)

# ================================================== 6. link recording to live class
# past session with no linked recording -> suggestion shown
edit_html = adm_c.get(f"/manage/live/{SESS_ID}/edit").get_data(as_text=True)
check("past session edit shows attach-recording hint",
      "This class has ended" in edit_html)
check("past session edit shows recording select",
      'name="attach_recording_id"' in edit_html)

r = adm_c.post(f"/manage/live/{SESS_ID}/edit",
               data={"title": "A Live Class 3",
                     "attach_recording_id": str(REC_A1)},
               follow_redirects=False)
check("live_edit attach POST redirects", r.status_code in (302, 303),
      f"status={r.status_code}")
with app.app_context():
    linked_rec = Recording.query.get(REC_A1)
    check("recording linked to live session",
          linked_rec.live_session_id == SESS_ID,
          f"live_session_id={linked_rec.live_session_id}")
edit_html2 = adm_c.get(f"/manage/live/{SESS_ID}/edit").get_data(as_text=True)
check("linked recording preselected in dropdown",
      f'<option value="{REC_A1}" selected>' in edit_html2)
check("suggestion gone once linked", "This class has ended" not in edit_html2)

items2 = (stu_c.get("/calendar/recorded-sessions").get_json() or [])
a1b = next(i for i in items2 if i["title"] == "A1: Live Class 3")
check("endpoint shows linked live session title",
      a1b["live_session"] == "A Live Class 3",
      f"live_session={a1b['live_session']!r}")

# ================================================== 7. recording_new CRUD + prefill
with app.app_context():
    n0 = Recording.query.count()
r = adm_c.post(f"/manage/course/{COURSE_A_ID}/recording/new",
               data={"title": "A3: New CRUD Rec",
                     "video_url": "https://www.youtube.com/embed/zzz999",
                     "notes": "crud notes", "duration_min": "30",
                     "recorded_on": "2026-09-27",
                     "live_session_id": str(SESS_ID)},
               follow_redirects=False)
check("recording_new POST redirects", r.status_code in (302, 303),
      f"status={r.status_code}")
with app.app_context():
    newrec = Recording.query.filter_by(title="A3: New CRUD Rec").one()
    check("recording created with notes + live link",
          newrec.notes == "crud notes" and newrec.live_session_id == SESS_ID,
          f"notes={newrec.notes!r} live_session_id={newrec.live_session_id}")
    NEW_ID = newrec.id
    check("recording count +1", Recording.query.count() == n0 + 1)

prefill_html = adm_c.get(
    f"/manage/course/{COURSE_A_ID}/recording/new?live_session_id={SESS_ID}"
).get_data(as_text=True)
check("recording_new prefill shows linked session note",
      "Linked to live class" in prefill_html)

r = adm_c.post(f"/manage/recording/{NEW_ID}/delete",
               follow_redirects=False)
check("recording_delete POST redirects", r.status_code in (302, 303),
      f"status={r.status_code}")
with app.app_context():
    check("recording deleted",
          Recording.query.get(NEW_ID) is None and
          Recording.query.count() == n0)

# ================================================== 8. public recordings page locked down
# (approved lockdown: login + enrollment required; public page is teaser-only)
pub = client.get("/course/rs-course-a/recordings", follow_redirects=False)
check("public /course/<slug>/recordings locked down (not 200)",
      pub.status_code in (301, 302, 303, 307, 308, 401, 403),
      f"status={pub.status_code}")

# ================================================== 9. migration applies on fresh DB
MIG_DB = "/tmp/lms_test_rs_migration.db"
if os.path.exists(MIG_DB):
    os.remove(MIG_DB)
menv = dict(os.environ, SQLITE_PATH=MIG_DB, LMS_SKIP_CREATE_ALL="1",
            LMS_SCHEDULER="off",
            SECRET_KEY="lms-local-test-secret-not-for-production")
mp = subprocess.run(
    ["./venv/bin/flask", "db", "upgrade", "head"],
    cwd="/home/hatch/workspace/lms", env=menv,
    capture_output=True, text=True, timeout=180)
check("flask db upgrade head succeeds", mp.returncode == 0,
      (mp.stderr or "")[-300:] if mp.returncode else "")
con = sqlite3.connect(MIG_DB)
cols = {row[1] for row in con.execute("PRAGMA table_info(recordings)")}
tables = {row[0] for row in
          con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
con.close()
check("migration adds recordings.live_session_id", "live_session_id" in cols,
      f"cols={sorted(cols)}")
check("migration adds recordings.notes", "notes" in cols)
check("migration creates course_materials table",
      "course_materials" in tables)
os.path.exists(MIG_DB) and os.remove(MIG_DB)

# ================================================== 10. schema patches idempotent
from app import _ensure_schema_patches  # noqa: E402
try:
    _ensure_schema_patches(app)
    _ensure_schema_patches(app)
    check("_ensure_schema_patches runs twice without error", True)
except Exception as e:  # noqa: BLE001
    check("_ensure_schema_patches runs twice without error", False, str(e)[:200])

# ================================================== 11. course materials
from io import BytesIO  # noqa: E402
from app.models import CourseMaterial  # noqa: E402

MAT_DIR = os.path.join(app.config["UPLOAD_DIR"], "materials")


def upload(client_, course_id, title, filename, payload, desc="",
           session_id=""):
    data = {"title": title, "description": desc,
            "live_session_id": session_id,
            "file": (BytesIO(payload), filename)}
    return client_.post(f"/manage/course/{course_id}/material/new",
                        data=data, content_type="multipart/form-data",
                        follow_redirects=False)


# upload form renders
uf = adm_c.get(f"/manage/course/{COURSE_A_ID}/material/new")
uf_html = uf.get_data(as_text=True)
check("material upload form 200", uf.status_code == 200,
      f"status={uf.status_code}")
check("upload form has file input",
      'type="file" name="file"' in uf_html and
      'enctype="multipart/form-data"' in uf_html)

# faculty (instructor of A) uploads xlsx
with app.app_context():
    m0 = CourseMaterial.query.count()
r = upload(fac1_c, COURSE_A_ID, "W3 Workbook", "workbook.xlsx",
           b"XLSX-BYTES-1", desc="Week 3 practice")
check("xlsx upload accepted (302)", r.status_code in (302, 303),
      f"status={r.status_code}")
with app.app_context():
    mat1 = CourseMaterial.query.filter_by(title="W3 Workbook").one()
    MAT1_ID = mat1.id
    p1 = os.path.join(app.config["UPLOAD_DIR"], mat1.file_path)
    check("material row created with ext/size/desc",
          mat1.file_ext == "xlsx" and mat1.file_size == len(b"XLSX-BYTES-1")
          and mat1.description == "Week 3 practice"
          and mat1.course_id == COURSE_A_ID,
          f"ext={mat1.file_ext} size={mat1.file_size}")
    check("file stored under uploads/materials",
          os.path.isfile(p1) and
          os.path.dirname(os.path.abspath(p1)) == os.path.abspath(MAT_DIR),
          f"path={mat1.file_path}")
    check("stored name is server-generated (no raw filename)",
          os.path.basename(mat1.file_path).startswith("mat_"))

# pdf + pptx accepted
for fname, payload in (("slides.pdf", b"PDF-BYTES"), ("deck.pptx", b"PPTX-B")):
    r = upload(adm_c, COURSE_A_ID, f"file {fname}", fname, payload)
    check(f"{fname.rsplit('.', 1)[1]} upload accepted",
          r.status_code in (302, 303), f"status={r.status_code}")

# exe / sh / no-extension rejected
for bad in ("virus.exe", "run.sh", "noext"):
    with app.app_context():
        n_before = CourseMaterial.query.count()
    r = upload(adm_c, COURSE_A_ID, f"bad {bad}", bad, b"BAD")
    bad_html = r.get_data(as_text=True)
    with app.app_context():
        n_after = CourseMaterial.query.count()
    check(f".{bad.rsplit('.', 1)[-1]} upload rejected",
          r.status_code == 200 and "not allowed" in bad_html
          and n_after == n_before,
          f"status={r.status_code}")

# faculty of another course cannot upload here
r = upload(fac2_c, COURSE_A_ID, "sneaky", "s.pdf", b"S")
check("other-course faculty upload -> 403", r.status_code == 403,
      f"status={r.status_code}")

# student sees only enrolled-course materials
sm = stu_c.get("/calendar/materials")
check("student materials endpoint 200", sm.status_code == 200,
      f"status={sm.status_code}")
smtitles = [m["title"] for m in (sm.get_json() or [])]
check("student sees course A materials",
      "W3 Workbook" in smtitles, f"titles={smtitles}")
# faculty2 uploads to course B -> student must not see it
with app.app_context():
    cb_id = Course.query.filter_by(slug="rs-course-b").one().id
r = upload(fac2_c, cb_id, "B secret notes", "bnotes.pdf", b"BSECRET")
check("course B upload accepted", r.status_code in (302, 303))
smtitles2 = [m["title"] for m in (stu_c.get("/calendar/materials")
                                 .get_json() or [])]
check("student does NOT see course B materials",
      "B secret notes" not in smtitles2, f"titles={smtitles2}")
with app.app_context():
    MATB = CourseMaterial.query.filter_by(title="B secret notes").one().id

# download: enrolled student OK
dl = stu_c.get(f"/materials/{MAT1_ID}/download")
check("enrolled student download 200", dl.status_code == 200,
      f"status={dl.status_code}")
check("downloaded bytes match upload", dl.data == b"XLSX-BYTES-1")
check("download is attachment",
      "attachment" in dl.headers.get("Content-Disposition", ""))

# download: other course blocked, anonymous blocked
dl2 = stu_c.get(f"/materials/{MATB}/download")
check("student cannot download other-course material (404)",
      dl2.status_code == 404, f"status={dl2.status_code}")
dl3 = client.get(f"/materials/{MAT1_ID}/download")
check("anonymous download -> login redirect",
      dl3.status_code in (301, 302, 303), f"status={dl3.status_code}")

# oversized file rejected (101 MB > 100 MB cap -> HTTP 413, no row created)
big = b"0" * (101 * 1024 * 1024)
with app.app_context():
    n_big0 = CourseMaterial.query.count()
r = upload(adm_c, COURSE_A_ID, "too big", "big.pdf", big)
del big
with app.app_context():
    n_big1 = CourseMaterial.query.count()
check("oversized upload rejected",
      r.status_code in (200, 413) and n_big1 == n_big0,
      f"status={r.status_code}")

# path traversal cannot escape the materials dir
r = upload(adm_c, COURSE_A_ID, "evil?", "../../../evil.txt", b"EVIL")
check("traversal filename accepted safely (302)",
      r.status_code in (302, 303), f"status={r.status_code}")
with app.app_context():
    ev = CourseMaterial.query.filter_by(title="evil?").one()
    ev_abs = os.path.abspath(
        os.path.join(app.config["UPLOAD_DIR"], ev.file_path))
    check("traversal file stays inside materials dir",
          os.path.dirname(ev_abs) == os.path.abspath(MAT_DIR)
          and ".." not in ev.file_path and "/" not in
          os.path.basename(ev.file_path),
          f"file_path={ev.file_path}")
    check("no escape file created alongside uploads dir",
          not os.path.exists(
              os.path.join(app.config["UPLOAD_DIR"], "evil.txt")))
    EV_ID = ev.id

# delete removes row + file
with app.app_context():
    ev_path = os.path.join(app.config["UPLOAD_DIR"], ev.file_path)
r = adm_c.post(f"/manage/material/{EV_ID}/delete", follow_redirects=False)
check("material delete redirects", r.status_code in (302, 303),
      f"status={r.status_code}")
with app.app_context():
    check("material row + file deleted",
          CourseMaterial.query.get(EV_ID) is None
          and not os.path.exists(ev_path))

# calendar page: materials section + search
check("materials section present", 'id="sec-materials"' in cal_html)
check("materials search box present", 'id="matSearch"' in cal_html)
check("materials fetch wired", "calendar/materials" in cal_html)

# migration also created the course_materials table (checked on the scratch
# upgrade DB earlier in section 9) — re-verify here via PRAGMA on that path
# (table presence asserted through the model-level tests above on create_all)

# ================================================== 13. signed video security
# Recorded videos are non-downloadable: tab payload carries only signed,
# expiring watch URLs; playback goes through an enrollment-checked stream
# endpoint; the player has nodownload controls; raw URLs never in source.

adm_items = adm_c.get("/calendar/recorded-sessions").get_json() or []
b1 = next(i for i in adm_items if i["title"] == "B1: Live Class 1")
check("mp4 recording has signed watch_url, no raw video_url",
      b1["watch_url"].startswith("/rec/") and "video_url" not in b1,
      f"watch_url={b1['watch_url']!r}")
b1_token = b1["watch_url"].split("/rec/")[1]

# watch page: nodownload player, raw mp4 URL absent from source
r = adm_c.get(b1["watch_url"])
check("watch page 200 for entitled admin", r.status_code == 200,
      f"status={r.status_code}")
check("watch page has nodownload controls",
      'controlsList="nodownload' in r.text)
check("watch page: raw mp4 URL never in source",
      "https://example.com/vid.mp4" not in r.text)
check("watch page: no download link",
      "download" not in r.text.lower().replace("nodownload", ""))

# stream endpoint 302s to storage for external URLs
r = adm_c.get(f"/rec/{b1_token}/stream", follow_redirects=False)
check("stream 302s to stored URL",
      r.status_code == 302 and
      r.headers.get("Location") == "https://example.com/vid.mp4",
      f"status={r.status_code} loc={r.headers.get('Location')!r}")

# youtube recording -> provider iframe in watch page
r = stu_c.get(a1["watch_url"])
check("youtube watch page 200 for enrolled student", r.status_code == 200,
      f"status={r.status_code}")
check("youtube watch page embeds provider player",
      "<iframe" in r.text and "youtube.com/embed/abc123XYZ" in r.text)

# token bound to one user: student's token rejected for admin session
stu_tok = a1["watch_url"].split("/rec/")[1]
r = adm_c.get(f"/rec/{stu_tok}", follow_redirects=False)
check("other user's token -> 403", r.status_code == 403,
      f"status={r.status_code}")
r = adm_c.get(f"/rec/{stu_tok}/stream", follow_redirects=False)
check("other user's stream token -> 403", r.status_code == 403,
      f"status={r.status_code}")

# tampered + malformed tokens rejected
r = adm_c.get(f"/rec/{b1_token[:-3]}XYZ", follow_redirects=False)
check("tampered token -> 403", r.status_code == 403,
      f"status={r.status_code}")
r = adm_c.get("/rec/not-a-token", follow_redirects=False)
check("malformed token -> 403", r.status_code == 403,
      f"status={r.status_code}")

# expired token rejected (minted in-process with negative expiry)
from app.video13 import mint_recording_token
with app.app_context():
    stu_id = User.query.filter_by(email="rsstu@example.com").one().id
    expired_tok = mint_recording_token(REC_A1, stu_id, expiry_hours=-1)
    # enrollment check: student token for a course they are NOT enrolled in
    unenr_tok = mint_recording_token(REC_B1, stu_id)
r = stu_c.get(f"/rec/{expired_tok}", follow_redirects=False)
check("expired token -> 403", r.status_code == 403,
      f"status={r.status_code}")

# enrollment check: student token for a course they are NOT enrolled in
r = stu_c.get(f"/rec/{unenr_tok}", follow_redirects=False)
check("unenrolled student watch -> 403", r.status_code == 403,
      f"status={r.status_code}")
r = stu_c.get(f"/rec/{unenr_tok}/stream", follow_redirects=False)
check("unenrolled student stream -> 403", r.status_code == 403,
      f"status={r.status_code}")

# anonymous -> login redirect
r = client.get(b1["watch_url"], follow_redirects=False)
check("anonymous watch -> login redirect", r.status_code in (301, 302, 303),
      f"status={r.status_code}")

# lesson tokens must NOT validate as recording tokens (namespace separation)
from app.video13 import mint_video_token
with app.app_context():
    lesson_tok = mint_video_token(1, stu_id)
r = stu_c.get(f"/rec/{lesson_tok}", follow_redirects=False)
check("lesson token rejected on recording endpoint", r.status_code == 403,
      f"status={r.status_code}")

# local relative file: served enrollment-checked from the PRIVATE
# recordings dir (outside UPLOAD_DIR and outside Flask static/)
local_rel = "rs_local_test_video.mp4"
local_abs = os.path.join(app.config["RECORDINGS_DIR"], local_rel)
with open(local_abs, "wb") as fh:
    fh.write(b"\x00\x00\x00\x18ftypmp42" + b"V" * 5000)
with app.app_context():
    rec_local = Recording(course_id=COURSE_A_ID, title="Local MP4",
                          video_url=local_rel)
    db.session.add(rec_local)
    db.session.commit()
    local_id = rec_local.id
# mint via the endpoint to get a server-side URL (same SECRET_KEY in tests)
items2 = stu_c.get("/calendar/recorded-sessions").get_json() or []
loc = next(i for i in items2 if i["title"] == "Local MP4")
r = stu_c.get(loc["watch_url"])
check("local-file watch page 200", r.status_code == 200,
      f"status={r.status_code}")
check("local-file watch page uses stream endpoint, no raw path",
      "/stream" in r.text and local_rel not in r.text)
loc_token = loc["watch_url"].split("/rec/")[1]
r = stu_c.get(f"/rec/{loc_token}/stream")
check("local-file stream serves bytes (enrollment-checked)",
      r.status_code == 200 and r.data.startswith(b"\x00\x00\x00\x18ftyp"),
      f"status={r.status_code}")
check("local-file stream is no-store",
      r.headers.get("Cache-Control") == "no-store")
check("local-file stream is inline, not attachment",
      "attachment" not in (r.headers.get("Content-Disposition") or ""))
# HTTP Range -> 206 partial content (seeking works)
r = stu_c.get(f"/rec/{loc_token}/stream", headers={"Range": "bytes=0-99"})
check("range request -> 206 partial content", r.status_code == 206 and
      r.headers.get("Content-Range", "").startswith("bytes 0-99/") and
      len(r.data) == 100,
      f"status={r.status_code} cr={r.headers.get('Content-Range')!r}")
# direct static/uploads paths must NOT reach the private file
r = stu_c.get(f"/files/{local_rel}")
check("direct /files/ path -> 404", r.status_code == 404,
      f"status={r.status_code}")
r = stu_c.get(f"/static/{local_rel}")
check("direct /static/ path -> 404", r.status_code == 404,
      f"status={r.status_code}")
r = client.get(f"/files/{local_rel}")
check("anonymous direct /files/ path blocked", r.status_code in (302, 404),
      f"status={r.status_code}")
# other-course student cannot fetch it even with a valid own token
fac2_c, _ = login_as("rsfac2@example.com", "pw-rs-fac2")
r = fac2_c.get(f"/rec/{loc_token}/stream", follow_redirects=False)
check("other-course faculty stream -> 403", r.status_code == 403,
      f"status={r.status_code}")
# cleanup local file + row
with app.app_context():
    db.session.delete(Recording.query.get(local_id))
    db.session.commit()
os.remove(local_abs)
check("local test file cleaned up", not os.path.exists(local_abs))

# ================================================== summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
