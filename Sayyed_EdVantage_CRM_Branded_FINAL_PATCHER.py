from pathlib import Path
import ast
import shutil

SOURCE = Path("Sayyed_EdVantage_CRM_Branded.py")
OUTPUT = Path("Sayyed_EdVantage_CRM_Branded_FINAL.py")
BACKUP = Path("Sayyed_EdVantage_CRM_Branded.py.backup")

COUNSELLING_FUNCTION = '\ndef counselling_page(leads, q="", counsellor="", outcome="", date_filter="", message=""):\n    """Branded Counselling Manager dashboard using the same leads.json data."""\n    q = str(q or "").strip().lower()\n    counsellor = str(counsellor or "").strip().lower()\n    outcome = str(outcome or "").strip().lower()\n    date_filter = str(date_filter or "").strip()\n\n    sessions = []\n    counsellor_values = set()\n\n    for lead in leads:\n        if not isinstance(lead, dict):\n            continue\n\n        history = lead.get("counselling_history", [])\n        if not isinstance(history, list):\n            continue\n\n        for session in history:\n            if not isinstance(session, dict):\n                continue\n\n            item = dict(session)\n            item["_lead_id"] = str(lead.get("lead_id", ""))\n            item["_name"] = str(lead.get("name", ""))\n            item["_phone"] = str(lead.get("phone", ""))\n            item["_country"] = str(lead.get("country", ""))\n            item["_course"] = str(lead.get("course_interest", ""))\n            sessions.append(item)\n\n            counsellor_name = str(session.get("counsellor", "")).strip()\n            if counsellor_name:\n                counsellor_values.add(counsellor_name)\n\n    filtered = []\n    today = datetime.now().date().isoformat()\n\n    for session in sessions:\n        searchable = " ".join(\n            str(session.get(k, ""))\n            for k in (\n                "_lead_id", "_name", "_phone", "_country", "_course",\n                "counsellor", "mode", "outcome", "notes"\n            )\n        ).lower()\n\n        if q and q not in searchable:\n            continue\n\n        if counsellor and str(session.get("counsellor", "")).strip().lower() != counsellor:\n            continue\n\n        if outcome and str(session.get("outcome", "")).strip().lower() != outcome:\n            continue\n\n        if date_filter and str(session.get("counselling_date", "")) != date_filter:\n            continue\n\n        filtered.append(session)\n\n    filtered.sort(\n        key=lambda s: (\n            str(s.get("counselling_date", "")),\n            str(s.get("counselling_time", "")),\n            str(s.get("_name", "")).lower(),\n        ),\n        reverse=True,\n    )\n\n    today_count = sum(\n        1 for s in sessions\n        if str(s.get("counselling_date", "")) == today\n    )\n\n    pending_count = sum(\n        1 for s in sessions\n        if str(s.get("outcome", "")).strip().lower() in {"pending", "call back"}\n    )\n\n    enrolled_count = sum(\n        1 for s in sessions\n        if str(s.get("outcome", "")).strip().lower() == "enrolled"\n    )\n\n    rows = []\n\n    for session in filtered:\n        next_follow = str(\n            session.get("next_follow_up_date", "") or "Not scheduled"\n        )\n\n        if session.get("next_follow_up_time"):\n            next_follow += " " + str(session.get("next_follow_up_time"))\n\n        rows.append(\n            f"""\n            <tr>\n              <td><strong>{safe(session.get("_lead_id"))}</strong></td>\n              <td>\n                <strong>{safe(session.get("_name"))}</strong><br>\n                <small>{safe(session.get("_phone"))}</small>\n              </td>\n              <td>\n                {safe(session.get("_country"))}<br>\n                <small>{safe(session.get("_course"))}</small>\n              </td>\n              <td>\n                <strong>{safe(session.get("counselling_date")) or "Not set"}</strong><br>\n                <small>{safe(session.get("counselling_time")) or "Time not set"}</small>\n              </td>\n              <td>\n                {safe(session.get("counsellor")) or \'<span class="muted">Unassigned</span>\'}\n              </td>\n              <td>{safe(session.get("mode"))}</td>\n              <td><span class="outcome">{safe(session.get("outcome"))}</span></td>\n              <td>\n                {safe(session.get("notes")) or \'<span class="muted">No notes</span>\'}<br>\n                <small>Next: {safe(next_follow)}</small>\n              </td>\n              <td>\n                <a class="view" href="/lead?id={safe(session.get("_lead_id"))}">\n                    Open Lead\n                </a>\n              </td>\n            </tr>\n            """\n        )\n\n    table = "".join(rows) or (\n        \'<tr><td colspan="9" class="empty">\'\n        \'No counselling sessions match your filters.\'\n        \'</td></tr>\'\n    )\n\n    counsellor_options = (\n        \'<option value="">All counsellors</option>\'\n        + option_list(sorted(counsellor_values, key=str.lower), counsellor)\n    )\n\n    if outcome:\n        outcome_options = (\n            \'<option value="">All outcomes</option>\'\n            + counselling_outcome_options(outcome.title())\n        )\n    else:\n        outcome_options = (\n            \'<option value="" selected>All outcomes</option>\'\n            + counselling_outcome_options("")\n        )\n\n    return f"""<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Counselling Manager — Sayyed EdVantage</title>\n<style>\n:root{{--blue:#1769aa;--dark:#14213d;--gold:#c9972b;--border:#dfe5ee;--muted:#697586;--bg:#f4f7fb}}\n*{{box-sizing:border-box}}\nbody{{margin:0;font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:#172033}}\nheader{{background:linear-gradient(135deg,#14213d,#1c355d);color:#fff;padding:22px 34px}}\nheader h1{{margin:0;font-size:25px}}\nheader p{{margin:5px 0 0;opacity:.85}}\nnav{{background:#fff;border-bottom:1px solid var(--border);padding:10px 34px;display:flex;gap:8px;flex-wrap:wrap}}\n.nav-link{{display:inline-block;padding:8px 12px;border-radius:8px;color:#1769aa;text-decoration:none;font-weight:600}}\n.nav-link.active{{background:#1769aa;color:#fff}}\nmain{{max-width:1500px;margin:24px auto;padding:0 22px}}\n.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}}\n.card{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:17px}}\n.card span{{display:block;color:var(--muted);font-size:12px}}\n.card strong{{display:block;font-size:28px;margin-top:6px;color:var(--dark)}}\n.toolbar,.new-session{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:18px}}\n.section-title{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}\n.section-title h2{{margin:0;font-size:18px}}\n.toolbar form{{display:flex;gap:8px;flex-wrap:wrap}}\ninput,select,button{{border:1px solid #cbd3df;border-radius:8px;padding:9px 10px;font-size:13px;background:#fff}}\n.toolbar input{{min-width:260px}}\nbutton{{background:var(--blue);color:#fff;border-color:var(--blue);cursor:pointer;font-weight:600}}\n.table-wrap{{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:auto}}\ntable{{width:100%;border-collapse:collapse;min-width:1250px}}\nth,td{{padding:11px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;font-size:12px}}\nth{{background:#f8f9fc;color:#4e5a6c;position:sticky;top:0}}\nsmall,.muted{{color:var(--muted)}}\n.outcome{{display:inline-block;padding:5px 9px;border-radius:14px;background:#eef5ff;color:var(--blue);font-weight:700}}\n.view{{display:inline-block;padding:7px 10px;border:1px solid var(--border);border-radius:7px;color:var(--blue);text-decoration:none;font-weight:600}}\n.empty{{text-align:center;padding:35px;color:var(--muted)}}\n@media(max-width:800px){{.cards{{grid-template-columns:1fr 1fr}}main{{padding:18px}}}}\n</style>\n</head>\n<body>\n<header>\n  <h1>Sayyed EdVantage</h1>\n  <p>Admissions CRM & Counselling Manager</p>\n</header>\n<nav>{navigation_html("counselling")}</nav>\n<main>\n{f\'<div class="notice">{safe(message)}</div>\' if message else \'\'}\n\n<div class="cards">\n  <div class="card"><span>Total Counselling Sessions</span><strong>{len(sessions)}</strong></div>\n  <div class="card"><span>Today\'s Counselling</span><strong>{today_count}</strong></div>\n  <div class="card"><span>Pending / Call Back</span><strong>{pending_count}</strong></div>\n  <div class="card"><span>Enrolled from Counselling</span><strong>{enrolled_count}</strong></div>\n</div>\n\n<section class="new-session">\n  <div class="section-title">\n    <h2>New Counselling Session</h2>\n    <a href="/">← Back to Lead Manager</a>\n  </div>\n  <p class="muted">\n    Open any student profile to record a counselling session.\n    The session automatically updates the student\'s CRM follow-up and status.\n  </p>\n</section>\n\n<section class="toolbar">\n<form method="get" action="/counselling">\n  <input name="q" value="{safe(q)}" placeholder="Search student, lead ID, phone, course...">\n  <select name="counsellor">{counsellor_options}</select>\n  <select name="outcome">{outcome_options}</select>\n  <input type="date" name="date" value="{safe(date_filter)}">\n  <button type="submit">Search</button>\n  <a href="/counselling" style="padding:9px 12px;color:#1769aa;text-decoration:none">Clear</a>\n</form>\n</section>\n\n<section class="table-wrap">\n<table>\n<thead>\n<tr>\n<th>Lead ID</th><th>Student</th><th>Country / Course</th>\n<th>Date / Time</th><th>Counsellor</th><th>Mode</th>\n<th>Outcome</th><th>Notes / Next Follow-up</th><th>Action</th>\n</tr>\n</thead>\n<tbody>{table}</tbody>\n</table>\n</section>\n\n<p class="muted" style="margin-top:12px">\nShowing {len(filtered)} of {len(sessions)} counselling sessions.\nSessions are stored inside the same leads.json used by the AI Agent.\n</p>\n</main>\n</body>\n</html>"""\n'

def function_exists(source_text, name):
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
        for node in tree.body
    )

def insert_before_function(source_text, target_name, block):
    marker = f"\\ndef {target_name}("
    pos = source_text.find(marker)
    if pos == -1:
        raise RuntimeError(f"Could not find def {target_name}(...) in the branded CRM.")
    return source_text[:pos] + "\n" + block.strip() + "\n" + source_text[pos:]

if not SOURCE.exists():
    raise FileNotFoundError(
        f"{SOURCE} was not found. Put this patcher in the same main folder as the CRM."
    )

original = SOURCE.read_text(encoding="utf-8")

# Never overwrite the original. Create one backup first.
if not BACKUP.exists():
    shutil.copy2(SOURCE, BACKUP)

final_text = original

# The branded CRM already contains the /counselling route and /add-counselling
# POST handler. The missing piece is the page function itself.
if not function_exists(final_text, "counselling_page"):
    final_text = insert_before_function(
        final_text,
        "lead_details_page",
        COUNSELLING_FUNCTION,
    )

# Safety check: make sure the final source is valid Python.
ast.parse(final_text)

OUTPUT.write_text(final_text, encoding="utf-8")

print("=" * 70)
print("Sayyed EdVantage CRM final build completed")
print("=" * 70)
print(f"Original : {SOURCE.resolve()}")
print(f"Backup   : {BACKUP.resolve()}")
print(f"Final    : {OUTPUT.resolve()}")
print()
print("The original branded CRM was NOT overwritten.")
print("Run the FINAL file only after checking the generated file.")
print()
print("Start command:")
print(f"python .\\{OUTPUT.name}")
print("=" * 70)
