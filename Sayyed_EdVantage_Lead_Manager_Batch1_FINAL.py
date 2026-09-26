from __future__ import annotations

import html
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.leads.lead_manager import (
    get_all_leads,
    get_lead,
    update_lead,
    add_counselling_session,
    get_counselling_history,
    add_follow_up_action,
    get_follow_up_history,
    set_fee_details,
    get_payment_summary,
    record_payment,
    get_payment_history,
    PAYMENT_MODES,
    PAYMENT_STATUSES as LEAD_PAYMENT_STATUSES,
    COUNSELLING_OUTCOMES,
    COUNSELLING_MODES,
)

# Step 2: connect the existing Follow-up Manager page to this main CRM server.
from Sayyed_EdVantage_Lead_Manager_FOLLOWUPS import followups_page


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

PAYMENT_STATUSES = list(LEAD_PAYMENT_STATUSES)

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


def parse_decimal(value, default=Decimal("0")):
    try:
        if value is None or str(value).strip() == "":
            return default
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def money_value(value):
    amount = parse_decimal(value)
    return float(amount)


def valid_date(value):
    value = str(value or "").strip()
    if not value:
        return True
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def valid_time(value):
    value = str(value or "").strip()
    if not value:
        return True
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def filtered_leads(
    leads,
    q="",
    name="",
    lead_id="",
    phone="",
    email="",
    status="",
    country="",
    course="",
    payment_status="",
    source="",
    counsellor="",
    created_date="",
    follow_up_date="",
):
    filters = {
        "q": str(q or "").strip().lower(),
        "name": str(name or "").strip().lower(),
        "lead_id": str(lead_id or "").strip().lower(),
        "phone": str(phone or "").strip().lower(),
        "email": str(email or "").strip().lower(),
        "status": str(status or "").strip().lower(),
        "country": str(country or "").strip().lower(),
        "course": str(course or "").strip().lower(),
        "payment_status": str(payment_status or "").strip().lower(),
        "source": str(source or "").strip().lower(),
        "counsellor": str(counsellor or "").strip().lower(),
        "created_date": str(created_date or "").strip(),
        "follow_up_date": str(follow_up_date or "").strip(),
    }

    result = []

    for lead in leads:
        if not isinstance(lead, dict):
            continue

        if filters["status"] and str(lead.get("status", "")).strip().lower() != filters["status"]:
            continue
        if filters["payment_status"] and str(lead.get("payment_status", "")).strip().lower() != filters["payment_status"]:
            continue
        if filters["country"] and str(lead.get("country", "")).strip().lower() != filters["country"]:
            continue
        if filters["source"] and str(lead.get("source", "")).strip().lower() != filters["source"]:
            continue
        if filters["counsellor"] and str(lead.get("assigned_counsellor", "")).strip().lower() != filters["counsellor"]:
            continue
        if filters["course"] and filters["course"] not in str(lead.get("course_interest", "")).lower():
            continue
        if filters["name"] and filters["name"] not in str(lead.get("name", "")).lower():
            continue
        if filters["lead_id"] and filters["lead_id"] not in str(lead.get("lead_id", "")).lower():
            continue
        if filters["phone"] and filters["phone"] not in str(lead.get("phone", "")).lower():
            continue
        if filters["email"] and filters["email"] not in str(lead.get("email", "")).lower():
            continue
        if filters["created_date"] and not str(lead.get("created_at", "")).startswith(filters["created_date"]):
            continue
        if filters["follow_up_date"] and str(lead.get("follow_up_date", "")).strip() != filters["follow_up_date"]:
            continue

        if filters["q"]:
            searchable = " ".join(
                str(lead.get(k, ""))
                for k in (
                    "lead_id", "name", "phone", "email", "country",
                    "course_interest", "education", "source",
                    "assigned_counsellor", "follow_up_notes",
                )
            ).lower()
            if filters["q"] not in searchable:
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


def counselling_outcome_options(selected="Pending"):
    return option_list(COUNSELLING_OUTCOMES, selected)


def counselling_mode_options(selected="Phone"):
    return option_list(COUNSELLING_MODES, selected)


def navigation_html(active="dashboard"):
    links = [
        ("dashboard", "/", "Lead Manager"),
        ("counselling", "/counselling", "Counselling Manager"),
        ("followups", "/follow-ups", "Follow-up Manager"),
    ]
    return "".join(
        f'<a class="nav-link {"active" if key == active else ""}" href="{href}">{label}</a>'
        for key, href, label in links
    )


def dashboard_page(
    leads,
    q="",
    name="",
    lead_id="",
    phone="",
    email="",
    status="",
    country="",
    course="",
    payment_status="",
    source="",
    counsellor="",
    created_date="",
    follow_up_date="",
    message="",
):
    filtered = filtered_leads(
        leads, q, name, lead_id, phone, email, status, country, course,
        payment_status, source, counsellor, created_date, follow_up_date
    )

    status_counts = {s: 0 for s in STATUSES}
    payment_counts = {s: 0 for s in PAYMENT_STATUSES}
    source_counts = {}
    total_final_fee = Decimal("0")
    total_paid = Decimal("0")
    total_balance = Decimal("0")

    today = datetime.now().date().isoformat()
    followups_today = 0
    overdue_followups = 0
    upcoming_followups = 0
    international = 0

    for lead in leads:
        if not isinstance(lead, dict):
            continue

        st = str(lead.get("status", "New")).strip() or "New"
        ps = str(lead.get("payment_status", "Not Started")).strip() or "Not Started"
        src = str(lead.get("source", "Other")).strip() or "Other"

        status_counts[st] = status_counts.get(st, 0) + 1
        payment_counts[ps] = payment_counts.get(ps, 0) + 1
        source_counts[src] = source_counts.get(src, 0) + 1

        total_final_fee += parse_decimal(lead.get("final_fee"))
        total_paid += parse_decimal(lead.get("total_paid"))
        total_balance += parse_decimal(lead.get("balance_amount"))

        if lead.get("international_student"):
            international += 1

        follow_up = str(lead.get("follow_up_date", "")).strip()
        if follow_up == today:
            followups_today += 1
        elif follow_up and follow_up < today:
            overdue_followups += 1
        elif follow_up and follow_up > today:
            upcoming_followups += 1

    enrolled = status_counts.get("Enrolled", 0)
    conversion = round((enrolled / len(leads)) * 100, 1) if leads else 0
    countries = unique_values(leads, "country")
    courses = unique_values(leads, "course_interest")
    counsellors = unique_values(leads, "assigned_counsellor")
    created_dates = sorted(
        {
            str(l.get("created_at", ""))[:10]
            for l in leads
            if isinstance(l, dict) and str(l.get("created_at", ""))[:10]
        },
        reverse=True,
    )

    def pipeline_link(label, count):
        target = "" if label == "All" else label
        return (
            f'<a class="pipeline-row" href="/?status={safe(target)}">'
            f'<span>{safe(label)}</span><b>{count}</b></a>'
        )

    pipeline = pipeline_link("All", len(leads)) + "".join(
        pipeline_link(s, status_counts.get(s, 0)) for s in STATUSES
    )

    source_summary = "".join(
        f'<div class="mini"><span>{safe(k)}</span><b>{v}</b></div>'
        for k, v in sorted(source_counts.items(), key=lambda x: (-x[1], x[0].lower()))
    ) or '<div class="muted">No source data yet.</div>'

    rows = []
    for lead in filtered:
        lid = str(lead.get("lead_id", ""))
        current_status = str(lead.get("status", "New"))
        current_payment = str(lead.get("payment_status", "Not Started"))
        current_source = str(lead.get("source", "Other"))

        rows.append(f"""
        <tr>
          <td><strong>{safe(lid)}</strong></td>
          <td>
            <strong>{safe(lead.get("name"))}</strong><br>
            <small>{safe(lead.get("phone"))}</small>
          </td>
          <td>{safe(lead.get("email"))}</td>
          <td>
            {safe(lead.get("country"))}<br>
            <small>{safe(lead.get("course_interest"))}</small>
          </td>
          <td>{safe(current_status)}</td>
          <td>{safe(current_payment)}</td>
          <td>{safe(lead.get("assigned_counsellor")) or "—"}</td>
          <td>{safe(lead.get("follow_up_date")) or "—"} {safe(lead.get("follow_up_time"))}</td>
          <td>
            <form method="post" action="/update-lead" class="quick-edit">
              <input type="hidden" name="lead_id" value="{safe(lid)}">
              <select name="status">{status_options(current_status)}</select>
              <select name="payment_status">{payment_options(current_payment)}</select>
              <button type="submit">Save</button>
            </form>
            <a class="details" href="/lead?id={safe(lid)}">Open full profile →</a>
          </td>
        </tr>
        """)

    table = "".join(rows) or '<tr><td colspan="9" class="empty">No leads match the selected filters.</td></tr>'

    status_filter = '<option value="">All statuses</option>' + option_list(STATUSES, status)
    payment_filter = '<option value="">All payment statuses</option>' + option_list(PAYMENT_STATUSES, payment_status)
    country_filter = '<option value="">All countries</option>' + option_list(countries, country)
    course_filter = '<option value="">All courses</option>' + option_list(courses, course)
    source_filter = '<option value="">All sources</option>' + option_list(SOURCES, source)
    counsellor_filter = '<option value="">All counsellors</option>' + option_list(counsellors, counsellor)
    created_filter = '<option value="">Any created date</option>' + option_list(created_dates, created_date)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sayyed EdVantage — Admissions CRM</title>
<style>
:root{{--blue:#1769aa;--dark:#14213d;--bg:#f4f7fb;--border:#dfe5ee;--muted:#697586;--white:#fff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:#172033;font-family:Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(135deg,var(--dark),var(--blue));color:#fff;padding:24px 34px}}
header h1{{margin:0 0 5px;font-size:28px}} header p{{margin:0;opacity:.85}}
nav{{background:#fff;border-bottom:1px solid var(--border);padding:10px 34px;display:flex;gap:8px;flex-wrap:wrap}}
.nav-link{{padding:8px 13px;border-radius:8px;text-decoration:none;color:var(--blue);font-weight:600;border:1px solid transparent}}
.nav-link.active{{background:var(--blue);color:#fff}}
main{{max-width:1650px;margin:auto;padding:24px 30px}}
.notice{{background:#eef8f0;border:1px solid #b9dfc0;padding:10px 12px;border-radius:8px;margin-bottom:15px;color:#17633f}}
.cards{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}}
.card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:15px}}
.card span{{font-size:11px;color:var(--muted)}} .card strong{{display:block;font-size:24px;margin-top:5px;color:var(--dark)}}
.card.money strong{{font-size:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px}}
.panel{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:17px}}
.panel h2{{font-size:16px;margin:0 0 12px}}
.pipeline-row{{display:flex;justify-content:space-between;padding:7px 5px;border-bottom:1px solid #eef1f5;font-size:13px;text-decoration:none;color:#172033;border-radius:5px}}
.pipeline-row:hover{{background:#f5f9fd;color:var(--blue)}}
.pipeline-row b{{color:var(--blue)}}
.mini{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eef1f5;font-size:13px}}
.filters{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:15px;margin-bottom:18px}}
.filters h2{{margin:0 0 12px;font-size:16px}}
.filter-grid{{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px}}
.filter-grid input,.filter-grid select,button{{width:100%;border:1px solid #cbd3df;border-radius:8px;padding:9px 10px;font-size:13px;background:#fff}}
.filter-actions{{display:flex;gap:8px;margin-top:9px}}
button{{background:var(--blue);color:#fff;border-color:var(--blue);cursor:pointer;font-weight:600}}
.clear{{display:inline-flex;align-items:center;padding:9px 12px;color:var(--blue);text-decoration:none;border:1px solid var(--border);border-radius:8px}}
.table-wrap{{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:auto}}
table{{width:100%;border-collapse:collapse;min-width:1350px}}
th,td{{padding:10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;font-size:12px}}
th{{background:#f8f9fc;color:#4e5a6c;position:sticky;top:0;z-index:1}}
.quick-edit{{display:flex;gap:5px;min-width:330px}}
.quick-edit select{{width:145px;padding:7px;border:1px solid #cbd3df;border-radius:7px}}
.quick-edit button{{width:65px;padding:7px}}
.details{{display:inline-block;margin-top:7px;color:var(--blue);text-decoration:none;font-weight:600}}
small,.muted{{color:var(--muted)}}
.empty{{text-align:center;padding:35px;color:var(--muted)}}
.metric-note{{margin-top:7px;font-size:11px;color:var(--muted)}}
@media(max-width:1100px){{.cards{{grid-template-columns:repeat(3,1fr)}}.filter-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:700px){{.cards,.grid,.filter-grid{{grid-template-columns:1fr}}main{{padding:18px}}}}
</style>
</head>
<body>
<header><h1>Sayyed EdVantage</h1><p>Admissions CRM & Lead Manager</p></header>
<nav>{navigation_html("dashboard")}</nav>
<main>
{f'<div class="notice">{safe(message)}</div>' if message else ''}

<div class="cards">
  <div class="card"><span>Total Leads</span><strong>{len(leads)}</strong></div>
  <div class="card"><span>New</span><strong>{status_counts.get("New",0)}</strong></div>
  <div class="card"><span>Interested</span><strong>{status_counts.get("Interested",0)}</strong></div>
  <div class="card"><span>Enrolled</span><strong>{enrolled}</strong></div>
  <div class="card"><span>Follow-ups Today</span><strong>{followups_today}</strong></div>
  <div class="card"><span>Overdue</span><strong>{overdue_followups}</strong></div>
  <div class="card"><span>Upcoming</span><strong>{upcoming_followups}</strong></div>
  <div class="card"><span>International</span><strong>{international}</strong></div>
  <div class="card"><span>Conversion</span><strong>{conversion}%</strong></div>
  <div class="card money"><span>Total Final Fees</span><strong>{total_final_fee:,.2f}</strong><div class="metric-note">Across lead records</div></div>
  <div class="card money"><span>Total Collected</span><strong>{total_paid:,.2f}</strong><div class="metric-note">Across lead records</div></div>
  <div class="card money"><span>Total Outstanding</span><strong>{total_balance:,.2f}</strong><div class="metric-note">Across lead records</div></div>
</div>

<div class="grid">
  <section class="panel"><h2>Admission Pipeline</h2>{pipeline}</section>
  <section class="panel">
    <h2>Lead Sources</h2>{source_summary}
    <div class="metric-note">Payment status: {", ".join(f"{k}: {v}" for k,v in payment_counts.items() if v) or "No payment data"}</div>
  </section>
</div>

<section class="filters">
<h2>Advanced Search & Filters</h2>
<form method="get" action="/">
<div class="filter-grid">
  <input name="q" value="{safe(q)}" placeholder="Global search">
  <input name="name" value="{safe(name)}" placeholder="Student name">
  <input name="lead_id" value="{safe(lead_id)}" placeholder="Lead ID">
  <input name="phone" value="{safe(phone)}" placeholder="Phone">
  <input name="email" value="{safe(email)}" placeholder="Email">
  <select name="course">{course_filter}</select>
  <select name="country">{country_filter}</select>
  <select name="status">{status_filter}</select>
  <select name="payment_status">{payment_filter}</select>
  <select name="source">{source_filter}</select>
  <select name="counsellor">{counsellor_filter}</select>
  <select name="created_date">{created_filter}</select>
  <input type="date" name="follow_up_date" value="{safe(follow_up_date)}" title="Follow-up date">
</div>
<div class="filter-actions">
  <button type="submit">Search / Filter</button>
  <a class="clear" href="/">Clear All</a>
</div>
</form>
</section>

<section class="table-wrap">
<table>
<thead><tr>
<th>Lead ID</th><th>Student</th><th>Email</th><th>Country / Course</th>
<th>Status</th><th>Payment</th><th>Counsellor</th><th>Follow-up</th><th>Quick Actions</th>
</tr></thead>
<tbody>{table}</tbody>
</table>
</section>

<p class="muted" style="margin-top:12px">
Showing {len(filtered)} of {len(leads)} leads. Data is stored in the same leads.json used by the AI Agent.
</p>
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
    base_fee = lead.get("base_fee", 0.0)
    discount = lead.get("discount", 0.0)
    final_fee = lead.get("final_fee", 0.0)
    total_paid = lead.get("total_paid", 0.0)
    balance_amount = lead.get("balance_amount", 0.0)
    currency = lead.get("currency", "INR")
    converted = lead.get("converted_amount", 0.0)
    payment_mode = lead.get("payment_mode", "")
    transaction_id = lead.get("transaction_id", "")
    payment_date = lead.get("payment_date", "")
    payment_history = get_payment_history(lead_id_raw)

    # Load counselling and follow-up history BEFORE building the activity timeline.
    counselling_history = get_counselling_history(lead_id_raw)
    followup_history = get_follow_up_history(lead_id_raw)

    activity = []
    created = lead.get("created_at")
    updated = lead.get("updated_at")
    last_contacted = lead.get("last_contacted_at")

    def activity_sort_key(item):
        value = str(item[1] or "")
        return value

    if created:
        activity.append(("Lead created", created, "AI Agent / CRM"))

    if last_contacted:
        activity.append(("Student contacted / stage progressed", last_contacted, "CRM"))

    if updated and updated != created and updated != last_contacted:
        activity.append(("Lead record updated", updated, "CRM"))

    for session in counselling_history:
        if not isinstance(session, dict):
            continue
        session_date = str(session.get("counselling_date", "")).strip()
        session_time = str(session.get("counselling_time", "")).strip()
        event_time = f"{session_date}T{session_time}" if session_date else str(session.get("created_at", ""))
        outcome = str(session.get("outcome", "Pending"))
        counsellor_name = str(session.get("counsellor", "")).strip() or "Unassigned"
        activity.append((
            f"Counselling session — {outcome}",
            event_time,
            f"Counsellor: {counsellor_name}"
        ))

    for action in followup_history:
        if not isinstance(action, dict):
            continue
        action_time = str(action.get("action_at", ""))
        outcome = str(action.get("outcome", "Contacted"))
        counsellor_name = str(action.get("counsellor", "")).strip() or "Unassigned"
        activity.append((
            f"Follow-up completed — {outcome}",
            action_time,
            f"Counsellor: {counsellor_name}"
        ))

    for payment in payment_history:
        if not isinstance(payment, dict):
            continue
        payment_date = str(payment.get("payment_date", "")).strip()
        payment_time = str(payment.get("payment_at", "")).strip()
        event_time = f"{payment_date}T{payment_time}" if payment_time else payment_date
        activity.append((
            f"Payment recorded — {safe(payment.get('amount'))} {safe(currency)}",
            event_time,
            str(payment.get("payment_mode", "Payment"))
        ))

    activity.sort(key=activity_sort_key, reverse=True)

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

    if followup_history:
        followup_rows = []
        for action in reversed(followup_history):
            next_follow = str(action.get("next_follow_up_date", ""))
            if action.get("next_follow_up_time"):
                next_follow = f"{next_follow} {action.get('next_follow_up_time')}".strip()
            followup_rows.append(
                f'<tr><td>{safe(action.get("action_at"))}</td>'
                f'<td>{safe(action.get("counsellor"))}</td>'
                f'<td>{safe(action.get("outcome"))}</td>'
                f'<td>{safe(action.get("notes")) or "—"}</td>'
                f'<td>{safe(next_follow) or "—"}</td></tr>'
            )
        followup_history_html = (
            '<div class="table-wrap"><table style="width:100%;border-collapse:collapse">'
            '<thead><tr><th>Date / Time</th><th>Counsellor</th><th>Outcome</th><th>Notes</th><th>Next Follow-up</th></tr></thead>'
            '<tbody>' + "".join(followup_rows) + '</tbody></table></div>'
        )
    else:
        followup_history_html = '<div class="message">No follow-up actions recorded yet.</div>'

    payment_rows = []
    for payment in reversed(payment_history):
        payment_rows.append(
            f'<tr><td>{safe(payment.get("payment_id"))}</td>'
            f'<td>{safe(payment.get("payment_date"))}</td>'
            f'<td>{safe(payment.get("amount"))} {safe(currency)}</td>'
            f'<td>{safe(payment.get("payment_mode"))}</td>'
            f'<td>{safe(payment.get("transaction_id")) or "—"}</td>'
            f'<td>{safe(payment.get("notes")) or "—"}</td></tr>'
        )

    payment_history_html = (
        '<div class="table-wrap"><table style="width:100%;border-collapse:collapse">'
        '<thead><tr><th>Payment ID</th><th>Payment Date</th><th>Amount</th><th>Payment Mode</th><th>Transaction / Reference ID</th><th>Notes</th></tr></thead>'
        '<tbody>' + ''.join(payment_rows) + '</tbody></table></div>'
        if payment_rows else '<div class="message">No payments recorded yet.</div>'
    )

    converted_display = (
        f"{safe(converted)} {safe(currency)}"
        if converted not in (None, "", 0, 0.0, "0", "0.0")
        else "Not set"
    )

    lead_overview_html = f'''
    <div class="lead-overview">
      <div>
        <span>Current Status</span>
        <strong>{safe(status)}</strong>
      </div>
      <div>
        <span>Payment Status</span>
        <strong>{safe(payment_status)}</strong>
      </div>
      <div>
        <span>Counselling Sessions</span>
        <strong>{len(counselling_history)}</strong>
      </div>
      <div>
        <span>Follow-up Actions</span>
        <strong>{len(followup_history)}</strong>
      </div>
      <div>
        <span>Balance Due</span>
        <strong>{safe(balance_amount)} {safe(currency)}</strong>
      </div>
    </div>
    '''

    financial_html = f'''
    <div class="finance-grid">
      <div class="finance-card">
        <span>Student Type</span>
        <strong>{"International" if international else "Indian"}</strong>
      </div>
      <div class="finance-card">
        <span>Base Fee</span>
        <strong>{safe(base_fee)} {safe(currency)}</strong>
      </div>
      <div class="finance-card">
        <span>Discount</span>
        <strong>{safe(discount)} {safe(currency)}</strong>
      </div>
      <div class="finance-card highlight">
        <span>Final Fee</span>
        <strong>{safe(final_fee)} {safe(currency)}</strong>
      </div>
      <div class="finance-card paid-card">
        <span>Total Paid</span>
        <strong>{safe(total_paid)} {safe(currency)}</strong>
      </div>
      <div class="finance-card balance-card">
        <span>Balance Due</span>
        <strong>{safe(balance_amount)} {safe(currency)}</strong>
      </div>
      <div class="finance-card status-card">
        <span>Payment Status</span>
        <strong>{safe(payment_status)}</strong>
      </div>
      <div class="finance-card">
        <span>Converted Amount</span>
        <strong>{converted_display}</strong>
      </div>
    </div>

    <div class="fee-flow">
      <div class="fee-flow-step">
        <span>Base Fee</span>
        <strong>{safe(base_fee)} {safe(currency)}</strong>
      </div>
      <div class="fee-flow-arrow">−</div>
      <div class="fee-flow-step">
        <span>Discount</span>
        <strong>{safe(discount)} {safe(currency)}</strong>
      </div>
      <div class="fee-flow-arrow">=</div>
      <div class="fee-flow-step final">
        <span>Final Fee</span>
        <strong>{safe(final_fee)} {safe(currency)}</strong>
      </div>
      <div class="fee-flow-arrow">−</div>
      <div class="fee-flow-step">
        <span>Total Paid</span>
        <strong>{safe(total_paid)} {safe(currency)}</strong>
      </div>
      <div class="fee-flow-arrow">=</div>
      <div class="fee-flow-step balance">
        <span>Balance</span>
        <strong>{safe(balance_amount)} {safe(currency)}</strong>
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
.nav-link{{padding:8px 13px;border-radius:8px;text-decoration:none;color:#1769aa;font-weight:600;border:1px solid transparent}}
.nav-link.active{{background:#1769aa;color:#fff}}
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
.finance-card.paid-card{{border-color:#c8e6d0;background:#f3fbf5}}
.finance-card.balance-card{{border-color:#f0d6a0;background:#fffaf0}}
.finance-card.status-card{{border-color:#d8c9ef;background:#faf7ff}}
.fee-flow{{display:flex;align-items:stretch;gap:6px;margin-top:14px;padding:12px;background:#f8fafc;border:1px solid var(--border);border-radius:10px;overflow:auto}}
.fee-flow-step{{min-width:115px;flex:1;border:1px solid var(--border);background:#fff;border-radius:8px;padding:9px;text-align:center}}
.fee-flow-step span{{display:block;color:var(--muted);font-size:10px;margin-bottom:4px}}
.fee-flow-step strong{{font-size:13px;color:var(--dark)}}
.fee-flow-step.final{{border-color:#b7d5ef;background:#f1f8ff}}
.fee-flow-step.balance{{border-color:#f0d6a0;background:#fffaf0}}
.fee-flow-arrow{{display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;color:var(--muted);min-width:20px}}
.payment-summary{{margin-top:12px}}
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
<nav style="background:#fff;border-bottom:1px solid #dfe5ee;padding:10px 34px;display:flex;gap:8px;flex-wrap:wrap">
{navigation_html("dashboard")}
</nav>

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
      <div class="section-heading-row">
        <h3>Counselling History</h3>
        <div class="quick-links">
          <a href="/counselling">Counselling Manager</a>
          <a href="/follow-ups">Follow-up Manager</a>
        </div>
      </div>
      {(
        '<div class="table-wrap"><table style="width:100%;border-collapse:collapse">'
        '<thead><tr><th>Date</th><th>Time</th><th>Counsellor</th><th>Mode</th><th>Outcome</th><th>Notes</th><th>Next Follow-up</th></tr></thead><tbody>'
        + "".join(
            f'<tr><td>{safe(s.get("counselling_date"))}</td>'
            f'<td>{safe(s.get("counselling_time"))}</td>'
            f'<td>{safe(s.get("counsellor"))}</td>'
            f'<td>{safe(s.get("mode"))}</td>'
            f'<td>{safe(s.get("outcome"))}</td>'
            f'<td>{safe(s.get("notes"))}</td>'
            f'<td>{safe(s.get("next_follow_up_date"))} {safe(s.get("next_follow_up_time"))}</td></tr>'
            for s in get_counselling_history(lead_id_raw)
            if isinstance(s, dict)
        )
        + '</tbody></table></div>'
        if get_counselling_history(lead_id_raw)
        else '<div class="message">No counselling sessions recorded yet.</div>'
      )}
    </section>

    <section class="panel">
      <h3>New Counselling Session</h3>
      <form method="post" action="/add-counselling">
        <input type="hidden" name="lead_id" value="{lead_id}">
        <div class="edit-grid">
          <div>
            <label>Counsellor</label>
            <input name="counsellor" value="{safe(lead.get("assigned_counsellor"))}" placeholder="Counsellor name">
          </div>
          <div>
            <label>Counselling Mode</label>
            <select name="mode">{counselling_mode_options("Phone")}</select>
          </div>
          <div>
            <label>Counselling Date</label>
            <input type="date" name="counselling_date" value="{safe(datetime.now().date().isoformat())}">
          </div>
          <div>
            <label>Counselling Time</label>
            <input type="time" name="counselling_time">
          </div>
          <div>
            <label>Outcome</label>
            <select name="outcome">{counselling_outcome_options("Pending")}</select>
          </div>
          <div>
            <label>Next Follow-up Date</label>
            <input type="date" name="next_follow_up_date">
          </div>
          <div>
            <label>Next Follow-up Time</label>
            <input type="time" name="next_follow_up_time">
          </div>
          <div class="full">
            <label>Counselling Notes</label>
            <textarea name="notes" placeholder="Record the student's requirements, questions, objections, counselling discussion and next action"></textarea>
          </div>
        </div>
        <div class="actions">
          <button type="submit">Save Counselling Session</button>
        </div>
      </form>
    </section>

    <section class="panel" id="followup-history">
      <h3>Follow-up History</h3>
      {followup_history_html}
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
      <h3>Payment Management</h3>
      <form method="post" action="/set-fee">
        <input type="hidden" name="lead_id" value="{lead_id}">
        <div class="edit-grid">
          <div>
            <label>Base Fee</label>
            <input type="number" step="0.01" min="0" name="base_fee" value="{safe(base_fee)}">
          </div>
          <div>
            <label>Discount</label>
            <input type="number" step="0.01" min="0" name="discount" value="{safe(discount)}">
          </div>
          <div>
            <label>Currency</label>
            <input name="currency" value="{safe(currency)}">
          </div>
          <div>
            <label>Converted Amount</label>
            <input type="number" step="0.01" min="0" name="converted_amount" value="{safe(converted)}">
          </div>
        </div>
        <div class="actions"><button type="submit">Save Fee Details</button></div>
      </form>

      <hr style="border:0;border-top:1px solid #edf0f4;margin:20px 0">

      <div class="payment-summary">
        <div class="finance-grid">
          <div class="finance-card">
            <span>Final Fee</span>
            <strong>{safe(final_fee)} {safe(currency)}</strong>
          </div>
          <div class="finance-card paid-card">
            <span>Already Paid</span>
            <strong>{safe(total_paid)} {safe(currency)}</strong>
          </div>
          <div class="finance-card balance-card">
            <span>Remaining Balance</span>
            <strong>{safe(balance_amount)} {safe(currency)}</strong>
          </div>
          <div class="finance-card status-card">
            <span>Current Status</span>
            <strong>{safe(payment_status)}</strong>
          </div>
        </div>
      </div>

      <form method="post" action="/record-payment">
        <input type="hidden" name="lead_id" value="{lead_id}">
        <div class="edit-grid">
          <div>
            <label>Payment Amount</label>
            <input type="number" step="0.01" min="0" name="amount" required>
          </div>
          <div>
            <label>Payment Mode</label>
            <select name="payment_mode">
              {option_list(PAYMENT_MODES, payment_mode or "Online")}
            </select>
          </div>
          <div>
            <label>Transaction / Reference ID</label>
            <input name="transaction_id" value="{safe(transaction_id)}">
          </div>
          <div>
            <label>Payment Date</label>
            <input type="date" name="payment_date" value="{safe(payment_date or datetime.now().date().isoformat())}">
          </div>
          <div class="full">
            <label>Payment Notes</label>
            <textarea name="notes" placeholder="Payment remarks, receipt details, etc."></textarea>
          </div>
        </div>
        <div class="actions"><button type="submit">Record Payment</button></div>
      </form>

      <h3 style="margin-top:22px">Payment History</h3>
      {payment_history_html}
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
                params.get("name", [""])[0],
                params.get("lead_id", [""])[0],
                params.get("phone", [""])[0],
                params.get("email", [""])[0],
                params.get("status", [""])[0],
                params.get("country", [""])[0],
                params.get("course", [""])[0],
                params.get("payment_status", [""])[0],
                params.get("source", [""])[0],
                params.get("counsellor", [""])[0],
                params.get("created_date", [""])[0],
                params.get("follow_up_date", [""])[0],
                params.get("message", [""])[0],
            ))
            return

        if parsed.path == "/counselling":
            self.send_html(
                counselling_page(
                    get_all_leads(),
                    params.get("q", [""])[0],
                    params.get("counsellor", [""])[0],
                    params.get("outcome", [""])[0],
                    params.get("date", [""])[0],
                    params.get("message", [""])[0],
                )
            )
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

        if parsed.path == "/follow-up-action":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = parse_qs(body)

                lead_id = data.get("lead_id", [""])[0].strip()
                lead = get_lead(lead_id)

                if not lead:
                    self.send_html("<h1>Lead not found</h1>", 404)
                    return

                follow_outcome = data.get("outcome", ["Contacted"])[0].strip()
                next_follow_date = data.get("next_follow_up_date", [""])[0].strip()
                next_follow_time = data.get("next_follow_up_time", [""])[0].strip()

                if not valid_date(next_follow_date) or not valid_time(next_follow_time):
                    self.send_html("<h1>Invalid next follow-up date/time</h1><p>Use YYYY-MM-DD and HH:MM.</p>", 400)
                    return
                if not follow_outcome:
                    self.send_html("<h1>Follow-up outcome is required</h1>", 400)
                    return

                action = add_follow_up_action(
                    lead_id=lead_id,
                    outcome=follow_outcome,
                    notes=data.get("notes", [""])[0].strip(),
                    next_follow_up_date=next_follow_date,
                    next_follow_up_time=next_follow_time,
                    counsellor=data.get("counsellor", [""])[0].strip(),
                )

                if not action:
                    self.send_html("<h1>Unable to save follow-up action</h1>", 500)
                    return

                self.redirect("/follow-ups?filter=today&message=Follow-up+saved+successfully")
            except Exception as exc:
                self.send_html(
                    f"<h1>Server error</h1><pre>{safe(exc)}</pre>",
                    500,
                )
            return

        if parsed.path == "/add-counselling":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = parse_qs(body)

                lead_id = data.get("lead_id", [""])[0].strip()
                if not get_lead(lead_id):
                    self.send_html("<h1>Lead not found</h1>", 404)
                    return

                counselling_date = data.get("counselling_date", [""])[0].strip()
                counselling_time = data.get("counselling_time", [""])[0].strip()
                next_date = data.get("next_follow_up_date", [""])[0].strip()
                next_time = data.get("next_follow_up_time", [""])[0].strip()
                mode = data.get("mode", ["Phone"])[0].strip()
                outcome = data.get("outcome", ["Pending"])[0].strip()

                if not valid_date(counselling_date) or not valid_time(counselling_time):
                    self.send_html("<h1>Invalid counselling date/time</h1><p>Use YYYY-MM-DD and HH:MM.</p>", 400)
                    return
                if not valid_date(next_date) or not valid_time(next_time):
                    self.send_html("<h1>Invalid next follow-up date/time</h1><p>Use YYYY-MM-DD and HH:MM.</p>", 400)
                    return
                if mode not in COUNSELLING_MODES:
                    self.send_html("<h1>Invalid counselling mode</h1>", 400)
                    return
                if outcome not in COUNSELLING_OUTCOMES:
                    self.send_html("<h1>Invalid counselling outcome</h1>", 400)
                    return

                session = add_counselling_session(
                    lead_id=lead_id,
                    counsellor=data.get("counsellor", [""])[0].strip(),
                    counselling_date=counselling_date,
                    counselling_time=counselling_time,
                    mode=mode,
                    outcome=outcome,
                    notes=data.get("notes", [""])[0].strip(),
                    next_follow_up_date=next_date,
                    next_follow_up_time=next_time,
                )

                if not session:
                    self.send_html("<h1>Unable to save counselling session</h1>", 500)
                    return

                self.redirect(
                    f"/lead?id={lead_id}&message=Counselling+session+saved+successfully"
                )
            except Exception as exc:
                self.send_html(
                    f"<h1>Server error</h1><pre>{safe(exc)}</pre>",
                    500,
                )
            return

        if parsed.path == "/set-fee":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = parse_qs(body)
                lead_id = data.get("lead_id", [""])[0].strip()
                if not get_lead(lead_id):
                    self.send_html("<h1>Lead not found</h1>", 404)
                    return

                base_fee = parse_decimal(data.get("base_fee", ["0"])[0])
                discount = parse_decimal(data.get("discount", ["0"])[0])
                converted_amount = parse_decimal(data.get("converted_amount", ["0"])[0])
                currency = data.get("currency", ["INR"])[0].strip() or "INR"

                if base_fee < 0 or discount < 0 or converted_amount < 0:
                    self.send_html("<h1>Invalid fee details</h1><p>Fee, discount and converted amount cannot be negative.</p>", 400)
                    return
                if discount > base_fee:
                    self.send_html("<h1>Invalid discount</h1><p>Discount cannot be greater than the base fee.</p>", 400)
                    return

                result = set_fee_details(
                    lead_id=lead_id,
                    base_fee=str(base_fee),
                    discount=str(discount),
                    currency=currency,
                    converted_amount=str(converted_amount),
                )
                if not result:
                    self.send_html("<h1>Unable to save fee details</h1>", 500)
                    return
                self.redirect(f"/lead?id={lead_id}&message=Fee+details+saved+successfully")
            except Exception as exc:
                self.send_html(f"<h1>Server error</h1><pre>{safe(exc)}</pre>", 500)
            return

        if parsed.path == "/record-payment":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = parse_qs(body)
                lead_id = data.get("lead_id", [""])[0].strip()
                if not get_lead(lead_id):
                    self.send_html("<h1>Lead not found</h1>", 404)
                    return

                amount = parse_decimal(data.get("amount", ["0"])[0])
                payment_mode = data.get("payment_mode", ["Online"])[0].strip()
                payment_date = data.get("payment_date", [""])[0].strip()

                if amount <= 0:
                    self.send_html("<h1>Invalid payment amount</h1><p>Payment amount must be greater than zero.</p>", 400)
                    return
                if payment_mode not in PAYMENT_MODES:
                    self.send_html("<h1>Invalid payment mode</h1>", 400)
                    return
                if not valid_date(payment_date):
                    self.send_html("<h1>Invalid payment date</h1><p>Use YYYY-MM-DD.</p>", 400)
                    return

                current = get_lead(lead_id)
                final_fee = parse_decimal(current.get("final_fee"))
                paid = parse_decimal(current.get("total_paid"))
                balance = parse_decimal(current.get("balance_amount"))
                if balance <= 0 and final_fee > 0:
                    self.send_html("<h1>No balance due</h1><p>This lead has no outstanding balance.</p>", 400)
                    return
                if final_fee > 0 and amount > balance:
                    self.send_html(
                        f"<h1>Payment exceeds balance</h1><p>Maximum allowed payment is {balance}.</p>",
                        400,
                    )
                    return

                payment = record_payment(
                    lead_id=lead_id,
                    amount=str(amount),
                    payment_mode=payment_mode,
                    transaction_id=data.get("transaction_id", [""])[0].strip(),
                    payment_date=payment_date,
                    notes=data.get("notes", [""])[0].strip(),
                )
                if not payment:
                    self.send_html(
                        "<h1>Payment could not be recorded</h1>"
                        "<p>Check the amount, payment mode and remaining balance.</p>",
                        400,
                    )
                    return
                self.redirect(f"/lead?id={lead_id}&message=Payment+recorded+successfully")
            except Exception as exc:
                self.send_html(f"<h1>Server error</h1><pre>{safe(exc)}</pre>", 500)
            return

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
                "status": data.get("status", [lead.get("status", "New")])[0].strip(),
                "payment_status": data.get(
                    "payment_status", [lead.get("payment_status", "Not Started")]
                )[0].strip(),
                "source": data.get("source", [lead.get("source", "Other")])[0].strip(),
                "follow_up_date": data.get("follow_up_date", [""])[0].strip(),
                "follow_up_time": data.get("follow_up_time", [""])[0].strip(),
                "assigned_counsellor": data.get("assigned_counsellor", [""])[0].strip(),
                "follow_up_notes": data.get("follow_up_notes", [""])[0].strip(),
            }

            if updates["status"] not in STATUSES:
                self.send_html("<h1>Invalid lead status</h1>", 400)
                return
            if updates["payment_status"] not in PAYMENT_STATUSES:
                self.send_html("<h1>Invalid payment status</h1>", 400)
                return
            if updates["source"] not in SOURCES:
                self.send_html("<h1>Invalid lead source</h1>", 400)
                return
            if not valid_date(updates["follow_up_date"]) or not valid_time(updates["follow_up_time"]):
                self.send_html("<h1>Invalid follow-up date/time</h1><p>Use YYYY-MM-DD and HH:MM.</p>", 400)
                return

            if updates["follow_up_date"] and updates["follow_up_date"] < datetime.now().date().isoformat():
                # Historical dates are allowed for completed records, but the user should not
                # accidentally create a new overdue task without knowing it.
                if updates["status"] not in {"Enrolled", "Lost"}:
                    pass

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
    print("Sayyed EdVantage Admissions CRM v4")
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