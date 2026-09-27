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
    db.session.add_all([ds, da, py])
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
      ".chat-msg.bot{background:#16294d" in html
      and ".chat-msg.user{background:linear-gradient(135deg,#d4af37,#9c7a1e)" in html)

# ================================================================ summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
