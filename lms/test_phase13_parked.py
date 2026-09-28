"""Phase 13 Stream 6: parked pre-launch fixes — website-chat lead persistence.

Covers the hardened /api/chat lead-capture path (app/parked13.py):

  1. FULL flow: course -> name -> phone creates a Lead with correct
     name/phone/course/source='chat', hot score, today's follow-up date,
     linked conversation and a "Website chat" transcript entry.
  2. Duplicate phone: a second conversation sharing the same number updates /
     adopts the existing lead instead of creating a duplicate or erroring.
  3. Invalid phone: no lead, a LeadCaptureLog13 "validate" row, CHAT-LEAD in
     the server logs, reply still 200.
  4. Bogus course_id flag: lead still created (course dropped), "validate"
     row logged.
  5. Forced DB error in the write stage: reply still 200, NO silent loss —
     a LeadCaptureLog13 "write" row AND a CHAT-LEAD exception in the logs.
  6. Forced enrichment error: the lead row SURVIVES (tight write transaction),
     a LeadCaptureLog13 "enrich" row is recorded.
  7. Diagnostics endpoint /admin/diagnostics/chat-leads: anonymous -> login
     redirect, student -> 403, admin -> 200 showing recent chat leads + errors.
  8. LeadCaptureLog13 pruning: rows older than 30 days are pruned on write.

Runs against the Flask test client on a FRESH SQLite DB (no dev server):

    cd ~/workspace/lms && ./run_suite.sh test_phase13_parked
"""
import logging
import os
import sys
from datetime import datetime, timedelta

os.environ["LMS_SCHEDULER"] = "off"
os.environ.pop("OPENAI_API_KEY", None)  # deterministic rules engine
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_phase13_parked.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB

sys.path.insert(0, "/home/hatch/workspace/lms")

# Import BEFORE create_app() so LeadCaptureLog13 is registered with
# SQLAlchemy and the startup db.create_all() creates its table.
import app.parked13 as P13  # noqa: E402
from app import create_app, db  # noqa: E402
from app.models import (ChatConversation, Course, Lead, ROLE_ADMIN,  # noqa: E402
                        ROLE_STUDENT, User)
from app.models13_parked import LeadCaptureLog13, log_capture_error  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


app = create_app()
if "parked13" not in app.blueprints:  # create_app() now registers all Phase 13 blueprints
    app.register_blueprint(P13.parked13_bp)

# Capture server log records so we can assert the CHAT-LEAD prefix.
log_records = []


class _Cap(logging.Handler):
    def emit(self, record):
        log_records.append(record)


app.logger.addHandler(_Cap())
app.logger.setLevel(logging.DEBUG)


def chat_leads_logged(stage=None):
    msgs = [r.getMessage() for r in log_records if "CHAT-LEAD" in r.getMessage()]
    if stage:
        msgs = [m for m in msgs if f"stage={stage}" in m]
    return msgs


with app.app_context():
    ds = Course(title="Data Science", slug="data-science", fee=50000,
                short_desc="DS course")
    db.session.add(ds)
    admin = User(name="T Admin", email="t13admin@example.com", role=ROLE_ADMIN)
    admin.set_password("pw-admin-1")
    stu = User(name="T Student", email="t13student@example.com",
               role=ROLE_STUDENT)
    stu.set_password("pw-student-1")
    db.session.add_all([admin, stu])
    db.session.commit()
    DS_ID = ds.id

client = app.test_client()


def chat(msg, cid=None):
    payload = {"message": msg}
    if cid:
        payload["conversation_id"] = cid
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 200, r.status_code
    return r.get_json()


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


# ================================================== 1. full flow: course -> name -> phone
d = chat("tell me about data science")
cid = d["conversation_id"]
chat("my name is Salman Khan", cid)
d3 = chat("my number is 9876543210", cid)
check("full flow: reply 200 + conversation kept", bool(cid) and d3["conversation_id"] == cid)
with app.app_context():
    conv = db.session.get(ChatConversation, cid)
    lead = db.session.get(Lead, conv.lead_id) if conv and conv.lead_id else None
    check("full flow: lead row exists", lead is not None)
    check("full flow: name captured", lead is not None and lead.name == "Salman Khan",
          f"name={lead.name if lead else None}")
    check("full flow: phone captured", lead is not None and lead.phone == "9876543210")
    check("full flow: course captured", lead is not None and lead.course_id == DS_ID,
          f"course_id={lead.course_id if lead else None}")
    check("full flow: source=website-chat marker", lead is not None and lead.source == "chat",
          f"source={lead.source if lead else None}")
    check("full flow: hot + follow-up today",
          lead is not None and lead.score == "hot"
          and str(lead.follow_up_date) == datetime.utcnow().date().isoformat())
    check("full flow: transcript entry on timeline",
          lead is not None and any(a.text.startswith("Website chat")
                                   for a in lead.activities))
    check("full flow: no capture errors logged", LeadCaptureLog13.query.count() == 0,
          f"errors={LeadCaptureLog13.query.count()}")
LEAD1_ID = lead.id if lead else None

# ================================================== 2. duplicate phone: update, don't duplicate
d = chat("hi, my number is 9876543210")  # brand-new conversation, same number
cid2 = d["conversation_id"]
with app.app_context():
    conv2 = db.session.get(ChatConversation, cid2)
    dupes = Lead.query.filter_by(phone="9876543210").all()
    check("duplicate phone: exactly one lead owns the number", len(dupes) == 1,
          f"count={len(dupes)}")
    check("duplicate phone: conversation adopts the existing lead",
          conv2.lead_id == LEAD1_ID, f"conv.lead_id={conv2.lead_id}")
    check("duplicate phone: original name kept (not overwritten)",
          dupes[0].name == "Salman Khan", f"name={dupes[0].name}")

# placeholder-name lead gets its name updated by a later message
d = chat("my number is 9123456780")
cid3 = d["conversation_id"]
chat("my name is Priya Nair", cid3)
with app.app_context():
    l3 = db.session.get(Lead, db.session.get(ChatConversation, cid3).lead_id)
    check("duplicate flow: placeholder name updated on existing lead",
          l3 is not None and l3.name == "Priya Nair",
          f"name={l3.name if l3 else None}")
    check("duplicate flow: still one lead for the number",
          Lead.query.filter_by(phone="9123456780").count() == 1)

# ================================================== 3. invalid phone -> validate log, no bad number stored
check("normalize: +91 prefix + spaces", P13.normalize_chat_phone("+91 98765 43210") == "9876543210")
check("normalize: leading 0", P13.normalize_chat_phone("09876543210") == "9876543210")
check("normalize: dashes", P13.normalize_chat_phone("987-654-3210") == "9876543210")
check("normalize: too short rejected", P13.normalize_chat_phone("12345") is None)
check("normalize: bad leading digit rejected", P13.normalize_chat_phone("5876543210") is None)
check("normalize: empty rejected", P13.normalize_chat_phone("") is None)
with app.app_context():
    conv3 = ChatConversation(id="t13badphone", ip_hash="x")
    db.session.add(conv3)
    db.session.commit()
    bad_lead = P13.capture_chat_lead(
        conv3, {"phone": "12345", "name": "Bad Phone", "high_intent": True})
    check("invalid phone: bad number never stored on a lead",
          Lead.query.filter_by(phone="12345").count() == 0)
    vrow = (LeadCaptureLog13.query.filter_by(stage="validate")
            .order_by(LeadCaptureLog13.id.desc()).first())
    check("invalid phone: LeadCaptureLog13 validate row", vrow is not None
          and "12345" in (vrow.lead_email_or_phone or ""))
check("invalid phone: CHAT-LEAD in server logs", bool(chat_leads_logged("validate")))

# ================================================== 4. bogus course_id flag -> lead kept, course dropped
with app.app_context():
    conv4 = ChatConversation(id="t13boguscourse", ip_hash="x")
    db.session.add(conv4)
    db.session.commit()
    lead4 = P13.capture_chat_lead(
        conv4, {"phone": "9812345678", "name": "Bogus Course",
                "course_id": 999999, "high_intent": True})
    db.session.refresh(conv4)
    check("bogus course: lead still created",
          lead4 is not None and lead4.phone == "9812345678")
    check("bogus course: course_id dropped, not dangling",
          lead4 is not None and lead4.course_id is None,
          f"course_id={lead4.course_id if lead4 else None}")
    check("bogus course: validate row logged",
          LeadCaptureLog13.query.filter(
              LeadCaptureLog13.stage == "validate",
              LeadCaptureLog13.error.like("%course_id%")).count() >= 1)

# ================================================== 5. forced write-stage DB error
import app.crm as crm_mod
_orig_create = crm_mod.create_lead


def _boom(*a, **k):
    raise RuntimeError("t13 forced write failure")


crm_mod.create_lead = _boom
try:
    with app.app_context():
        n_before = Lead.query.count()
    d = chat("my number is 9000000001")
    check("write failure: reply still 200", d.get("conversation_id"))
    with app.app_context():
        check("write failure: no lead created", Lead.query.count() == n_before)
        wrow = (LeadCaptureLog13.query.filter_by(stage="write")
                .order_by(LeadCaptureLog13.id.desc()).first())
        check("write failure: LeadCaptureLog13 write row",
              wrow is not None and "forced write failure" in (wrow.error or ""))
finally:
    crm_mod.create_lead = _orig_create
check("write failure: CHAT-LEAD exception in server logs",
      any("stage=write" in m and "FAILED" in m for m in chat_leads_logged()))

# ================================================== 6. enrich failure must NOT destroy the lead
_orig_refresh = crm_mod.refresh_score


def _boom2(lead):
    raise RuntimeError("t13 forced enrich failure")


crm_mod.refresh_score = _boom2
try:
    with app.app_context():
        conv6 = ChatConversation(id="t13enrich", ip_hash="x")
        db.session.add(conv6)
        db.session.commit()
        lead6 = P13.capture_chat_lead(
            conv6, {"phone": "9000000002", "name": "Enrich Test",
                    "high_intent": True})
        check("enrich failure: capture_chat_lead returns the lead",
              lead6 is not None)
        kept = (db.session.query(Lead).filter_by(phone="9000000002").one_or_none())
        check("enrich failure: lead row SURVIVES in the DB", kept is not None)
        erow = (LeadCaptureLog13.query.filter_by(stage="enrich")
                .order_by(LeadCaptureLog13.id.desc()).first())
        check("enrich failure: LeadCaptureLog13 enrich row",
              erow is not None and "forced enrich failure" in (erow.error or ""))
finally:
    crm_mod.refresh_score = _orig_refresh
check("enrich failure: CHAT-LEAD exception in server logs",
      any("stage=enrich" in m for m in chat_leads_logged()))

# ================================================== 7. diagnostics endpoint auth
r = client.get("/admin/diagnostics/chat-leads")
check("diagnostics: anonymous redirected to login",
      r.status_code in (301, 302) and "/login" in (r.headers.get("Location") or ""),
      f"status={r.status_code}")
s_stu, _ = login_as("t13student@example.com", "pw-student-1")
r = s_stu.get("/admin/diagnostics/chat-leads")
check("diagnostics: student gets 403", r.status_code == 403,
      f"status={r.status_code}")
s_admin, _ = login_as("t13admin@example.com", "pw-admin-1")
r = s_admin.get("/admin/diagnostics/chat-leads")
body = r.get_data(as_text=True)
check("diagnostics: admin gets 200", r.status_code == 200,
      f"status={r.status_code}")
check("diagnostics: page lists the chat lead phone", "9876543210" in body)
check("diagnostics: page lists capture errors", "forced write failure" in body
      or "validate" in body)

# ================================================== 8. 30-day pruning on write
with app.app_context():
    old = LeadCaptureLog13(stage="write", lead_email_or_phone="old",
                           error="old", payload_summary="old",
                           created_at=datetime.utcnow() - timedelta(days=31))
    db.session.add(old)
    db.session.commit()
    old_id = old.id
    log_capture_error("write", "new", "new", "new")
    check("prune: 31-day-old row pruned on write",
          db.session.get(LeadCaptureLog13, old_id) is None)
    check("prune: fresh row kept",
          LeadCaptureLog13.query.filter_by(lead_email_or_phone="new").count() == 1)

# ================================================== summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
