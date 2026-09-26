from __future__ import annotations

import base64
import html
import json
import re
import shutil
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LEADS_FILE = DATA_DIR / "leads.json"
BRAND_FILE = ROOT / "sayyed_edvantage_brand.png"

HOST = "127.0.0.1"
PORT = 8000

STATUSES = [
    "New", "Contacted", "Counselling", "Interested",
    "Application", "Payment Pending", "Enrolled", "Lost",
]
PAYMENT_STATUSES = [
    "Not Started", "Quotation Sent", "Payment Pending",
    "Partially Paid", "Paid", "Refunded",
]
SOURCES = [
    "AI Agent", "Website", "Google Ads", "Instagram", "Facebook",
    "YouTube", "WhatsApp", "Referral", "School/College", "Other",
]
COUNSELLING_MODES = ["Phone", "WhatsApp", "Video Call", "In Person", "Email"]
COUNSELLING_OUTCOMES = [
    "Pending", "Interested", "Call Back", "Application",
    "Payment Pending", "Enrolled", "Not Interested", "Lost",
]
FOLLOWUP_OUTCOMES = [
    "Contacted", "No Answer", "Call Back", "Interested",
    "Not Interested", "Application", "Payment Pending", "Enrolled", "Lost",
]
PAYMENT_MODES = ["Cash", "UPI", "Bank Transfer", "Card", "Online", "Other"]

BRAND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 120">
<defs>
<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F7D774"/><stop offset="1" stop-color="#A87518"/></linearGradient>
<linearGradient id="blue" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#56C2FF"/><stop offset="1" stop-color="#1769AA"/></linearGradient>
</defs>
<g transform="translate(8 8)">
<path d="M40 25 L92 7 L144 25 L92 42 Z" fill="#14213D"/>
<path d="M144 25v21" stroke="#D7A93B" stroke-width="4"/>
<circle cx="144" cy="50" r="4" fill="#D7A93B"/>
<text x="35" y="82" font-family="Arial" font-size="68" font-weight="800" fill="url(#gold)">S</text>
<text x="78" y="82" font-family="Arial" font-size="68" font-weight="800" fill="url(#blue)">E</text>
<path d="M37 91 Q92 64 147 91" fill="none" stroke="#56C2FF" stroke-width="5"/>
<path d="M47 94 Q92 76 137 94" fill="none" stroke="#D7A93B" stroke-width="3"/>
</g>
<text x="180" y="54" font-family="Arial" font-size="31" font-weight="800" fill="#D7A93B">SAYYED</text>
<text x="180" y="88" font-family="Arial" font-size="30" font-weight="700" fill="#56C2FF">EdVantage</text>
<text x="180" y="108" font-family="Arial" font-size="10" letter-spacing="2" fill="#FFFFFF">EMPOWERING STUDENTS FOR SUCCESS</text>
</svg>"""

CSS = r"""
:root{--navy:#071a3a;--navy2:#0c2d59;--blue:#1475bd;--blue2:#0b9be8;--gold:#e4b63e;--bg:#eef4fa;--card:#fff;--ink:#14223d;--muted:#66758b;--line:#dbe5ef;--green:#16855b;--red:#c74646;--shadow:0 10px 30px rgba(12,45,89,.09)}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:Inter,Segoe UI,Arial,sans-serif;background:linear-gradient(135deg,#edf3f9,#f8fbfe);color:var(--ink)}
a{text-decoration:none;color:inherit}
.header{background:radial-gradient(circle at 78% 15%,#1f69a1 0,#164f84 30%,#0a244b 70%,#07172f 100%);color:#fff;min-height:190px;padding:22px 42px;display:flex;align-items:center;gap:34px;position:relative;overflow:hidden}
.header:after{content:"";position:absolute;width:480px;height:480px;border:1px solid rgba(255,255,255,.08);border-radius:50%;right:30px;top:-250px;box-shadow:0 0 0 90px rgba(255,255,255,.025),0 0 0 180px rgba(255,255,255,.018)}
.brand-box{width:700px;max-width:52%;display:flex;align-items:center;z-index:1}
.brand-box img{width:100%;max-height:150px;object-fit:contain;object-position:left center}
.brand-fallback{display:flex;align-items:center;gap:15px}
.brand-fallback .se{font-size:54px;font-weight:900;color:#f1c44d}
.brand-fallback .name{font-size:30px;font-weight:900}
.brand-fallback .name span{color:#40b7ff}
.hero-copy{border-left:1px solid rgba(255,255,255,.28);padding-left:32px;z-index:1}
.kicker{color:#f3c648;font-size:14px;letter-spacing:4px;font-weight:800}
.hero-copy h1{font-size:38px;margin:8px 0 7px}
.hero-copy p{margin:0;color:#d8e3f1;font-size:17px}
.nav{background:#fff;border-bottom:1px solid var(--line);display:flex;gap:12px;padding:13px 42px;position:sticky;top:0;z-index:10;box-shadow:0 3px 15px rgba(0,0,0,.04)}
.nav a{padding:13px 22px;border-radius:12px;color:#1268aa;font-weight:800}
.nav a.active{background:linear-gradient(135deg,#0d315d,#1979bc);color:#fff;box-shadow:0 8px 18px rgba(18,104,170,.22)}
main{max-width:1680px;margin:auto;padding:28px 40px 60px}
.notice{background:#eaf8f1;color:#146a49;border:1px solid #b9e4cf;border-radius:12px;padding:12px 15px;margin-bottom:18px;font-weight:700}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
.card,.panel{background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow)}
.card{padding:22px;min-height:120px;position:relative;overflow:hidden}
.card:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:linear-gradient(#e8c64c,#187dc0)}
.label{color:#68788d;font-size:13px;font-weight:800;letter-spacing:.6px;text-transform:uppercase}
.value{font-size:30px;font-weight:900;margin-top:12px}
.sub{color:var(--muted);font-size:13px;margin-top:7px}
.panel{padding:22px;margin-top:20px}
.panel h2,.panel h3{margin:0 0 16px}
.toolbar{display:grid;grid-template-columns:2fr repeat(4,1fr) auto;gap:10px}
input,select,textarea{width:100%;border:1px solid #d3dfeb;background:#fff;border-radius:11px;padding:12px 13px;font:inherit;color:var(--ink);outline:none}
input:focus,select:focus,textarea:focus{border-color:#1682c8;box-shadow:0 0 0 3px rgba(22,130,200,.1)}
textarea{min-height:105px;resize:vertical}
button,.btn{border:0;border-radius:11px;padding:12px 18px;background:linear-gradient(135deg,#0d5f9d,#1388ce);color:#fff;font-weight:800;cursor:pointer;display:inline-block}
.btn.secondary{background:#eef4f9;color:#155f95}
.btn.danger{background:#c74646}
.tablewrap{overflow:auto}
table{width:100%;border-collapse:collapse;min-width:900px}
th{background:#f3f7fb;color:#62738a;text-transform:uppercase;font-size:11px;letter-spacing:.5px;text-align:left}
th,td{padding:13px;border-bottom:1px solid #e7edf3;vertical-align:top}
tr:hover td{background:#fafcff}
.badge{display:inline-flex;padding:6px 10px;border-radius:999px;background:#eaf3fb;color:#1266a5;font-size:12px;font-weight:800}
.badge.green{background:#eaf8f1;color:#16805a}.badge.red{background:#fdeeee;color:#b33f3f}.badge.gold{background:#fff7dc;color:#916c0b}
.section-title{display:flex;justify-content:space-between;gap:15px;align-items:center}
.pipeline{display:grid;gap:8px}
.pipeline a{display:flex;justify-content:space-between;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:#fbfdff}
.pipeline a:hover{border-color:#6db3df}
.form-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.form-grid .full{grid-column:1/-1}
.field label{display:block;font-size:12px;font-weight:800;color:#5e6e84;margin-bottom:6px}
.actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:16px}
.muted{color:var(--muted)}
.timeline{border-left:2px solid #dce8f2;margin-left:8px;padding-left:20px}
.event{position:relative;padding:0 0 18px}
.event:before{content:"";position:absolute;width:9px;height:9px;border-radius:50%;background:#1681c5;left:-26px;top:5px}
.statrow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.statmini{padding:15px;border-radius:12px;background:#f5f9fc;border:1px solid var(--line)}
.money{font-weight:900}
@media(max-width:1100px){.grid4{grid-template-columns:repeat(2,1fr)}.toolbar{grid-template-columns:repeat(2,1fr)}.brand-box{max-width:45%}.hero-copy h1{font-size:30px}}
@media(max-width:700px){.header{padding:18px;min-height:250px;display:block}.brand-box{max-width:100%;width:100%;height:110px}.hero-copy{border-left:0;border-top:1px solid rgba(255,255,255,.25);padding:15px 0}.grid4,.grid3,.grid2,.form-grid,.toolbar,.statrow{grid-template-columns:1fr}.nav{padding:9px 12px;overflow:auto}main{padding:18px}.hero-copy h1{font-size:25px}.brand-box img{max-height:105px}}
"""

def esc(v):
    return html.escape("" if v is None else str(v))

def dec(v):
    try:
        return Decimal(str(v or "0").replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")

def money(v):
    return f"{dec(v):,.2f}"

def now():
    return datetime.now().isoformat(timespec="seconds")

def today():
    return date.today().isoformat()

def valid_date(v):
    if not str(v or "").strip(): return True
    try: datetime.strptime(str(v), "%Y-%m-%d"); return True
    except ValueError: return False

def valid_time(v):
    if not str(v or "").strip(): return True
    try: datetime.strptime(str(v), "%H:%M"); return True
    except ValueError: return False

def ensure_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not LEADS_FILE.exists():
        LEADS_FILE.write_text("{}", encoding="utf-8")
        return
    try:
        obj = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError
    except Exception:
        bad = LEADS_FILE.with_name("leads_invalid_backup.json")
        try: shutil.copy2(LEADS_FILE, bad)
        except Exception: pass
        LEADS_FILE.write_text("{}", encoding="utf-8")

def load():
    ensure_data()
    try:
        obj = json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def save(obj):
    ensure_data()
    tmp = LEADS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LEADS_FILE)

def all_leads():
    return [x for x in load().values() if isinstance(x, dict)]

def get_lead(lid):
    return load().get(lid)

def history(lead, key):
    value = lead.get(key, [])
    if not isinstance(value, list):
        value = []
        lead[key] = value
    return value

def option_list(values, selected=""):
    return "".join(
        f'<option value="{esc(v)}" {"selected" if str(v).lower()==str(selected).lower() else ""}>{esc(v)}</option>'
        for v in values
    )

def find_logo():
    if BRAND_FILE.exists():
        return BRAND_FILE
    candidates = sorted(ROOT.glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True)
    pattern = re.compile(r'BRAND_LOGO_PNG_B64\s*=\s*["\']([^"\']+)["\']', re.S)
    for p in candidates:
        if p.name == Path(__file__).name:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            m = pattern.search(text)
            if m and len(m.group(1)) > 1000:
                data = base64.b64decode(m.group(1))
                if data.startswith(b"\x89PNG"):
                    BRAND_FILE.write_bytes(data)
                    return BRAND_FILE
        except Exception:
            pass
    return None

def logo_html():
    logo = find_logo()
    if logo:
        return '<img src="/brand-logo" alt="Sayyed EdVantage">'
    return '<div class="brand-fallback"><div class="se">SE</div><div class="name">SAYYED <span>EdVantage</span><small style="display:block;font-size:10px;letter-spacing:2px;color:#fff">EMPOWERING STUDENTS FOR SUCCESS</small></div></div>'

def page(title, active, body):
    nav = [
        ("dashboard", "/", "Lead Manager"),
        ("counselling", "/counselling", "Counselling Manager"),
        ("followups", "/follow-ups", "Follow-up Manager"),
    ]
    links = "".join(
        f'<a class="{"active" if k==active else ""}" href="{u}">{esc(t)}</a>'
        for k,u,t in nav
    )
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Sayyed EdVantage</title><style>{CSS}</style></head><body>
<header class="header"><div class="brand-box">{logo_html()}</div>
<div class="hero-copy"><div class="kicker">ADMISSIONS • CRM • AI SALES</div>
<h1>Admissions Command Center</h1><p>Manage leads, counselling, follow-ups, payments and admissions.</p></div></header>
<nav class="nav">{links}</nav><main>{body}</main></body></html>"""

def follow_state(l):
    d = str(l.get("follow_up_date","")).strip()
    if not d: return "none"
    if d < today(): return "overdue"
    if d == today(): return "today"
    return "upcoming"

def dashboard(params):
    leads = all_leads()
    q = params.get("q",[""])[0].strip().lower()
    status = params.get("status",[""])[0]
    country = params.get("country",[""])[0]
    course = params.get("course",[""])[0]
    filtered=[]
    for l in leads:
        hay=" ".join(str(l.get(k,"")) for k in ("lead_id","name","phone","email","country","course_interest","education","source","assigned_counsellor","follow_up_notes")).lower()
        if q and q not in hay: continue
        if status and str(l.get("status","")) != status: continue
        if country and str(l.get("country","")) != country: continue
        if course and course.lower() not in str(l.get("course_interest","")).lower(): continue
        filtered.append(l)
    counts={s:0 for s in STATUSES}
    total_fee=Decimal("0"); total_paid=Decimal("0"); total_bal=Decimal("0")
    for l in leads:
        st=str(l.get("status","New")); counts[st]=counts.get(st,0)+1
        total_fee += dec(l.get("final_fee"))
        total_paid += dec(l.get("total_paid"))
        total_bal += dec(l.get("balance_amount"))
    today_count=sum(1 for l in leads if follow_state(l)=="today")
    overdue=sum(1 for l in leads if follow_state(l)=="overdue")
    upcoming=sum(1 for l in leads if follow_state(l)=="upcoming")
    enrolled=counts.get("Enrolled",0)
    conversion=(enrolled/len(leads)*100) if leads else 0
    cards=[
        ("TOTAL LEADS",len(leads),"All admission enquiries"),
        ("NEW",counts.get("New",0),"Fresh leads"),
        ("INTERESTED",counts.get("Interested",0),"High-intent students"),
        ("ENROLLED",enrolled,"Successful admissions"),
        ("FOLLOW-UPS TODAY",today_count,"Scheduled today"),
        ("OVERDUE",overdue,"Needs attention"),
        ("UPCOMING",upcoming,"Future follow-ups"),
        ("CONVERSION",f"{conversion:.1f}%","Enrolled / total leads"),
        ("TOTAL FINAL FEES",money(total_fee),"Configured final fees"),
        ("TOTAL COLLECTED",money(total_paid),"Payments received"),
        ("TOTAL OUTSTANDING",money(total_bal),"Remaining balance"),
    ]
    card_html="".join(f'<div class="card"><div class="label">{a}</div><div class="value">{b}</div><div class="sub">{c}</div></div>' for a,b,c in cards)
    countries=sorted({str(l.get("country","")).strip() for l in leads if str(l.get("country","")).strip()}, key=str.lower)
    courses=sorted({str(l.get("course_interest","")).strip() for l in leads if str(l.get("course_interest","")).strip()}, key=str.lower)
    rows=[]
    for l in filtered:
        lid=str(l.get("lead_id",""))
        rows.append(f"""<tr><td><b>{esc(lid)}</b></td><td><b>{esc(l.get("name"))}</b><br><small>{esc(l.get("phone"))}</small></td>
<td>{esc(l.get("country"))}<br><small>{esc(l.get("course_interest"))}</small></td>
<td><span class="badge">{esc(l.get("status","New"))}</span></td><td>{esc(l.get("payment_status","Not Started"))}</td>
<td>{esc(l.get("assigned_counsellor")) or "—"}</td><td>{esc(l.get("follow_up_date")) or "—"} {esc(l.get("follow_up_time"))}</td>
<td><a class="btn secondary" href="/lead?id={esc(lid)}">Open</a></td></tr>""")
    pipeline="".join(f'<a href="/?{urlencode({"status":s})}"><span>{esc(s)}</span><b>{counts.get(s,0)}</b></a>' for s in STATUSES)
    body=f"""<div class="grid4">{card_html}</div>
<section class="panel"><div class="section-title"><h2>Lead Search & Filters</h2><span class="muted">{len(filtered)} of {len(leads)} leads</span></div>
<form class="toolbar" method="get"><input name="q" value="{esc(params.get("q",[""])[0])}" placeholder="Search student, lead ID, phone, course...">
<select name="status"><option value="">All statuses</option>{option_list(STATUSES,status)}</select>
<select name="country"><option value="">All countries</option>{option_list(countries,country)}</select>
<select name="course"><option value="">All courses</option>{option_list(courses,course)}</select>
<button>Search</button><a class="btn secondary" href="/">Clear</a></form></section>
<div class="grid2"><section class="panel"><h2>Admission Pipeline</h2><div class="pipeline"><a href="/"><span>All Leads</span><b>{len(leads)}</b></a>{pipeline}</div></section>
<section class="panel"><h2>Quick Actions</h2><div class="actions"><a class="btn" href="/counselling">Open Counselling</a><a class="btn" href="/follow-ups">Open Follow-ups</a></div><p class="muted">All pages use the same admissions data and shared branding.</p></section></div>
<section class="panel"><div class="section-title"><h2>Lead Manager</h2><span class="muted">Live CRM records</span></div>
<div class="tablewrap"><table><thead><tr><th>Lead ID</th><th>Student</th><th>Country / Course</th><th>Status</th><th>Payment</th><th>Counsellor</th><th>Follow-up</th><th>Action</th></tr></thead><tbody>
{''.join(rows) or '<tr><td colspan="8" class="muted">No leads match the current filters.</td></tr>'}</tbody></table></div></section>"""
    return page("Lead Manager","dashboard",body)

def counselling_page(params):
    leads=all_leads(); q=params.get("q",[""])[0].strip().lower(); co=params.get("counsellor",[""])[0]; out=params.get("outcome",[""])[0]; df=params.get("date",[""])[0]
    sessions=[]
    for l in leads:
        for s in history(l,"counselling_history"):
            if not isinstance(s,dict): continue
            x=dict(s); x["_lead_id"]=l.get("lead_id",""); x["_name"]=l.get("name",""); x["_phone"]=l.get("phone",""); x["_course"]=l.get("course_interest","")
            hay=" ".join(str(x.get(k,"")) for k in ("_lead_id","_name","_phone","_course","counsellor","mode","outcome","notes")).lower()
            if q and q not in hay: continue
            if co and str(x.get("counsellor","")) != co: continue
            if out and str(x.get("outcome","")) != out: continue
            if df and str(x.get("counselling_date","")) != df: continue
            sessions.append(x)
    sessions.sort(key=lambda x:(str(x.get("counselling_date","")),str(x.get("counselling_time",""))),reverse=True)
    today_n=sum(1 for s in sessions if s.get("counselling_date")==today())
    pending=sum(1 for s in sessions if str(s.get("outcome","")).lower() in {"pending","call back"})
    enrolled=sum(1 for s in sessions if str(s.get("outcome","")).lower()=="enrolled")
    counsellors=sorted({str(s.get("counsellor","")) for s in sessions if str(s.get("counsellor",""))},key=str.lower)
    rows="".join(f'<tr><td><b>{esc(s["_lead_id"])}</b></td><td><b>{esc(s["_name"])}</b><br><small>{esc(s["_phone"])}</small></td><td>{esc(s["_course"])}</td><td>{esc(s.get("counselling_date"))}<br>{esc(s.get("counselling_time"))}</td><td>{esc(s.get("counsellor")) or "—"}</td><td>{esc(s.get("mode"))}</td><td><span class="badge">{esc(s.get("outcome"))}</span></td><td>{esc(s.get("notes")) or "—"}<br><small>Next: {esc(s.get("next_follow_up_date")) or "—"}</small></td><td><a class="btn secondary" href="/lead?id={esc(s["_lead_id"])}">Open</a></td></tr>' for s in sessions)
    body=f"""<div class="statrow"><div class="statmini"><div class="label">TOTAL SESSIONS</div><b class="value">{len(sessions)}</b></div><div class="statmini"><div class="label">TODAY</div><b class="value">{today_n}</b></div><div class="statmini"><div class="label">PENDING / CALLBACK</div><b class="value">{pending}</b></div><div class="statmini"><div class="label">ENROLLED</div><b class="value">{enrolled}</b></div></div>
<section class="panel"><h2>Counselling Manager</h2><form class="toolbar" method="get"><input name="q" value="{esc(params.get("q",[""])[0])}" placeholder="Search student, lead, course..."><select name="counsellor"><option value="">All counsellors</option>{option_list(counsellors,co)}</select><select name="outcome"><option value="">All outcomes</option>{option_list(COUNSELLING_OUTCOMES,out)}</select><input type="date" name="date" value="{esc(df)}"><button>Search</button><span></span></form></section>
<section class="panel"><div class="tablewrap"><table><thead><tr><th>Lead</th><th>Student</th><th>Course</th><th>Date / Time</th><th>Counsellor</th><th>Mode</th><th>Outcome</th><th>Notes / Next</th><th>Action</th></tr></thead><tbody>{rows or '<tr><td colspan="9" class="muted">No counselling sessions found.</td></tr>'}</tbody></table></div></section>"""
    return page("Counselling Manager","counselling",body)

def followups_page(params):
    leads=all_leads(); filt=params.get("filter",["all"])[0]; q=params.get("q",[""])[0].strip().lower()
    items=[]
    for l in leads:
        state=follow_state(l)
        if filt=="today" and state!="today": continue
        if filt=="overdue" and state!="overdue": continue
        if filt=="upcoming" and state!="upcoming": continue
        if q:
            hay=" ".join(str(l.get(k,"")) for k in ("lead_id","name","phone","course_interest","assigned_counsellor","follow_up_notes")).lower()
            if q not in hay: continue
        if state!="none": items.append(l)
    items.sort(key=lambda l:(str(l.get("follow_up_date","")),str(l.get("follow_up_time",""))))
    rows="".join(f'<tr><td><b>{esc(l.get("lead_id"))}</b></td><td><b>{esc(l.get("name"))}</b><br><small>{esc(l.get("phone"))}</small></td><td>{esc(l.get("course_interest"))}</td><td>{esc(l.get("follow_up_date"))}<br>{esc(l.get("follow_up_time"))}</td><td>{esc(l.get("assigned_counsellor")) or "—"}</td><td><span class="badge {"red" if follow_state(l)=="overdue" else "gold" if follow_state(l)=="today" else ""}">{follow_state(l).upper()}</span></td><td>{esc(l.get("follow_up_notes")) or "—"}</td><td><a class="btn secondary" href="/lead?id={esc(l.get("lead_id"))}">Open</a></td></tr>' for l in items)
    body=f"""<div class="statrow"><div class="statmini"><div class="label">TODAY</div><b class="value">{sum(1 for l in leads if follow_state(l)=="today")}</b></div><div class="statmini"><div class="label">OVERDUE</div><b class="value">{sum(1 for l in leads if follow_state(l)=="overdue")}</b></div><div class="statmini"><div class="label">UPCOMING</div><b class="value">{sum(1 for l in leads if follow_state(l)=="upcoming")}</b></div><div class="statmini"><div class="label">TOTAL SCHEDULED</div><b class="value">{sum(1 for l in leads if follow_state(l)!="none")}</b></div></div>
<section class="panel"><h2>Follow-up Manager</h2><form class="toolbar" method="get"><input name="q" value="{esc(q)}" placeholder="Search student, lead ID, course..."><select name="filter"><option value="all" {"selected" if filt=="all" else ""}>All scheduled</option><option value="today" {"selected" if filt=="today" else ""}>Today</option><option value="overdue" {"selected" if filt=="overdue" else ""}>Overdue</option><option value="upcoming" {"selected" if filt=="upcoming" else ""}>Upcoming</option></select><span></span><span></span><button>Filter</button><a class="btn secondary" href="/follow-ups">Clear</a></form></section>
<section class="panel"><div class="tablewrap"><table><thead><tr><th>Lead</th><th>Student</th><th>Course</th><th>Date / Time</th><th>Counsellor</th><th>State</th><th>Notes</th><th>Action</th></tr></thead><tbody>{rows or '<tr><td colspan="8" class="muted">No scheduled follow-ups.</td></tr>'}</tbody></table></div></section>"""
    return page("Follow-up Manager","followups",body)

def lead_page(lid, message=""):
    l=get_lead(lid)
    if not l:
        return page("Lead Not Found","dashboard",'<section class="panel"><h2>Lead not found</h2><a class="btn" href="/">Back</a></section>')
    ch=history(l,"counselling_history"); fh=history(l,"follow_up_history"); ph=history(l,"payment_history")
    final_fee=dec(l.get("final_fee")); paid=dec(l.get("total_paid")); bal=dec(l.get("balance_amount")); curr=str(l.get("currency","INR"))
    ch_rows="".join(f'<tr><td>{esc(s.get("counselling_date"))}</td><td>{esc(s.get("counselling_time"))}</td><td>{esc(s.get("counsellor"))}</td><td>{esc(s.get("mode"))}</td><td>{esc(s.get("outcome"))}</td><td>{esc(s.get("notes"))}</td><td>{esc(s.get("next_follow_up_date"))}</td></tr>' for s in ch if isinstance(s,dict))
    fh_rows="".join(f'<tr><td>{esc(a.get("action_at"))}</td><td>{esc(a.get("counsellor"))}</td><td>{esc(a.get("outcome"))}</td><td>{esc(a.get("notes"))}</td><td>{esc(a.get("next_follow_up_date"))} {esc(a.get("next_follow_up_time"))}</td></tr>' for a in fh if isinstance(a,dict))
    ph_rows="".join(f'<tr><td>{esc(p.get("payment_id"))}</td><td>{money(p.get("amount"))}</td><td>{esc(p.get("payment_mode"))}</td><td>{esc(p.get("transaction_id"))}</td><td>{esc(p.get("payment_date"))}</td></tr>' for p in ph if isinstance(p,dict))
    timeline=[]
    if l.get("created_at"): timeline.append(("Lead created",l.get("created_at"),"CRM"))
    for s in ch:
        if isinstance(s,dict): timeline.append(("Counselling",s.get("created_at",""),f'{s.get("outcome","")} · {s.get("mode","")}'))
    for a in fh:
        if isinstance(a,dict): timeline.append(("Follow-up",a.get("action_at",""),str(a.get("outcome",""))))
    timeline.sort(key=lambda x:str(x[1]),reverse=True)
    timeline_html="".join(f'<div class="event"><b>{esc(a)}</b><div class="muted">{esc(b)} · {esc(c)}</div></div>' for a,b,c in timeline)
    body=f"""<a class="btn secondary" href="/">← Back to Lead Manager</a>{f'<div class="notice" style="margin-top:15px">{esc(message)}</div>' if message else ""}
<section class="panel"><div class="section-title"><div><div class="label">LEAD PROFILE</div><h2>{esc(l.get("name"))}</h2><div class="muted">{esc(l.get("lead_id"))} · {esc(l.get("course_interest"))}</div></div><span class="badge">{esc(l.get("status","New"))}</span></div></section>
<div class="grid2"><section class="panel"><h2>Student Information</h2><div class="form-grid">
<div class="field"><label>Lead ID</label><input value="{esc(l.get("lead_id"))}" disabled></div><div class="field"><label>Name</label><input value="{esc(l.get("name"))}" disabled></div>
<div class="field"><label>Phone</label><input value="{esc(l.get("phone"))}" disabled></div><div class="field"><label>Email</label><input value="{esc(l.get("email"))}" disabled></div>
<div class="field"><label>Country</label><input value="{esc(l.get("country"))}" disabled></div><div class="field"><label>Preferred Language</label><input value="{esc(l.get("preferred_language"))}" disabled></div>
<div class="field"><label>Course Interest</label><input value="{esc(l.get("course_interest"))}" disabled></div><div class="field"><label>Education</label><input value="{esc(l.get("education"))}" disabled></div>
</div></section>
<section class="panel"><h2>Finance</h2><div class="grid2"><div class="card"><div class="label">Final Fee</div><div class="value">{money(final_fee)} {esc(curr)}</div></div><div class="card"><div class="label">Collected</div><div class="value">{money(paid)} {esc(curr)}</div></div><div class="card"><div class="label">Outstanding</div><div class="value">{money(bal)} {esc(curr)}</div></div><div class="card"><div class="label">Payment Status</div><div class="value" style="font-size:20px">{esc(l.get("payment_status","Not Started"))}</div></div></div></section></div>
<section class="panel"><h2>Update CRM</h2><form method="post" action="/update-lead"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="form-grid">
<div class="field"><label>Status</label><select name="status">{option_list(STATUSES,l.get("status","New"))}</select></div>
<div class="field"><label>Payment Status</label><select name="payment_status">{option_list(PAYMENT_STATUSES,l.get("payment_status","Not Started"))}</select></div>
<div class="field"><label>Lead Source</label><select name="source">{option_list(SOURCES,l.get("source","Other"))}</select></div>
<div class="field"><label>Assigned Counsellor</label><input name="assigned_counsellor" value="{esc(l.get("assigned_counsellor"))}"></div>
<div class="field"><label>Follow-up Date</label><input type="date" name="follow_up_date" value="{esc(l.get("follow_up_date"))}"></div>
<div class="field"><label>Follow-up Time</label><input type="time" name="follow_up_time" value="{esc(l.get("follow_up_time"))}"></div>
<div class="field full"><label>Follow-up Notes</label><textarea name="follow_up_notes">{esc(l.get("follow_up_notes"))}</textarea></div>
</div><div class="actions"><button>Save CRM Changes</button></div></form></section>
<section class="panel"><h2>New Counselling Session</h2><form method="post" action="/add-counselling"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="form-grid">
<div class="field"><label>Counsellor</label><input name="counsellor" value="{esc(l.get("assigned_counsellor"))}"></div><div class="field"><label>Date</label><input type="date" name="counselling_date" value="{today()}"></div>
<div class="field"><label>Time</label><input type="time" name="counselling_time"></div><div class="field"><label>Mode</label><select name="mode">{option_list(COUNSELLING_MODES,"Phone")}</select></div>
<div class="field"><label>Outcome</label><select name="outcome">{option_list(COUNSELLING_OUTCOMES,"Pending")}</select></div><div class="field"><label>Next Follow-up Date</label><input type="date" name="next_follow_up_date"></div>
<div class="field"><label>Next Follow-up Time</label><input type="time" name="next_follow_up_time"></div><div class="field full"><label>Notes</label><textarea name="notes"></textarea></div>
</div><div class="actions"><button>Save Counselling Session</button></div></form></section>
<section class="panel"><h2>Counselling History</h2><div class="tablewrap"><table><thead><tr><th>Date</th><th>Time</th><th>Counsellor</th><th>Mode</th><th>Outcome</th><th>Notes</th><th>Next</th></tr></thead><tbody>{ch_rows or '<tr><td colspan="7" class="muted">No counselling sessions recorded.</td></tr>'}</tbody></table></div></section>
<section class="panel"><h2>Record Follow-up Action</h2><form method="post" action="/follow-up-action"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="form-grid">
<div class="field"><label>Outcome</label><select name="outcome">{option_list(FOLLOWUP_OUTCOMES,"Contacted")}</select></div><div class="field"><label>Counsellor</label><input name="counsellor" value="{esc(l.get("assigned_counsellor"))}"></div>
<div class="field"><label>Next Date</label><input type="date" name="next_follow_up_date"></div><div class="field"><label>Next Time</label><input type="time" name="next_follow_up_time"></div>
<div class="field full"><label>Notes</label><textarea name="notes"></textarea></div></div><div class="actions"><button>Save Follow-up Action</button></div></form></section>
<section class="panel"><h2>Follow-up History</h2><div class="tablewrap"><table><thead><tr><th>When</th><th>Counsellor</th><th>Outcome</th><th>Notes</th><th>Next</th></tr></thead><tbody>{fh_rows or '<tr><td colspan="5" class="muted">No follow-up actions recorded.</td></tr>'}</tbody></table></div></section>
<section class="panel"><h2>Payment</h2><form method="post" action="/record-payment"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="form-grid">
<div class="field"><label>Payment Amount</label><input type="number" step="0.01" min="0" name="amount" required></div><div class="field"><label>Payment Mode</label><select name="payment_mode">{option_list(PAYMENT_MODES,"Online")}</select></div>
<div class="field"><label>Transaction / Reference ID</label><input name="transaction_id"></div><div class="field"><label>Payment Date</label><input type="date" name="payment_date" value="{today()}"></div>
<div class="field full"><label>Notes</label><textarea name="notes"></textarea></div></div><div class="actions"><button>Record Payment</button></div></form>
<h3 style="margin-top:25px">Payment History</h3><div class="tablewrap"><table><thead><tr><th>Payment ID</th><th>Amount</th><th>Mode</th><th>Reference</th><th>Date</th></tr></thead><tbody>{ph_rows or '<tr><td colspan="5" class="muted">No payments recorded.</td></tr>'}</tbody></table></div></section>
<section class="panel"><h2>Activity Timeline</h2><div class="timeline">{timeline_html or '<div class="muted">No activity recorded yet.</div>'}</div></section>"""
    return page(f"{lid} — Lead Profile","dashboard",body)

def error_page(exc):
    return page("Server Error","dashboard",f'<section class="panel"><h2>Server Error</h2><p>{esc(exc)}</p><a class="btn" href="/">Back to Dashboard</a></section>')

def update_record(lid, data):
    obj=load(); l=obj.get(lid)
    if not isinstance(l,dict): return False
    updates={
        "status":data.get("status",[l.get("status","New")])[0].strip(),
        "payment_status":data.get("payment_status",[l.get("payment_status","Not Started")])[0].strip(),
        "source":data.get("source",[l.get("source","Other")])[0].strip(),
        "assigned_counsellor":data.get("assigned_counsellor",[""])[0].strip(),
        "follow_up_date":data.get("follow_up_date",[""])[0].strip(),
        "follow_up_time":data.get("follow_up_time",[""])[0].strip(),
        "follow_up_notes":data.get("follow_up_notes",[""])[0].strip(),
    }
    if updates["status"] not in STATUSES: updates["status"]="New"
    if updates["payment_status"] not in PAYMENT_STATUSES: updates["payment_status"]="Not Started"
    if updates["source"] not in SOURCES: updates["source"]="Other"
    if not valid_date(updates["follow_up_date"]) or not valid_time(updates["follow_up_time"]): return False
    old=l.get("status","New")
    l.update(updates)
    if updates["status"]!=old:
        sh=history(l,"status_history")
        if not sh or not isinstance(sh[-1],dict) or sh[-1].get("status")!=old:
            sh.append({"status":old,"changed_at":l.get("created_at",now())})
        sh.append({"status":updates["status"],"changed_at":now()})
    l["last_contacted_at"]=now() if updates["status"] not in {"New","Lost"} else l.get("last_contacted_at","")
    l["updated_at"]=now()
    country=str(l.get("country","")).strip().lower()
    l["international_student"]=country not in ("","india","indian")
    obj[lid]=l; save(obj); return True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[CRM]", fmt % args)
    def send_html(self, content, status=200):
        b=content.encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def redirect(self,url):
        self.send_response(303); self.send_header("Location",url); self.end_headers()
    def post_data(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        return parse_qs(self.rfile.read(n).decode("utf-8"),keep_blank_values=True)
    def do_GET(self):
        try:
            u=urlparse(self.path); p=parse_qs(u.query,keep_blank_values=True)
            if u.path=="/brand-logo":
                logo=find_logo()
                if logo:
                    data=logo.read_bytes(); self.send_response(200); self.send_header("Content-Type","image/png"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
                data=BRAND_SVG.encode(); self.send_response(200); self.send_header("Content-Type","image/svg+xml"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
            if u.path=="/": return self.send_html(dashboard(p))
            if u.path=="/counselling": return self.send_html(counselling_page(p))
            if u.path=="/follow-ups": return self.send_html(followups_page(p))
            if u.path=="/lead":
                lid=p.get("id",[""])[0]; l=get_lead(lid); return self.send_html(lead_page(lid,p.get("message",[""])[0]),200 if l else 404)
            return self.send_html(page("404","dashboard",'<section class="panel"><h2>404 — Page not found</h2><a class="btn" href="/">Back</a></section>'),404)
        except Exception as exc:
            print("GET ERROR:",repr(exc)); return self.send_html(error_page(exc),500)
    def do_POST(self):
        try:
            u=urlparse(self.path); d=self.post_data()
            if u.path=="/update-lead":
                lid=d.get("lead_id",[""])[0].strip()
                if not get_lead(lid): return self.send_html("<h1>Lead not found</h1>",404)
                if not update_record(lid,d): return self.send_html("<h1>Invalid CRM data</h1><p>Check date/time and selected options.</p>",400)
                return self.redirect("/lead?"+urlencode({"id":lid,"message":"CRM changes saved"}))
            if u.path=="/add-counselling":
                lid=d.get("lead_id",[""])[0].strip()
                if not get_lead(lid): return self.send_html("<h1>Lead not found</h1>",404)
                cd=d.get("counselling_date",[""])[0].strip(); ct=d.get("counselling_time",[""])[0].strip(); nd=d.get("next_follow_up_date",[""])[0].strip(); nt=d.get("next_follow_up_time",[""])[0].strip()
                mode=d.get("mode",["Phone"])[0].strip(); outcome=d.get("outcome",["Pending"])[0].strip()
                if not valid_date(cd) or not valid_time(ct) or not valid_date(nd) or not valid_time(nt): return self.send_html("<h1>Invalid date/time</h1>",400)
                obj=load(); l=obj.get(lid); ch=history(l,"counselling_history"); t=now()
                s={"session_id":f"CS-{len(ch)+1:05d}","counsellor":d.get("counsellor",[""])[0].strip(),"counselling_date":cd,"counselling_time":ct,"mode":mode if mode in COUNSELLING_MODES else "Phone","outcome":outcome if outcome in COUNSELLING_OUTCOMES else "Pending","notes":d.get("notes",[""])[0].strip(),"next_follow_up_date":nd,"next_follow_up_time":nt,"created_at":t,"updated_at":t}
                ch.append(s); l["assigned_counsellor"]=s["counsellor"] or l.get("assigned_counsellor",""); l["follow_up_date"]=nd; l["follow_up_time"]=nt; l["follow_up_notes"]=s["notes"]; l["last_contacted_at"]=t
                l["status"]={"Interested":"Interested","Application":"Application","Payment Pending":"Payment Pending","Enrolled":"Enrolled","Lost":"Lost","Not Interested":"Lost","Call Back":"Contacted","Pending":"Counselling"}.get(s["outcome"],l.get("status","Counselling")); l["updated_at"]=t; obj[lid]=l; save(obj)
                return self.redirect("/lead?"+urlencode({"id":lid,"message":"Counselling session saved successfully"}))
            if u.path=="/follow-up-action":
                lid=d.get("lead_id",[""])[0].strip()
                if not get_lead(lid): return self.send_html("<h1>Lead not found</h1>",404)
                obj=load(); l=obj[lid]; fh=history(l,"follow_up_history"); outcome=d.get("outcome",["Contacted"])[0].strip(); t=now(); nd=d.get("next_follow_up_date",[""])[0].strip(); nt=d.get("next_follow_up_time",[""])[0].strip()
                if not valid_date(nd) or not valid_time(nt): return self.send_html("<h1>Invalid next follow-up date/time</h1>",400)
                if outcome not in FOLLOWUP_OUTCOMES: outcome="Contacted"
                if outcome in {"Enrolled","Lost","Not Interested"}: nd=nt=""
                new_status={"Contacted":"Contacted","No Answer":"Contacted","Call Back":"Contacted","Interested":"Interested","Not Interested":"Lost","Application":"Application","Payment Pending":"Payment Pending","Enrolled":"Enrolled","Lost":"Lost"}.get(outcome,l.get("status","New"))
                a={"action_id":f"FU-{len(fh)+1:05d}","action_at":t,"counsellor":d.get("counsellor",[""])[0].strip() or l.get("assigned_counsellor",""),"outcome":outcome,"notes":d.get("notes",[""])[0].strip(),"next_follow_up_date":nd,"next_follow_up_time":nt,"status_after":new_status}
                fh.append(a); l["status"]=new_status; l["follow_up_date"]=nd; l["follow_up_time"]=nt; l["follow_up_notes"]=a["notes"] or l.get("follow_up_notes",""); l["assigned_counsellor"]=a["counsellor"]; l["last_contacted_at"]=t; l["updated_at"]=t; obj[lid]=l; save(obj)
                return self.redirect("/lead?"+urlencode({"id":lid,"message":"Follow-up action saved successfully"}))
            if u.path=="/record-payment":
                lid=d.get("lead_id",[""])[0].strip(); amount=dec(d.get("amount",["0"])[0])
                if not get_lead(lid) or amount<=0: return self.send_html("<h1>Invalid payment</h1>",400)
                obj=load(); l=obj[lid]; final=dec(l.get("final_fee")); paid=dec(l.get("total_paid")); balance=max(Decimal("0"),final-paid)
                if final>0: amount=min(amount,balance)
                if amount<=0: return self.send_html("<h1>No remaining balance</h1>",400)
                ph=history(l,"payment_history"); t=now(); pm=d.get("payment_mode",["Online"])[0]
                pay={"payment_id":f"PAY-{len(ph)+1:05d}","amount":float(amount),"payment_mode":pm if pm in PAYMENT_MODES else "Other","transaction_id":d.get("transaction_id",[""])[0].strip(),"payment_date":d.get("payment_date",[today()])[0].strip() or today(),"notes":d.get("notes",[""])[0].strip(),"recorded_at":t}
                ph.append(pay); l["total_paid"]=float(paid+amount); l["payment_mode"]=pay["payment_mode"]; l["transaction_id"]=pay["transaction_id"]; l["payment_date"]=pay["payment_date"]; l["final_fee"]=float(final); l["balance_amount"]=float(max(Decimal("0"),final-(paid+amount))); l["payment_status"]="Paid" if final>0 and paid+amount>=final else "Partial"; l["updated_at"]=t; obj[lid]=l; save(obj)
                return self.redirect("/lead?"+urlencode({"id":lid,"message":"Payment recorded successfully"}))
            return self.send_html("<h1>404 - Not Found</h1>",404)
        except Exception as exc:
            print("POST ERROR:",repr(exc)); return self.send_html(error_page(exc),500)

def main():
    ensure_data()
    find_logo()
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print("="*72)
    print("SAYYED EDVANTAGE CRM — CLEAN PROFESSIONAL BUILD")
    print(f"Dashboard: http://{HOST}:{PORT}")
    print(f"Data     : {LEADS_FILE}")
    print("Routes   : /  /counselling  /follow-ups  /lead")
    print("Press Ctrl+C to stop.")
    print("="*72)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCRM stopped.")
    finally:
        server.server_close()

if __name__=="__main__":
    main()
