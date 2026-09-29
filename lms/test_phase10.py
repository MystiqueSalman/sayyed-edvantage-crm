"""Phase 10 — Platform hardening (end-to-end).

Runs against a dev server on http://localhost:5000 with a FRESH DB
(migrated via `flask db upgrade` + seeded), same SQLITE_PATH for server and
this script. Mixes HTTP flows with in-process checks.

Every app-context block re-fetches its rows (never reuse ORM instances
across blocks — the session closes between them).

Coverage: API-key auth (hash storage, scopes, revocation, rate limits,
error envelope), /api/v1 endpoints, HMAC webhook signing + retry +
delivery log, SQLite backup create/download/restore (typed confirmation,
audit entry survives), message templates (render, preview, safe delete),
notification center (real event -> bell -> read), SEO (meta/OG/JSON-LD,
sitemap, robots), monitoring (/health, stats, log tail), developer docs,
blank-chain migration reaching the Phase 10 head.
"""
import hashlib
import hmac as hmac_lib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

BASE = "http://localhost:5000"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app import hardening as H  # noqa: E402
from app.models import (ApiKey, AuditLog, Backup, Certificate, Course,  # noqa: E402
                        Enrollment, MessageTemplate, Notification, Quiz,
                        User, Webhook, WebhookDelivery)

app = create_app()
passed, failed, notes = 0, 0, []


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS {name}")
    else:
        failed += 1
        notes.append(name)
        print(f"  FAIL {name} {detail}")


def login(session, email, password):
    r = session.post(f"{BASE}/login",
                     data={"email": email, "password": password})
    return "Logout" in r.text


def ctx():
    return app.app_context()


s_adm = requests.Session()
s_stu = requests.Session()
assert login(s_adm, "admin@sayyed.in", "admin123"), "admin login failed"
assert login(s_stu, "student@sayyed.in", "student123"), "student login failed"


def issue_key(name, scopes, rate_limit=300):
    """Create an API key via the admin UI; returns (raw_key, key_id)."""
    data = [("name", name), ("rate_limit", str(rate_limit))]
    data += [("scopes", s) for s in scopes]
    r = s_adm.post(f"{BASE}/admin/api-keys", data=data)
    m = re.search(r"se_live_[A-Za-z0-9_\-]+", r.text)
    assert m, f"raw key not shown on issue page: {r.status_code}"
    raw = m.group(0)
    with ctx():
        row = ApiKey.query.filter_by(
            key_hash=hashlib.sha256(raw.encode()).hexdigest()).first()
        kid = row.id if row else None
    return raw, kid


def api_headers(key, use_x_header=False):
    if use_x_header:
        return {"X-API-Key": key}
    return {"Authorization": f"Bearer {key}"}


print("== API key auth ==")
raw_full, kid_full = issue_key("p10-full",
                               ["courses.read", "enrollments.read",
                                "quizzes.read", "leads.read", "leads.write",
                                "batches.read", "payments.read",
                                "certificates.verify"])
raw_limited, kid_limited = issue_key("p10-courses-only", ["courses.read"])
raw_rl, _ = issue_key("p10-ratelimit", ["courses.read"], rate_limit=2)

r = requests.get(f"{BASE}/api/v1/courses")
check("API without key -> 401",
      r.status_code == 401 and r.json()["error"]["code"] == "missing_api_key",
      r.status_code)
r = requests.get(f"{BASE}/api/v1/courses",
                 headers=api_headers("se_live_bogus"))
check("API with bad key -> 401",
      r.status_code == 401 and
      r.json()["error"]["code"] == "invalid_api_key", r.status_code)
r = requests.get(f"{BASE}/api/v1/courses", headers=api_headers(raw_full))
check("API with valid key -> 200 + items",
      r.status_code == 200 and len(r.json().get("items", [])) >= 7,
      r.status_code)
r = requests.get(f"{BASE}/api/v1/courses",
                 headers=api_headers(raw_full, use_x_header=True))
check("X-API-Key header also accepted", r.status_code == 200, r.status_code)
r = requests.get(f"{BASE}/api/v1/leads", headers=api_headers(raw_limited))
check("wrong scope -> 403 insufficient_scope",
      r.status_code == 403 and
      r.json()["error"]["code"] == "insufficient_scope", r.status_code)
check("error envelope shape",
      set(r.json().get("error", {}).keys()) == {"code", "message"})

with ctx():
    row = db.session.get(ApiKey, kid_full)
    check("only hash+prefix stored (no raw key in DB)",
          row is not None and raw_full not in (row.key_hash or "") and
          len(row.key_hash) == 64 and row.key_prefix.startswith("se_live_"))
s_adm.post(f"{BASE}/admin/api-keys/{kid_full}/revoke")
r = requests.get(f"{BASE}/api/v1/courses", headers=api_headers(raw_full))
check("revoked key -> 401", r.status_code == 401, r.status_code)
s_adm.post(f"{BASE}/admin/api-keys/{kid_limited}/delete")
with ctx():
    check("deleted key row gone", db.session.get(ApiKey, kid_limited) is None)

codes = [requests.get(f"{BASE}/api/v1/courses",
                      headers=api_headers(raw_rl)).status_code
         for _ in range(3)]
r_last = requests.get(f"{BASE}/api/v1/courses",
                      headers=api_headers(raw_rl))
check("rate limit 2/min -> 200,200,429", codes == [200, 200, 429], codes)
check("429 carries Retry-After", "Retry-After" in r_last.headers)

# re-issue a full key for the endpoint tests below
raw_full, _ = issue_key("p10-full-2",
                        ["courses.read", "enrollments.read", "quizzes.read",
                         "leads.read", "leads.write", "batches.read",
                         "payments.read", "certificates.verify"])
AH = api_headers(raw_full)

print("== /api/v1 endpoints ==")
r = requests.get(f"{BASE}/api/v1/courses", headers=AH)
items = r.json()["items"]
check("courses list has ≥7 seeded courses", len(items) >= 7, len(items))
cid = items[0]["id"]
r = requests.get(f"{BASE}/api/v1/courses/{cid}", headers=AH)
check("course detail -> 200 with modules/lessons",
      r.status_code == 200 and "modules" in r.json(), r.status_code)
r = requests.get(f"{BASE}/api/v1/courses/999999", headers=AH)
check("course detail 404 envelope",
      r.status_code == 404 and r.json()["error"]["code"] == "not_found",
      r.status_code)
r = requests.get(f"{BASE}/api/v1/enrollments", headers=AH)
check("enrollments list -> 200", r.status_code == 200, r.status_code)
with ctx():
    qz = Quiz.query.first()
    qzid = qz.id if qz else None
r = requests.get(f"{BASE}/api/v1/quizzes/{qzid}/attempts", headers=AH)
check("quiz attempts -> 200", r.status_code == 200, r.status_code)
r = requests.get(f"{BASE}/api/v1/leads", headers=AH)
check("leads list -> 200", r.status_code == 200, r.status_code)
r = requests.post(f"{BASE}/api/v1/leads", headers={**AH,
                  "Content-Type": "application/json"},
                  data=json.dumps({"name": "P10 API Lead",
                                   "phone": "+919100000001",
                                   "email": "p10lead@example.com",
                                   "course_id": cid}))
check("lead create -> 201", r.status_code == 201, r.status_code)
with ctx():
    from app.models import Lead
    check("lead persisted in DB",
          Lead.query.filter_by(phone="+919100000001").count() == 1)
r = requests.post(f"{BASE}/api/v1/leads", headers={**AH,
                  "Content-Type": "application/json"},
                  data=json.dumps({"name": "No Phone"}))
check("lead without phone -> 422",
      r.status_code == 422 and
      r.json()["error"]["code"] == "validation_error", r.status_code)
r = requests.get(f"{BASE}/api/v1/batches", headers=AH)
check("batches list -> 200", r.status_code == 200, r.status_code)
r = requests.get(f"{BASE}/api/v1/payments", headers=AH)
check("payments list -> 200", r.status_code == 200, r.status_code)
with ctx():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    crs = Course.query.get(cid)
    cert = Certificate(user_id=stu.id, course_id=crs.id,
                       code="P10CERT123",
                       issued_at=datetime.utcnow())
    db.session.add(cert)
    db.session.commit()
r = requests.get(f"{BASE}/api/v1/certificates/verify/P10CERT123", headers=AH)
check("certificate verify valid",
      r.status_code == 200 and r.json().get("valid") is True, r.text[:120])
r = requests.get(f"{BASE}/api/v1/certificates/verify/NOPE999", headers=AH)
check("certificate verify invalid -> valid:false",
      r.status_code == 200 and r.json().get("valid") is False, r.text[:120])

print("== webhooks: HMAC + retry + delivery log ==")
secret = "p10hooksecret"
body = b'{"event":"x"}'
sig = H.sign_payload(secret, body)
check("HMAC-SHA256 signature verifies",
      sig == hmac_lib.new(secret.encode(), body,
                           hashlib.sha256).hexdigest() and len(sig) == 64)

# capture server for a successful delivery
captured = {}


class CapHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        captured["body"] = self.rfile.read(n)
        captured["sig"] = self.headers.get("X-SE-Signature")
        captured["event"] = self.headers.get("X-SE-Event")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), CapHandler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

data = [("name", "p10-hook"), ("url", f"http://127.0.0.1:{port}/hook")]
data += [("events", e) for e in ("lead.created", "enrollment.created")]
r = s_adm.post(f"{BASE}/admin/webhooks", data=data)
check("webhook registered via admin", r.status_code in (200, 302),
      r.status_code)
with ctx():
    wh = Webhook.query.filter_by(name="p10-hook").first()
    whid, whsecret = (wh.id, wh.secret) if wh else (None, None)
check("webhook stored with secret + subscribed events",
      whid and whsecret and "lead.created" in (wh.events or []),
      whid)

with ctx():
    n0 = H.dispatch_webhook("lead.created", {"ping": 1}, sync=True)
    time.sleep(0.2)
    d = WebhookDelivery.query.filter_by(
        webhook_id=whid).order_by(WebhookDelivery.id.desc()).first()
    ok_delivery = (d is not None and d.success and d.attempts == 1 and
                   d.status_code == 200)
check("sync dispatch to live URL succeeds, 1 attempt", ok_delivery)
check("signature header verifies against webhook secret",
      captured.get("sig") == H.sign_payload(whsecret, captured.get("body",
                                                                   b""))
      and captured.get("event") == "lead.created")

# dead URL -> 3 attempts, logged failure
data = [("name", "p10-dead-hook"), ("url", "http://127.0.0.1:9/nope"),
        ("events", "lead.created")]
s_adm.post(f"{BASE}/admin/webhooks", data=data)
with ctx():
    dead = Webhook.query.filter_by(name="p10-dead-hook").first()
    deadid = dead.id if dead else None
    t0 = time.time()
    H.dispatch_webhook("lead.created", {"ping": 2}, sync=True)
    elapsed = time.time() - t0
    d = WebhookDelivery.query.filter_by(
        webhook_id=deadid).order_by(WebhookDelivery.id.desc()).first()
check("failed delivery retried 3x and logged",
      d is not None and not d.success and d.attempts == 3 and d.error,
      getattr(d, "attempts", None))
check("backoff happened (elapsed ≥ 3s)", elapsed >= 3, round(elapsed, 1))

# async dispatch from a real event path (lead.created via model hook)
captured.clear()
with ctx():
    wh_live = db.session.get(Webhook, whid)
    assert wh_live.is_active
from app import crm as CRM
with ctx():
    CRM.create_lead(name="P10 Hook Lead", phone="+919100000002",
                    email="p10hook@example.com")
time.sleep(4)
check("async dispatch fired by create_lead event",
      captured.get("event") == "lead.created", captured.get("event"))

r = s_adm.get(f"{BASE}/admin/webhooks/{whid}/deliveries")
check("delivery log page renders", r.status_code == 200 and
      "lead.created" in r.text, r.status_code)
s_adm.post(f"{BASE}/admin/webhooks/{whid}/toggle")
with ctx():
    check("webhook toggled off",
          db.session.get(Webhook, whid).is_active is False)
old_secret = whsecret
s_adm.post(f"{BASE}/admin/webhooks/{whid}/regenerate")
with ctx():
    new_secret = db.session.get(Webhook, whid).secret
check("secret regenerated", new_secret and new_secret != old_secret)
s_adm.post(f"{BASE}/admin/webhooks/{whid}/delete")
with ctx():
    check("webhook deleted",
          db.session.get(Webhook, whid) is None)
s_adm.post(f"{BASE}/admin/webhooks/{deadid}/delete")
srv.shutdown()

print("== backups ==")
r = s_adm.post(f"{BASE}/admin/backups/create")
check("backup created (redirect)", r.status_code in (200, 302),
      r.status_code)
with ctx():
    bkp = Backup.query.order_by(Backup.id.desc()).first()
    bkid = bkp.id if bkp else None
check("backup row recorded", bkid is not None)
with ctx():
    bkp = db.session.get(Backup, bkid)
    fpath = os.path.join(H.backup_dir(), bkp.filename)
check("backup file on disk and valid sqlite",
      os.path.exists(fpath) and H.verify_backup_file(fpath), fpath)
r = s_adm.get(f"{BASE}/admin/backups")
check("backups page lists the file",
      r.status_code == 200 and bkp.filename in r.text, r.status_code)
r = s_adm.get(f"{BASE}/admin/backups/{bkid}/download")
check("backup downloads", r.status_code == 200 and len(r.content) > 10000,
      (r.status_code, len(r.content)))
r = s_adm.post(f"{BASE}/admin/backups",
               data={"retention": "1", "retention_days": "3"})
with ctx():
    check("retention setting saved",
          H.get_setting("backup.retention_days", "7") == "3")
# wrong confirmation must not restore
before = os.path.getmtime(os.environ.get("SQLITE_PATH", ""))
r = s_adm.post(f"{BASE}/admin/backups/{bkid}/restore",
               data={"confirmation": "WRONG"})
after = os.path.getmtime(os.environ.get("SQLITE_PATH", ""))
check("wrong confirmation does not restore", before == after)
r = s_adm.post(f"{BASE}/admin/backups/{bkid}/restore",
               data={"confirmation": "RESTORE"})
check("restore with RESTORE accepted", r.status_code in (200, 302),
      r.status_code)
time.sleep(1)
with ctx():
    a = AuditLog.query.filter_by(
        action="backup.restore").order_by(AuditLog.id.desc()).first()
check("audit entry survives restore in restored DB", a is not None)
r = requests.get(f"{BASE}/")
check("server healthy after restore", r.status_code == 200, r.status_code)

print("== message templates ==")
check("render substitutes known vars",
      H.render_template_string("Hi {{user_name}}!",
                               {"user_name": "Asha"}) == "Hi Asha!")
check("unknown vars render empty (safe)",
      H.render_template_string("Hi {{nope}}!", {}) == "Hi !")
check("no code execution via template",
      H.render_template_string("{{ 7*7 }}", {}) == "")
data = {"name": "P10 Enroll Tpl", "event_key": "enrollment.created",
        "channel": "notification", "subject": "Welcome {{user_name}}!",
        "body": "You joined <b>{{course_title}}</b>."}
r = s_adm.post(f"{BASE}/admin/templates", data=data)
with ctx():
    tpl = MessageTemplate.query.filter_by(name="P10 Enroll Tpl").first()
    tplid = tpl.id if tpl else None
check("template created via admin", tplid is not None)
r = s_adm.get(f"{BASE}/admin/templates/{tplid}/preview")
check("template preview renders sample",
      r.status_code == 200 and "Aarav Sharma" in r.text, r.status_code)
with ctx():
    subj, body, tid = H.render_event_template(
        "enrollment.created", "notification",
        {"user_name": "Zed", "course_title": "Python"},
        "Fallback", "Fallback body")
    check("event render uses template",
          subj == "Welcome Zed!" and tid == tplid, subj)
    check("template use_count bumped",
          db.session.get(MessageTemplate, tplid).use_count >= 1)
# notify() should pick the template up for real events
with ctx():
    stu = User.query.filter_by(email="student@sayyed.in").first()
    stuid = stu.id
    H.notify(stuid, "enrollment.created", "Fallback title",
             context={"user_name": "Stu", "course_title": "DS"})
    n = Notification.query.filter_by(
        user_id=stuid).order_by(Notification.id.desc()).first()
check("notify() renders through template",
      n is not None and n.title == "Welcome Stu!", getattr(n, "title", None))
s_adm.post(f"{BASE}/admin/templates/{tplid}/toggle")
with ctx():
    subj2, _, _ = H.render_event_template(
        "enrollment.created", "notification", {"user_name": "Zed"},
        "FB", "FB")
check("toggled-off template no longer used", subj2 != "Welcome Zed!", subj2)
s_adm.post(f"{BASE}/admin/templates/{tplid}/delete")
with ctx():
    t = db.session.get(MessageTemplate, tplid)
check("used template is deactivated, not deleted",
      t is not None and t.is_active is False)

print("== notification center ==")
with ctx():
    free = Course.query.filter_by(fee=0).first() or Course.query.first()
    slug, freeid = free.slug, free.id
    stu = User.query.filter_by(email="student@sayyed.in").first()
    stuid = stu.id
    n_before = Notification.query.filter_by(user_id=stuid).count()
r = s_stu.post(f"{BASE}/enroll/{slug}", data={"confirm": "yes"})
check("enrollment POST accepted", r.status_code in (200, 302),
      r.status_code)
time.sleep(1)
with ctx():
    n_after = Notification.query.filter_by(user_id=stuid).count()
    n = Notification.query.filter_by(user_id=stuid).order_by(
        Notification.id.desc()).first()
    nid = n.id if n else None
check("real enrollment created a notification", n_after > n_before,
      (n_before, n_after))
r = s_stu.get(f"{BASE}/")
check("navbar bell shows unread count",
      'class="notif-count"' in r.text, r.status_code)
r = s_stu.get(f"{BASE}/notifications")
check("notifications page lists it",
      r.status_code == 200 and "Enrolled in" in r.text, r.status_code)
r = s_stu.post(f"{BASE}/notifications/{nid}/read")
with ctx():
    check("single notification marked read",
          db.session.get(Notification, nid).is_read is True)
s_stu.post(f"{BASE}/notifications/read-all")
with ctx():
    unread = Notification.query.filter_by(
        user_id=stuid, is_read=False).count()
check("mark-all-read clears unread", unread == 0, unread)

print("== SEO ==")
with ctx():
    c = Course.query.get(freeid)
r = s_adm.post(f"{BASE}/admin/courses/{freeid}/edit",
               data={"title": c.title, "slug": c.slug,
                     "short_desc": c.short_desc or "",
                     "description": c.description or "",
                     "fee": c.fee, "is_bonus": "",
                     "meta_title": "P10 Meta Title",
                     "meta_description": "P10 meta description text."})
with ctx():
    c2 = Course.query.get(freeid)
check("meta fields saved on course",
      c2.meta_title == "P10 Meta Title" and
      c2.meta_description == "P10 meta description text.")
r = requests.get(f"{BASE}/course/{slug}")
check("course page has canonical + OG + JSON-LD",
      all(s in r.text for s in (
          'rel="canonical"', 'property="og:title"',
          'application/ld+json', 'name="description"')), r.status_code)
check("meta title used in OG tag",
      "P10 Meta Title" in r.text)
r = requests.get(f"{BASE}/sitemap.xml")
check("sitemap is valid XML with course URL",
      r.status_code == 200 and "<urlset" in r.text and
      f"/course/{slug}" in r.text, r.status_code)
r = requests.get(f"{BASE}/robots.txt")
check("robots.txt points at sitemap",
      r.status_code == 200 and "Sitemap:" in r.text and
      "User-agent:" in r.text, r.status_code)

print("== monitoring + developer docs ==")
r = requests.get(f"{BASE}/health")
hj = r.json()
check("/health 200 with checks",
      r.status_code == 200 and hj.get("status") == "ok" and
      hj["checks"]["db"]["ok"] is True, r.status_code)
r = s_adm.get(f"{BASE}/admin/monitoring")
check("monitoring page renders with stats + log",
      r.status_code == 200 and "Top Endpoints" in r.text and
      "Application Log" in r.text, r.status_code)
r = requests.get(f"{BASE}/developers")
check("developer docs list live endpoints",
      r.status_code == 200 and "/api/v1/courses" in r.text and
      "X-SE-Signature" in r.text and "enrollment.created" in r.text,
      r.status_code)
check("log file exists on disk",
      os.path.exists(H.app_log_path()))

print("== blank-chain migration reaches Phase 10 head ==")
mig_db = "/tmp/p10_migcheck.db"
if os.path.exists(mig_db):
    os.remove(mig_db)
env = dict(os.environ, SQLITE_PATH=mig_db, LMS_SKIP_CREATE_ALL="1",
           LMS_SCHEDULER="off")
pr = subprocess.run([sys.executable, "-m", "flask", "db", "upgrade"],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    env=env, capture_output=True, text=True, timeout=180)
check("flask db upgrade exits 0 on blank DB", pr.returncode == 0,
      pr.stderr[-300:] if pr.returncode else "")
conn = sqlite3.connect(mig_db)
head = conn.execute(
    "SELECT version_num FROM alembic_version").fetchone()[0]
check("migration head is recorded-sessions revision (latest)", head == "f29d3e4a5b6c", head)
tables = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")}
check("Phase 10 tables exist",
      {"api_keys", "webhooks", "webhook_deliveries", "backups",
       "notifications", "message_templates", "app_settings"} <= tables)
cols = [r[1] for r in conn.execute("PRAGMA table_info(courses)")]
check("SEO columns on courses", "meta_title" in cols and
      "meta_description" in cols)
conn.close()

print(f"\n== Phase 10: {passed} passed, {failed} failed ==")
if notes:
    print("FAILURES:", notes)
sys.exit(1 if failed else 0)
