from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.leads.lead_manager import get_all_leads, get_lead, update_lead


HOST = "127.0.0.1"
PORT = 8000

STATUSES = [
    "New",
    "Contacted",
    "Counselling",
    "Interested",
    "Application",
    "Payment Pending",
    "Enrolled",
    "Lost",
]

PAYMENT_STATUSES = [
    "Not Started",
    "Quotation Sent",
    "Payment Pending",
    "Partially Paid",
    "Paid",
    "Refunded",
]

SOURCES = [
    "AI Agent",
    "Website",
    "Google Ads",
    "Instagram",
    "Facebook",
    "YouTube",
    "WhatsApp",
    "Referral",
    "School/College",
    "Other",
]


def safe(value) -> str:
    return html.escape(str(value or ""))


def filtered_leads(leads, q="", status="", country="", course=""):
    q = q.strip().lower()
    status = status.strip().lower()
    country = country.strip().lower()
    course = course.strip().lower()

    result = []

    for lead in leads:
        if not isinstance(lead, dict):
            continue

        if status and str(lead.get("status", "")).lower() != status:
            continue

        if country and str(lead.get("country", "")).lower() != country:
            continue

        if course and course not in str(lead.get("course_interest", "")).lower():
            continue

        if q:
            searchable = " ".join(
                str(lead.get(k, ""))
                for k in (
                    "lead_id", "name", "phone", "email", "country",
                    "course_interest", "education", "source",
                    "assigned_counsellor", "follow_up_notes",
                )
            ).lower()
            if q not in searchable:
                continue

        result.append(lead)

    return result


def unique_values(leads, key):
    return sorted(
        {
            str(lead.get(key, "")).strip()
            for lead in leads
            if isinstance(lead, dict) and str(lead.get(key, "")).strip()
        },
        key=str.lower,
    )


def option_list(values, selected=""):
    out = ""
    for value in values:
        out += (
            f'<option value="{safe(value)}" '
            f'{"selected" if value.lower() == selected.lower() else ""}>'
            f'{safe(value)}</option>'
        )
    return out


def status_options(selected):
    return option_list(STATUSES, selected)


def payment_options(selected):
    return option_list(PAYMENT_STATUSES, selected)


def source_options(selected):
    return option_list(SOURCES, selected)


def followup_state(lead, today=None):
    today = today or datetime.now().date()
    raw = str(lead.get("follow_up_date", "")).strip()
    if not raw:
        return "none"
    try:
        follow_date = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return "none"
    if follow_date < today:
        return "overdue"
    if follow_date == today:
        return "today"
    return "upcoming"


def followup_outcome_options(selected="Contacted"):
    outcomes = [
        "Contacted", "No Answer", "Call Back", "Interested",
        "Not Interested", "Application", "Payment Pending",
        "Enrolled", "Lost",
    ]
    return option_list(outcomes, selected)


def followups_page(leads, filter_name="today", message=""):
    today = datetime.now().date()
    valid_filters = {"overdue", "today", "upcoming", "all"}
    if filter_name not in valid_filters:
        filter_name = "today"

    work = []
    for lead in leads:
        state = followup_state(lead, today)
        if state == "none":
            continue
        if filter_name != "all" and state != filter_name:
            continue
        work.append(lead)

    def sort_key(lead):
        return (
            str(lead.get("follow_up_date", "9999-12-31")),
            str(lead.get("follow_up_time", "23:59")) or "23:59",
            str(lead.get("name", "")).lower(),
        )

    work.sort(key=sort_key)

    counts = {"overdue": 0, "today": 0, "upcoming": 0}
    for lead in leads:
        state = followup_state(lead, today)
        if state in counts:
            counts[state] += 1

    rows = []
    for lead in work:
        state = followup_state(lead, today)
        badge_class = {"overdue": "danger", "today": "today", "upcoming": "upcoming"}[state]
        state_label = {"overdue": "Overdue", "today": "Today", "upcoming": "Upcoming"}[state]
        lead_id = str(lead.get("lead_id", ""))
        phone = str(lead.get("phone", "")).strip()
        history = lead.get("follow_up_history", [])
        history = history if isinstance(history, list) else []
        phone_action = (
            f'<a class="call" href="tel:{safe(phone)}">Call / Contact</a>'
            if phone else '<span class="muted">No phone</span>'
        )

        rows.append(f"""
        <tr>
          <td><strong>{safe(lead_id)}</strong></td>
          <td><strong>{safe(lead.get('name'))}</strong><br><small>{safe(phone)}</small></td>
          <td>{safe(lead.get('country'))}<br><small>{safe(lead.get('course_interest'))}</small></td>
          <td><span class="badge {badge_class}">{state_label}</span><br>
              <strong>{safe(lead.get('follow_up_date'))}</strong>
              {f'<br><small>{safe(lead.get("follow_up_time"))}</small>' if lead.get('follow_up_time') else ''}
          </td>
          <td>{safe(lead.get('assigned_counsellor')) or '<span class="muted">Unassigned</span>'}</td>
          <td>{safe(lead.get('follow_up_notes')) or '<span class="muted">No notes</span>'}</td>
          <td>
            <div class="action-box">
              <div class="contact-row">{phone_action}<a class="view" href="/lead?id={safe(lead_id)}">Open Lead</a></div>
              <form method="post" action="/follow-up-action">
                <input type="hidden" name="lead_id" value="{safe(lead_id)}">
                <div class="action-grid">
                  <select name="outcome">{followup_outcome_options()}</select>
                  <input type="date" name="next_follow_up_date">
                  <input type="time" name="next_follow_up_time">
                  <input name="counsellor" value="{safe(lead.get('assigned_counsellor'))}" placeholder="Counsellor">
                </div>
                <textarea name="notes" placeholder="What happened in this follow-up? Add student response, objections, payment discussion, next action..."></textarea>
                <button type="submit">Save Follow-up</button>
              </form>
              <small class="history-link">{len(history)} follow-up action(s) recorded</small>
            </div>
          </td>
        </tr>
        """)

    table = "".join(rows) or '<tr><td colspan="7" class="empty">No follow-ups found for this view.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Follow-up Manager - Sayyed EdVantage</title>
<style>
:root {{--blue:#1769aa;--dark:#14213d;--bg:#f4f7fb;--border:#dfe5ee;--muted:#697586}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:#172033;font-family:Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(135deg,var(--dark),var(--blue));color:#fff;padding:24px 34px}}
header h1{{margin:0 0 5px;font-size:28px}} header p{{margin:0;opacity:.85}} main{{max-width:1600px;margin:auto;padding:24px 30px}}
a{{color:var(--blue);text-decoration:none;font-weight:600}} .back{{display:inline-block;margin-bottom:16px}}
.notice{{background:#eef8f0;border:1px solid #b9dfc0;padding:11px 13px;border-radius:8px;margin-bottom:16px;color:#17633f}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}} .card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px}}
.card span{{display:block;color:var(--muted);font-size:12px}} .card strong{{font-size:28px;display:block;margin-top:6px}}
.toolbar{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:18px;display:flex;gap:9px;align-items:center;flex-wrap:wrap}}
.toolbar a{{padding:9px 13px;border-radius:8px;border:1px solid var(--border);background:#fff}} .toolbar .active{{background:var(--blue);color:#fff;border-color:var(--blue)}}
.table-wrap{{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:auto}} table{{width:100%;border-collapse:collapse;min-width:1500px}}
th,td{{padding:12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;font-size:13px}} th{{background:#f8f9fc;color:#4e5a6c;position:sticky;top:0;z-index:1}}
small,.muted{{color:var(--muted)}} .badge{{display:inline-block;padding:4px 8px;border-radius:14px;font-size:11px;font-weight:700;margin-bottom:4px}}
.badge.danger{{background:#fff0f0;color:#b42318}} .badge.today{{background:#fff7df;color:#8a5b00}} .badge.upcoming{{background:#eef5ff;color:#1769aa}}
.view,.call{{display:inline-block;padding:7px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;margin-right:5px}} .call{{background:#eef8f0;border-color:#b9dfc0;color:#17633f}}
.action-box{{min-width:540px;background:#f8f9fc;border:1px solid var(--border);border-radius:10px;padding:10px}} .contact-row{{margin-bottom:8px}}
.action-grid{{display:grid;grid-template-columns:1.1fr 1fr 1fr 1fr;gap:6px;margin-bottom:6px}}
.action-grid input,.action-grid select,.action-box textarea{{width:100%;padding:8px;border:1px solid #cbd3df;border-radius:7px;background:#fff;font:inherit;font-size:12px}}
.action-box textarea{{min-height:58px;resize:vertical;margin-bottom:6px}} .action-box button{{background:var(--blue);color:#fff;border:1px solid var(--blue);border-radius:7px;padding:8px 12px;cursor:pointer;font-weight:600}}
.history-link{{display:block;margin-top:7px}} .empty{{text-align:center;padding:35px;color:var(--muted)}}
@media(max-width:900px){{.cards{{grid-template-columns:1fr}}main{{padding:18px}}.action-grid{{grid-template-columns:1fr}}}}
</style></head>
<body><header><h1>Sayyed EdVantage</h1><p>Admissions CRM & Follow-up Manager</p></header><main>
<a class="back" href="/">&larr; Back to Lead Manager</a>
{f'<div class="notice">{safe(message)}</div>' if message else ''}
<div class="cards"><div class="card"><span>Overdue Follow-ups</span><strong>{counts['overdue']}</strong></div><div class="card"><span>Follow-ups Today</span><strong>{counts['today']}</strong></div><div class="card"><span>Upcoming Follow-ups</span><strong>{counts['upcoming']}</strong></div></div>
<div class="toolbar"><strong>Follow-up Queue:</strong>
<a class="{'active' if filter_name == 'overdue' else ''}" href="/follow-ups?filter=overdue">Overdue ({counts['overdue']})</a>
<a class="{'active' if filter_name == 'today' else ''}" href="/follow-ups?filter=today">Today ({counts['today']})</a>
<a class="{'active' if filter_name == 'upcoming' else ''}" href="/follow-ups?filter=upcoming">Upcoming ({counts['upcoming']})</a>
<a class="{'active' if filter_name == 'all' else ''}" href="/follow-ups?filter=all">All</a></div>
<section class="table-wrap"><table><thead><tr><th>Lead ID</th><th>Student</th><th>Country / Course</th><th>Follow-up</th><th>Counsellor</th><th>Current Notes</th><th>Follow-up Action</th></tr></thead><tbody>{table}</tbody></table></section>
<p class="muted" style="margin-top:12px">Today is {safe(today.isoformat())}. Follow-up actions are stored in the same lead record used by the AI Agent.</p>
</main></body></html>"""


def dashboard_page(leads, q="", status="", country="", course="", message=""):
    filtered = filtered_leads(leads, q, status, country, course)

    status_counts = {s: 0 for s in STATUSES}
    payment_counts = {s: 0 for s in PAYMENT_STATUSES}
    source_counts = {}

    international = 0
    today = datetime.now().date().isoformat()
    followups_today = 0

    for lead in leads:
        st = str(lead.get("status", "New"))
        status_counts[st] = status_counts.get(st, 0) + 1

        ps = str(lead.get("payment_status", "Not Started"))
        payment_counts[ps] = payment_counts.get(ps, 0) + 1

        src = str(lead.get("source", "Other"))
        source_counts[src] = source_counts.get(src, 0) + 1

        if lead.get("international_student"):
            international += 1

        if str(lead.get("follow_up_date", "")) == today:
            followups_today += 1

    enrolled = status_counts.get("Enrolled", 0)
    conversion = round((enrolled / len(leads)) * 100, 1) if leads else 0

    countries = unique_values(leads, "country")
    courses = unique_values(leads, "course_interest")

    cards = f"""
    <div class="cards">
      <div class="card"><span>Total Leads</span><strong>{len(leads)}</strong></div>
      <div class="card"><span>New</span><strong>{status_counts.get("New", 0)}</strong></div>
      <div class="card"><span>Interested</span><strong>{status_counts.get("Interested", 0)}</strong></div>
      <div class="card"><span>International</span><strong>{international}</strong></div>
      <div class="card"><span>Follow-ups Today</span><strong>{followups_today}</strong></div>
      <div class="card"><span>Enrolled</span><strong>{enrolled}</strong></div>
      <div class="card"><span>Conversion</span><strong>{conversion}%</strong></div>
    </div>
    """

    status_pipeline = "".join(
        f'<div class="pipeline"><span>{safe(s)}</span><b>{status_counts.get(s, 0)}</b></div>'
        for s in STATUSES
    )

    source_summary = "".join(
        f'<div class="mini"><span>{safe(k)}</span><b>{v}</b></div>'
        for k, v in sorted(source_counts.items(), key=lambda x: (-x[1], x[0]))
    ) or '<div class="muted">No source data yet.</div>'

    rows = []

    for lead in filtered:
        lead_id = str(lead.get("lead_id", ""))
        current_status = str(lead.get("status", "New"))
        payment_status = str(lead.get("payment_status", "Not Started"))
        current_source = str(lead.get("source", "Other"))

        rows.append(f"""
        <tr>
          <td><strong>{safe(lead_id)}</strong></td>
          <td>
            <strong>{safe(lead.get("name"))}</strong><br>
            <small>{safe(lead.get("phone"))}</small>
          </td>
          <td>
            {safe(lead.get("country"))}
            {"<br><span class='intl'>International</span>" if lead.get("international_student") else ""}
          </td>
          <td>{safe(lead.get("course_interest"))}</td>
          <td>
            <div>{safe(lead.get("email"))}</div>
            <small>{safe(lead.get("education"))}</small>
          </td>
          <td>
            <form method="post" action="/update-lead" class="edit-form">
              <input type="hidden" name="lead_id" value="{safe(lead_id)}">
              <select name="status">{status_options(current_status)}</select>
              <select name="payment_status">{payment_options(payment_status)}</select>
              <select name="source">{source_options(current_source)}</select>
              <input type="date" name="follow_up_date" value="{safe(lead.get("follow_up_date"))}">
              <input type="time" name="follow_up_time" value="{safe(lead.get("follow_up_time"))}">
              <input name="assigned_counsellor" placeholder="Counsellor"
                     value="{safe(lead.get("assigned_counsellor"))}">
              <input name="follow_up_notes" placeholder="Follow-up notes"
                     value="{safe(lead.get("follow_up_notes"))}">
              <button type="submit">Save</button>
            </form>
          </td>
          <td>
            <a class="details" href="/lead?id={safe(lead_id)}">View</a>
          </td>
        </tr>
        """)

    table = "".join(rows) or """
      <tr><td colspan="7" class="empty">No leads match your filters.</td></tr>
    """

    status_filter = '<option value="">All statuses</option>' + option_list(STATUSES, status)
    country_filter = '<option value="">All countries</option>' + option_list(countries, country)
    course_filter = '<option value="">All courses</option>' + option_list(courses, course)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sayyed EdVantage — Admissions CRM</title>
<style>
:root {{
 --blue:#1769aa; --dark:#14213d; --gold:#c9972b; --bg:#f4f7fb;
 --border:#dfe5ee; --muted:#697586; --white:#fff;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:#172033;font-family:Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(135deg,var(--dark),var(--blue));color:#fff;padding:24px 34px}}
header h1{{margin:0 0 5px;font-size:28px}} header p{{margin:0;opacity:.85}}
main{{max-width:1600px;margin:auto;padding:24px 30px}}
.cards{{display:grid;grid-template-columns:repeat(7,minmax(120px,1fr));gap:12px;margin-bottom:18px}}
.card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;box-shadow:0 2px 8px #14213d0d}}
.card span{{font-size:12px;color:var(--muted)}} .card strong{{display:block;font-size:25px;margin-top:6px;color:var(--dark)}}
.grid{{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-bottom:18px}}
.panel{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:17px}}
.panel h2{{font-size:16px;margin:0 0 12px}}
.pipeline{{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #eef1f5;font-size:13px}}
.mini{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eef1f5;font-size:13px}}
.toolbar{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:18px}}
.toolbar form{{display:flex;gap:8px;flex-wrap:wrap}}
input,select,button{{border:1px solid #cbd3df;border-radius:8px;padding:8px 10px;font-size:13px;background:#fff}}
.toolbar input{{min-width:260px}}
button{{background:var(--blue);color:#fff;border-color:var(--blue);cursor:pointer}}
.table-wrap{{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:auto}}
table{{width:100%;border-collapse:collapse;min-width:1450px}}
th,td{{padding:11px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;font-size:12px}}
th{{background:#f8f9fc;color:#4e5a6c;position:sticky;top:0}}
.edit-form{{display:grid;grid-template-columns:145px 145px 130px 125px 100px 150px 150px 55px;gap:5px}}
.edit-form input,.edit-form select{{min-width:0;width:100%;padding:7px}}
.intl{{display:inline-block;margin-top:4px;font-size:10px;background:#eef7ff;color:var(--blue);padding:2px 6px;border-radius:10px}}
.details{{color:var(--blue);text-decoration:none;font-weight:600}}
.empty{{text-align:center;padding:35px;color:var(--muted)}}
.muted,small{{color:var(--muted)}}
.notice{{background:#eef8f0;border:1px solid #b9dfc0;padding:10px 12px;border-radius:8px;margin-bottom:14px}}
@media(max-width:1000px){{.cards{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header><h1>Sayyed EdVantage</h1><p>Admissions CRM & Lead Manager</p></header>
<main>
{f'<div class="notice">{safe(message)}</div>' if message else ''}
{cards}

<div class="grid">
  <section class="panel"><h2>Admission Pipeline</h2>{status_pipeline}</section>
  <section class="panel"><h2>Lead Sources</h2>{source_summary}</section>
</div>

<section class="toolbar">
<div style="margin-bottom:10px"><a href="/follow-ups" style="font-weight:700">Open Follow-up Manager</a></div>
<form method="get" action="/">
<input name="q" value="{safe(q)}" placeholder="Search name, phone, email, course...">
<select name="status">{status_filter}</select>
<select name="country">{country_filter}</select>
<select name="course">{course_filter}</select>
<button>Search</button>
<a href="/" style="padding:9px;color:#1769aa;text-decoration:none">Clear</a>
</form>
</section>

<section class="table-wrap">
<table>
<thead><tr>
<th>Lead ID</th><th>Student</th><th>Country</th><th>Course</th>
<th>Contact / Education</th><th>CRM Actions</th><th>Details</th>
</tr></thead>
<tbody>{table}</tbody>
</table>
</section>
<p class="muted">Showing {len(filtered)} of {len(leads)} leads. Data is stored in the same leads.json used by the AI Agent.</p>
</main>
</body>
</html>"""


def lead_details_page(lead, message=""):
    if not lead:
        return '''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Lead Not Found</title></head>
<body style="font-family:Segoe UI,Arial;padding:40px;background:#f4f7fb">
<h1>Lead not found</h1><p><a href="/">← Back to Lead Manager</a></p>
</body></html>'''

    lead_id_raw = str(lead.get("lead_id", ""))
    lead_id = safe(lead_id_raw)
    status = str(lead.get("status", "New"))
    payment_status = str(lead.get("payment_status", "Not Started"))
    source = str(lead.get("source", "Other"))

    international = bool(lead.get("international_student"))
    base_fee = lead.get("base_fee_inr", "")
    discount = lead.get("discount_percent", "")
    final_fee = lead.get("final_fee_inr", "")
    currency = lead.get("fee_currency", "INR")
    converted = lead.get("converted_fee", "")

    activity = []
    created = lead.get("created_at")
    updated = lead.get("updated_at")
    last_contacted = lead.get("last_contacted_at")

    if created:
        activity.append(("Lead created", created, "AI Agent / CRM"))
    if last_contacted:
        activity.append(("Student contacted / stage progressed", last_contacted, "CRM"))
    if updated and updated != created and updated != last_contacted:
        activity.append(("Lead record updated", updated, "CRM"))

    activity_html = "".join(
        f'''
        <div class="timeline-item">
          <div class="timeline-dot"></div>
          <div>
            <strong>{safe(title)}</strong>
            <div class="timeline-meta">{safe(when)} · {safe(actor)}</div>
          </div>
        </div>
        '''
        for title, when, actor in activity
    ) or '<div class="muted">No activity recorded yet.</div>'

    financial_html = f'''
    <div class="finance-grid">
      <div class="finance-card">
        <span>Student Type</span>
        <strong>{"International" if international else "Domestic"}</strong>
      </div>
      <div class="finance-card">
        <span>Base Fee</span>
        <strong>{safe(base_fee) if base_fee != "" else "Not set"} {safe(currency)}</strong>
      </div>
      <div class="finance-card">
        <span>Discount</span>
        <strong>{safe(discount) + "%" if discount != "" else "Not set"}</strong>
      </div>
      <div class="finance-card highlight">
        <span>Final Fee</span>
        <strong>{safe(final_fee) if final_fee != "" else "Not set"} {safe(currency)}</strong>
      </div>
      <div class="finance-card">
        <span>Converted Amount</span>
        <strong>{safe(converted) if converted != "" else "Not set"}</strong>
      </div>
    </div>
    '''

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{lead_id} — Sayyed EdVantage</title>
<style>
:root {{
  --blue:#1769aa; --dark:#14213d; --bg:#f4f7fb;
  --border:#dfe5ee; --muted:#697586; --white:#fff;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:#172033;font-family:Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(135deg,var(--dark),var(--blue));color:#fff;padding:24px 34px}}
header h1{{margin:0 0 5px;font-size:28px}}
header p{{margin:0;opacity:.85}}
main{{max-width:1250px;margin:auto;padding:24px 30px}}
.back{{display:inline-block;margin-bottom:16px;color:var(--blue);text-decoration:none;font-weight:600}}
.notice{{background:#eef8f0;border:1px solid #b9dfc0;padding:11px 13px;border-radius:8px;margin-bottom:16px;color:#17633f}}
.hero{{background:#fff;border:1px solid var(--border);border-radius:14px;padding:20px;margin-bottom:16px;
       display:flex;justify-content:space-between;align-items:center;gap:20px}}
.hero h2{{margin:0 0 5px;font-size:25px}}
.hero p{{margin:0;color:var(--muted)}}
.badge{{display:inline-block;padding:7px 12px;border-radius:20px;background:#eef5ff;color:var(--blue);
       font-weight:700;font-size:13px}}
.layout{{display:grid;grid-template-columns:1.35fr .65fr;gap:16px}}
.panel{{background:#fff;border:1px solid var(--border);border-radius:14px;padding:20px;margin-bottom:16px}}
.panel h3{{margin:0 0 15px;font-size:17px;color:var(--dark)}}
.info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}}
.item{{border-bottom:1px solid #edf0f4;padding:12px 0}}
.item span{{display:block;color:var(--muted);font-size:12px;margin-bottom:4px}}
.item strong{{display:block;word-break:break-word}}
.finance-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
.finance-card{{border:1px solid var(--border);border-radius:10px;padding:13px;background:#fbfcfe}}
.finance-card span{{display:block;color:var(--muted);font-size:11px}}
.finance-card strong{{display:block;margin-top:5px;font-size:17px}}
.finance-card.highlight{{border-color:#b7d5ef;background:#f1f8ff}}
.message{{background:#f8f9fc;border:1px solid #edf0f4;padding:15px;border-radius:9px;
          margin-top:10px;white-space:pre-wrap;word-break:break-word;min-height:45px}}
.timeline{{position:relative;padding-left:24px}}
.timeline:before{{content:"";position:absolute;left:6px;top:4px;bottom:4px;width:2px;background:#d9e4f0}}
.timeline-item{{position:relative;padding:0 0 18px 12px}}
.timeline-dot{{position:absolute;left:-22px;top:3px;width:12px;height:12px;border-radius:50%;
              background:var(--blue);border:2px solid #fff;box-shadow:0 0 0 2px #cfe1f3}}
.timeline-meta{{font-size:11px;color:var(--muted);margin-top:4px}}
.edit-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
label{{font-size:12px;color:var(--muted);display:block;margin-bottom:5px}}
input,select,textarea,button{{width:100%;border:1px solid #cbd3df;border-radius:8px;padding:9px 10px;
                              font:inherit;background:#fff}}
textarea{{min-height:100px;resize:vertical}}
button{{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600;cursor:pointer}}
.full{{grid-column:1 / -1}}
.actions{{display:flex;gap:10px;margin-top:12px}}
.actions a{{padding:9px 13px;border:1px solid var(--border);border-radius:8px;text-decoration:none;color:var(--blue)}}
.muted{{color:var(--muted);font-size:13px}}
@media(max-width:850px){{
  .layout{{grid-template-columns:1fr}}
  .info-grid,.edit-grid,.finance-grid{{grid-template-columns:1fr}}
  .hero{{align-items:flex-start;flex-direction:column}}
  main{{padding:18px}}
}}
</style>
</head>
<body>
<header>
  <h1>Sayyed EdVantage</h1>
  <p>Admissions CRM & Lead Manager</p>
</header>

<main>
<a class="back" href="/">← Back to Lead Manager</a>
{f'<div class="notice">{safe(message)}</div>' if message else ''}

<section class="hero">
  <div>
    <h2>{safe(lead.get("name"))}</h2>
    <p>Lead ID: <strong>{lead_id}</strong> · {safe(lead.get("course_interest"))}</p>
  </div>
  <span class="badge">{safe(status)}</span>
</section>

<div class="layout">
  <div>
    <section class="panel">
      <h3>Student Information</h3>
      <div class="info-grid">
        <div class="item"><span>Lead ID</span><strong>{lead_id}</strong></div>
        <div class="item"><span>Name</span><strong>{safe(lead.get("name"))}</strong></div>
        <div class="item"><span>Phone</span><strong>{safe(lead.get("phone"))}</strong></div>
        <div class="item"><span>Email</span><strong>{safe(lead.get("email"))}</strong></div>
        <div class="item"><span>Country</span><strong>{safe(lead.get("country"))}</strong></div>
        <div class="item"><span>Preferred Language</span><strong>{safe(lead.get("preferred_language"))}</strong></div>
        <div class="item"><span>Course Interest</span><strong>{safe(lead.get("course_interest"))}</strong></div>
        <div class="item"><span>Education</span><strong>{safe(lead.get("education"))}</strong></div>
        <div class="item"><span>Lead Source</span><strong>{safe(lead.get("source"))}</strong></div>
        <div class="item"><span>Payment Status</span><strong>{safe(payment_status)}</strong></div>
      </div>
    </section>

    <section class="panel">
      <h3>Fee & International Information</h3>
      {financial_html}
    </section>

    <section class="panel">
      <h3>Original Admission Enquiry</h3>
      <div class="message">{safe(lead.get("message")) or "No enquiry message recorded."}</div>
      <h3 style="margin-top:20px">Follow-up Notes</h3>
      <div class="message">{safe(lead.get("follow_up_notes")) or "No follow-up notes recorded."}</div>
    </section>

    <section class="panel">
      <h3>Activity Timeline</h3>
      <div class="timeline">{activity_html}</div>
    </section>
  </div>

  <div>
    <section class="panel">
      <h3>CRM Management</h3>
      <form method="post" action="/update-lead">
        <input type="hidden" name="lead_id" value="{lead_id}">

        <div class="edit-grid">
          <div>
            <label>Status</label>
            <select name="status">{status_options(status)}</select>
          </div>
          <div>
            <label>Payment Status</label>
            <select name="payment_status">{payment_options(payment_status)}</select>
          </div>
          <div>
            <label>Lead Source</label>
            <select name="source">{source_options(source)}</select>
          </div>
          <div>
            <label>Assigned Counsellor</label>
            <input name="assigned_counsellor" value="{safe(lead.get("assigned_counsellor"))}"
                   placeholder="Counsellor name">
          </div>
          <div>
            <label>Follow-up Date</label>
            <input type="date" name="follow_up_date" value="{safe(lead.get("follow_up_date"))}">
          </div>
          <div>
            <label>Follow-up Time</label>
            <input type="time" name="follow_up_time" value="{safe(lead.get("follow_up_time"))}">
          </div>
          <div class="full">
            <label>Follow-up Notes</label>
            <textarea name="follow_up_notes" placeholder="Add counselling or follow-up notes">{safe(lead.get("follow_up_notes"))}</textarea>
          </div>
        </div>

        <div class="actions">
          <button type="submit">Save CRM Changes</button>
          <a href="/">Cancel</a>
        </div>
      </form>
    </section>

    <section class="panel">
      <h3>Record Information</h3>
      <div class="item"><span>Created</span><strong>{safe(lead.get("created_at"))}</strong></div>
      <div class="item"><span>Last Updated</span><strong>{safe(lead.get("updated_at"))}</strong></div>
      <div class="item"><span>Last Contacted</span><strong>{safe(lead.get("last_contacted_at")) or "Not contacted yet"}</strong></div>
      <p class="muted" style="margin-top:14px">
        This profile reads from the same leads.json used by the Sayyed EdVantage AI Agent.
      </p>
    </section>
  </div>
</div>
</main>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[CRM] {self.address_string()} - {fmt % args}")

    def send_html(self, content, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            self.send_html(dashboard_page(
                get_all_leads(),
                params.get("q", [""])[0],
                params.get("status", [""])[0],
                params.get("country", [""])[0],
                params.get("course", [""])[0],
                params.get("message", [""])[0],
            ))
            return

        if parsed.path == "/follow-ups":
            self.send_html(
                followups_page(
                    get_all_leads(),
                    params.get("filter", ["today"])[0],
                    params.get("message", [""])[0],
                )
            )
            return

        if parsed.path == "/lead":
            lead = get_lead(params.get("id", [""])[0])
            self.send_html(
                lead_details_page(
                    lead,
                    params.get("message", [""])[0],
                ),
                200 if lead else 404,
            )
            return

        self.send_html("<h1>404 - Not Found</h1>", 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/update-lead":
            self.send_html("<h1>404 - Not Found</h1>", 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = parse_qs(body)

            lead_id = data.get("lead_id", [""])[0].strip()
            lead = get_lead(lead_id)

            if not lead:
                self.send_html("<h1>Lead not found</h1>", 404)
                return

            updates = {
                "status": data.get("status", [lead.get("status", "New")])[0],
                "payment_status": data.get(
                    "payment_status", [lead.get("payment_status", "Not Started")]
                )[0],
                "source": data.get("source", [lead.get("source", "Other")])[0],
                "follow_up_date": data.get("follow_up_date", [""])[0],
                "follow_up_time": data.get("follow_up_time", [""])[0],
                "assigned_counsellor": data.get("assigned_counsellor", [""])[0].strip(),
                "follow_up_notes": data.get("follow_up_notes", [""])[0].strip(),
            }

            if updates["status"] in {"Contacted", "Counselling", "Interested", "Application", "Payment Pending", "Enrolled"}:
                updates["last_contacted_at"] = datetime.now().isoformat(timespec="seconds")

            update_lead(lead_id, **updates)
            self.redirect("/?message=Lead+updated+successfully")

        except Exception as exc:
            self.send_html(
                f"<h1>Server error</h1><pre>{safe(exc)}</pre>",
                500,
            )


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 65)
    print("Sayyed EdVantage Admissions CRM v3")
    print(f"Dashboard: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    print("=" * 65)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Lead Manager...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()