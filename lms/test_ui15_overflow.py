"""UI15 — viewport-fit regression: the page must never need left/right dragging.

Covers:
  1. Public pages /, /courses, /login render 200.
  2. Student login -> /dashboard renders 200.
  3. Rendered HTML of those pages has no large fixed inline widths
     (plain `width: NNNpx` with NNN >= 500) that could force page overflow.
  4. CSS ships the global page-level overflow guard (overflow-x:clip).
  5. CSS collapses the public navbar into the drawer at 1600px
     (up from the old 900px breakpoint).
  6. CSS ships table-scroll safeguards + collapsible grid minimums.
  7. App sidebar collapses at 1024px (CSS + layout_app JS).
  8. base.html ships the scrim, expandable search row, and drawer CTA block.

Runs against the Flask test client on a FRESH SQLite DB (no dev server):

    cd ~/workspace/lms && ./run_suite.sh test_ui15_overflow
"""
import os
import re
import sys

os.environ["LMS_SCHEDULER"] = "off"
DB = os.environ.get("SQLITE_PATH", "/tmp/lms_test_ui15.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["SQLITE_PATH"] = DB
os.environ.setdefault("SECRET_KEY", "lms-local-test-secret-not-for-production")

sys.path.insert(0, "/home/hatch/workspace/lms")

import app.models_ui as MUI  # noqa: E402  (register UI14 tables before create_all)
from app import create_app, db  # noqa: E402
from app.models import Course, User, ROLE_STUDENT  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" — {extra}" if extra else ""))


app = create_app()

with app.app_context():
    stu = User(name="UI15 Student", email="ui15stu@example.com",
               role=ROLE_STUDENT)
    stu.set_password("pw-stu-ui15")
    course = Course(title="Data Science", slug="data-science", fee=50000,
                    short_desc="DS course")
    db.session.add_all([stu, course])
    db.session.commit()

client = app.test_client()


def login_as(email, pw):
    s = app.test_client()
    r = s.post("/login", data={"email": email, "password": pw},
               follow_redirects=False)
    return s, r.status_code


# ================================================== 1. pages render 200
pages = {}
for path in ("/", "/courses", "/login"):
    r = client.get(path)
    pages[path] = r.get_data(as_text=True)
    check(f"public {path} 200", r.status_code == 200,
          f"status={r.status_code}")

stu_c, code = login_as("ui15stu@example.com", "pw-stu-ui15")
check("student login accepted", code in (302, 303), f"status={code}")
r = stu_c.get("/dashboard")
pages["/dashboard"] = r.get_data(as_text=True)
check("student /dashboard 200", r.status_code == 200,
      f"status={r.status_code}")

# ================================================== 2. no large fixed inline widths
# Plain `width: NNNpx` with NNN >= 500 in rendered HTML is a page-overflow
# risk (max-/min-width are excluded: min-width tables scroll internally).
BIG_W = re.compile(r"(?<!max-)(?<!min-)width\s*:\s*(?:[5-9]\d\d|[1-9]\d{3,})px",
                   re.IGNORECASE)
for path, html in pages.items():
    hits = sorted(set(BIG_W.findall(html)))
    check(f"{path}: no fixed width >= 500px in HTML", not hits,
          f"hits={hits[:4]}" if hits else "")

# ================================================== 3. CSS guards
CSS = os.path.join(os.path.dirname(__file__),
                   "app", "static", "css", "style.css")
css = open(CSS).read()

check("css: page-level overflow guard (overflow-x:clip)",
      "overflow-x:clip" in css.replace(" ", ""))
check("css: navbar drawer breakpoint raised to 1600px",
      "@media(max-width:1600px)" in css.replace(" ", ""))
check("css: drawer rule targets .nav-links",
      ".nav-links{position:fixed" in css.replace(" ", "").replace("\n", ""))
check("css: old 900px navbar drawer is gone",
      not re.search(r"@media\(max-width:\s*900px\)[^{]*\{[^}]*\.nav-links\{position:fixed",
                    css))
check("css: .table-scroll internal-scroll rule",
      re.search(r"\.table-scroll\{[^}]*overflow-x:\s*auto", css) is not None)
check("css: tables scroll inside containers",
      "overflow-x:auto" in css.replace(" ", ""))
check("css: collapsible grid minimums (min(min(...,100%)",
      "minmax(min(" in css)
check("css: expandable search row + toggle exist",
      ".nav-search-row" in css and ".search-toggle" in css)
check("css: sidebar collapses at 1024px",
      "@media(max-width:1024px)" in css.replace(" ", ""))

# ================================================== 4. templates
BASE = os.path.join(os.path.dirname(__file__), "app", "templates", "base.html")
base = open(BASE).read()
check("base.html: drawer CTA block present", 'class="drawer-cta"' in base)
check("base.html: nav scrim present", 'id="navScrim"' in base)
check("base.html: search toggle present", 'id="searchToggle"' in base)
check("base.html: inline brand-text class (shrinkable on phones)",
      'class="brand-text"' in base)

LAYOUT = os.path.join(os.path.dirname(__file__), "app", "templates",
                      "layout_app.html")
layout = open(LAYOUT).read()
check("layout_app: sidebar JS breakpoint is 1024px",
      "innerWidth <= 1024" in layout)
check("layout_app: old 900px sidebar breakpoint gone",
      "innerWidth <= 900" not in layout)

# rendered markup actually contains the new structure
home = pages["/"]
check("homepage markup: drawer-cta rendered", 'class="drawer-cta"' in home)
check("homepage markup: scrim rendered", 'id="navScrim"' in home)

# ================================================== summary
fails = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
