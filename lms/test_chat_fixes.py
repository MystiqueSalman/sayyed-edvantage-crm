"""Regression tests for the 2026-09-27 website-chat bug fixes.

Bug 1: bot must share real module/syllabus outlines (never refuse) and the
       OpenAI prompt must bind "never claim you cannot save numbers".
Bug 2: phone shared mid-conversation must land on the SAME lead that owns the
       conversation, with the "Website chat (...)" transcript entry on it.
Bug 3: chat widget renders a timestamp under each message bubble.

Runs against the Flask test client on a FRESH SQLite DB (no dev server):

    cd ~/workspace/lms && SQLITE_PATH=/tmp/lms_test_chatfixes.db \
        LMS_SCHEDULER=off venv/bin/python test_chat_fixes.py
"""
import os
import sys

os.environ["LMS_SCHEDULER"] = "off"
os.environ.pop("OPENAI_API_KEY", None)  # deterministic rules engine
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_chatfixes.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB

sys.path.insert(0, "/home/hatch/workspace/lms")
from app import create_app, db
from app.models import (ChatConversation, Course, Lead, Lesson, Module)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


app = create_app()
with app.app_context():
    ds = Course(title="Data Science", slug="data-science", fee=50000,
                short_desc="DS course")
    da = Course(title="Data Analytics", slug="data-analytics", fee=40000,
                short_desc="DA course")
    py = Course(title="Python Programming", slug="python-programming",
                fee=35000, short_desc="Python course")  # no modules on purpose
    lx = Course(title="Linux Administration", slug="linux-administration",
                fee=25000, short_desc="Linux course")
    dv = Course(title="DevOps", slug="devops", fee=45000,
                short_desc="DevOps course")
    db.session.add_all([ds, da, py, lx, dv])
    db.session.flush()
    m1 = Module(course_id=ds.id, title="Python for Data Science", position=0)
    m2 = Module(course_id=ds.id, title="Statistics Essentials", position=1)
    db.session.add_all([m1, m2])
    db.session.flush()
    db.session.add_all([
        Lesson(module_id=m1.id, title="Python Basics Refresher", position=0),
        Lesson(module_id=m1.id, title="NumPy Arrays Deep Dive", position=1),
        Lesson(module_id=m2.id, title="Probability Foundations", position=0),
    ])
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


# ================================================================ BUG 1: modules intent
d = chat("share me the data science syllabus")
check("modules intent: real module titles returned",
      "Python for Data Science" in d["reply"] and "Statistics Essentials" in d["reply"],
      d["reply"][:80].replace("\n", " "))
check("modules intent: real lesson titles returned",
      "NumPy Arrays Deep Dive" in d["reply"] and "Probability Foundations" in d["reply"])
check("modules intent: never refuses",
      "don't have the capability" not in d["reply"]
      and "do not have the capability" not in d["reply"].lower())

d = chat("save my number and share me modules")
check("modules intent (no course): lists courses, asks which",
      "syllabus would you like to see" in d["reply"]
      and "Data Science" in d["reply"])
check("modules intent (no course): asks for mobile number",
      "mobile number" in d["reply"])

d = chat("what is the python programming curriculum?")
check("modules intent (no modules in DB): counsellor fallback",
      "counsellor" in d["reply"] and "mobile number" in d["reply"])

d = chat("what will i learn in data science?")
check("modules intent: 'what will i learn' triggers outline",
      "Python for Data Science" in d["reply"])

# direct rules-engine check on the exact reported message
from app.ai_agent import rules_reply, _system_prompt, course_knowledge
with app.app_context():
    reply, flags = rules_reply("save my number and share me modules", None)
check("rules_reply: reported message gets syllabus, not refusal",
      "syllabus would you like to see" in reply and "capability" not in reply)
with app.app_context():
    prompt = _system_prompt(course_knowledge())
check("system prompt: binds never-claim-cannot-save-numbers",
      "NEVER claim you cannot save" in prompt)
check("system prompt: binds never-refuse-modules",
      "NEVER refuse to share module/syllabus" in prompt)
check("system prompt: carries real DB outline",
      "Python for Data Science" in prompt)

# ================================================================ BUG 2: phone -> lead -> transcript chain
d0 = chat("save my number and share me modules")
cid = d0["conversation_id"]
chat("I want to take data analytics admission", cid)
d2 = chat("9967769721", cid)
check("phone reply acknowledges the number", "9967769721" in d2["reply"])
with app.app_context():
    conv = db.session.get(ChatConversation, cid)
    leads = Lead.query.order_by(Lead.id).all()
    phone_leads = [l for l in leads if l.phone == "9967769721"]
    check("exactly one lead owns the phone number", len(phone_leads) == 1,
          f"leads={len(leads)}")
    pl = phone_leads[0] if phone_leads else None
    check("conversation linked to the phone lead",
          pl is not None and conv.lead_id == pl.id,
          f"conv.lead_id={conv.lead_id}")
    check("phone lead timeline has transcript entry",
          pl is not None and any(a.text.startswith("Website chat")
                                 for a in pl.activities))
    if pl:
        entry = next(a.text for a in pl.activities
                     if a.text.startswith("Website chat"))
        check("transcript holds all three visitor messages",
              "save my number and share me modules" in entry
              and "I want to take data analytics admission" in entry
              and "9967769721" in entry)
        check("transcript caps respected",
              len([a for a in pl.activities
                   if a.text.startswith("Website chat")]) == 1
              and len(entry) <= 6000)
        check("phone lead hot + follow-up today",
              pl.score == "hot" and str(pl.follow_up_date) ==
              __import__("datetime").date.today().isoformat())

# dedup edge: number already on another lead -> conversation adopts it
with app.app_context():
    old = Lead(name="Old Lead", phone="9811111111", source="chat")
    db.session.add(old)
    db.session.commit()
d = chat("please call me about fees")
cid2 = d["conversation_id"]
chat("9811111111", cid2)
with app.app_context():
    conv2 = db.session.get(ChatConversation, cid2)
    adopted = db.session.get(Lead, conv2.lead_id)
    check("existing phone lead adopted by conversation",
          adopted is not None and adopted.phone == "9811111111"
          and adopted.name == "Old Lead")
    check("adopted lead got the transcript",
          any(a.text.startswith("Website chat") for a in adopted.activities))
    check("no duplicate lead created for known number",
          Lead.query.filter_by(phone="9811111111").count() == 1)

# ================================================================ BUG 3: timestamps in widget
with open("/home/hatch/workspace/lms/app/templates/base.html") as f:
    html = f.read()
check("widget: timestamp CSS present", ".chat-ts" in html)
check("widget: stamp() renders local time", "toLocaleTimeString" in html)
check("widget: date shown for older messages", "toLocaleDateString" in html)
check("widget: addMsg appends timestamp", 'className = "chat-ts " + who' in html)
check("widget: typing indicator has no timestamp",
      'who.indexOf("typing") === -1' in html)
check("widget: existing gold/blue bubble styling untouched",
      ".chat-msg.bot{background:#ffffff" in html
      and ".chat-msg.user{background:linear-gradient(135deg,#2f7fff,#0b54d6)" in html)

# ================================================================ LEAD ENRICHMENT: course + name capture
with app.app_context():
    DA_ID = Course.query.filter_by(slug="data-analytics").first().id
    PY_ID = Course.query.filter_by(slug="python-programming").first().id
    DS_ID2 = Course.query.filter_by(slug="data-science").first().id
    LX_ID = Course.query.filter_by(slug="linux-administration").first().id

# (1) course question -> lead created carrying the course interest
d = chat("I want data analytics admission")
cid3 = d["conversation_id"]
with app.app_context():
    conv3 = db.session.get(ChatConversation, cid3)
    l3 = db.session.get(Lead, conv3.lead_id)
    check("course question creates a lead", l3 is not None)
    check("lead carries Data Analytics course_id",
          l3 is not None and l3.course_id == DA_ID,
          f"course_id={l3.course_id if l3 else None}")
    check("lead has follow-up date for counsellor",
          l3 is not None and str(l3.follow_up_date) ==
          __import__("datetime").date.today().isoformat())
    check("creation note names the course interest",
          l3 is not None and any("Interested" in a.text and "Data Analytics" in a.text
                                 for a in l3.activities))

# (2) name + phone in one message -> fully-detailed lead
d = chat("Hi, I'm Rahul Sharma, my number is 9876543210")
cid4 = d["conversation_id"]
check("phone reply greets by name (no name ask)",
      "Rahul Sharma" in d["reply"] and "May I have your name" not in d["reply"])
with app.app_context():
    conv4 = db.session.get(ChatConversation, cid4)
    l4 = db.session.get(Lead, conv4.lead_id)
    check("one-message name+phone: real name stored",
          l4 is not None and l4.name == "Rahul Sharma",
          f"name={l4.name if l4 else None}")
    check("one-message name+phone: phone stored",
          l4 is not None and l4.phone == "9876543210")

# (3) name arriving in a later message replaces "Chat visitor"
d = chat("tell me about python")
cid5 = d["conversation_id"]
with app.app_context():
    l5 = db.session.get(Lead, db.session.get(ChatConversation, cid5).lead_id)
    check("course lead starts as Chat visitor",
          l5 is not None and l5.name == "Chat visitor")
chat("my name is Priya", cid5)
with app.app_context():
    l5 = db.session.get(Lead, db.session.get(ChatConversation, cid5).lead_id)
    check("later name updates the placeholder",
          l5 is not None and l5.name == "Priya",
          f"name={l5.name if l5 else None}")
    check("name update logged on timeline",
          l5 is not None and any("Priya" in a.text for a in l5.activities))

# (4) phone-only reply asks for the name
d = chat("9988776655")
check("phone reply asks for name when unknown",
      "May I have your name as well?" in d["reply"])

# (5) course interest follows the visitor across messages
d = chat("tell me about python programming")
cid6 = d["conversation_id"]
chat("tell me about data science", cid6)
with app.app_context():
    l6 = db.session.get(Lead, db.session.get(ChatConversation, cid6).lead_id)
    check("course interest updated to Data Science",
          l6 is not None and l6.course_id == DS_ID2,
          f"course_id={l6.course_id if l6 else None}")
    check("course change logged on timeline",
          l6 is not None and any("Interested course updated" in a.text
                                 for a in l6.activities))

# (6) combo maps to its first component course
d = chat("linux devops combo fees")
cid7 = d["conversation_id"]
with app.app_context():
    l7 = db.session.get(Lead, db.session.get(ChatConversation, cid7).lead_id)
    check("combo interest maps to Linux Administration",
          l7 is not None and l7.course_id == LX_ID,
          f"course_id={l7.course_id if l7 else None}")

# (7) later-stage leads keep the counsellor's course
with app.app_context():
    l8 = Lead(name="Progressed", phone="9722222222", source="chat",
              course_id=PY_ID, status=Lead.STATUS_QUALIFIED)
    db.session.add(l8)
    db.session.commit()
    L8_ID = l8.id
d = chat("tell me about data science")
cid8 = d["conversation_id"]
with app.app_context():
    conv8 = db.session.get(ChatConversation, cid8)
    conv8.lead_id = L8_ID  # simulate counsellor-linked conversation
    db.session.commit()
chat("tell me about data science", cid8)
with app.app_context():
    l8 = db.session.get(Lead, L8_ID)
    check("qualified lead keeps counsellor-set course",
          l8.course_id == PY_ID, f"course_id={l8.course_id}")

# (8) OpenAI prompt binds name capture
with app.app_context():
    prompt = _system_prompt(course_knowledge())
check("system prompt: asks for name with number",
      "ALWAYS ask for the visitor's NAME" in prompt)

# ================================================================ summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
