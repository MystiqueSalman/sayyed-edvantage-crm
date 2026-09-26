from pathlib import Path
from datetime import datetime
import shutil
import ast

# ============================================================
# SAYYED EDVANTAGE CRM — BATCH 1 SAFE PATCHER (FIXED)
# ============================================================
# This version fixes the previous "unterminated f-string literal"
# problem by escaping EVERY CSS { } before inserting CSS into the
# Python f-string HTML template.
#
# It does NOT modify the original working CRM.
# It creates:
#   1) a timestamped backup
#   2) a new Batch 1 file
# ============================================================

ROOT = Path(__file__).resolve().parent

SOURCE = ROOT / "Sayyed_EdVantage_CRM_REBUILT.py"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"Sayyed_EdVantage_CRM_REBUILT_BACKUP_{STAMP}.py"
OUTPUT = ROOT / "Sayyed_EdVantage_CRM_BATCH1.py"

if not SOURCE.exists():
    raise FileNotFoundError(
        f"Missing {SOURCE.name}. Make sure this patcher is inside "
        "the SayyedEdVantage-AI-Agent folder."
    )

original = SOURCE.read_text(encoding="utf-8")

# 1. Validate the original first.
ast.parse(original, filename=str(SOURCE))

# 2. Never overwrite the working source.
shutil.copy2(SOURCE, BACKUP)

# 3. Professional CSS.
CSS = r"""
/* ============================================================
   SAYYED EDVANTAGE — BATCH 1 PROFESSIONAL UI
   ============================================================ */

:root{
  --se-navy:#0b1730;
  --se-dark:#14213d;
  --se-blue:#1769aa;
  --se-blue2:#2388c7;
  --se-gold:#d8b64c;
  --se-border:#dbe4ee;
  --se-bg:#f3f7fc;
  --se-shadow:0 8px 24px rgba(20,33,61,.075);
}

html{
  scroll-behavior:smooth;
}

body{
  background:
    radial-gradient(circle at 92% 8%,rgba(35,136,199,.045),transparent 24%),
    linear-gradient(180deg,#f6f9fd 0%,var(--se-bg) 100%);
  color:#172033;
  font-family:"Segoe UI",Inter,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}

header,
header.brand-header{
  box-shadow:0 8px 25px rgba(20,33,61,.13);
}

nav{
  box-shadow:0 3px 14px rgba(20,33,61,.055);
  backdrop-filter:blur(8px);
}

.cards{
  grid-template-columns:repeat(4,minmax(0,1fr)) !important;
  gap:18px !important;
  margin-bottom:20px !important;
}

.card{
  min-height:126px;
  padding:21px 22px !important;
  border:1px solid var(--se-border) !important;
  border-radius:16px !important;
  background:
    radial-gradient(circle at 92% 105%,rgba(23,105,170,.055) 0 54px,transparent 55px),
    #fff !important;
  box-shadow:var(--se-shadow) !important;
  position:relative;
  overflow:hidden;
  transition:transform .16s ease,box-shadow .16s ease;
}

.card:before{
  content:"";
  position:absolute;
  left:0;
  top:0;
  bottom:0;
  width:5px;
  background:linear-gradient(180deg,var(--se-gold),var(--se-blue2));
}

.card:hover{
  transform:translateY(-2px);
  box-shadow:0 12px 28px rgba(20,33,61,.105) !important;
}

.card span{
  color:#647286 !important;
  font-size:12px !important;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:.35px;
}

.card strong{
  color:#14213d !important;
  font-size:30px !important;
  line-height:1.1;
  margin-top:9px !important;
  font-weight:800;
}

.card.money strong{
  font-size:25px !important;
}

.grid{
  gap:18px !important;
  margin-bottom:20px !important;
}

.panel{
  border:1px solid var(--se-border) !important;
  border-radius:16px !important;
  box-shadow:var(--se-shadow) !important;
  background:rgba(255,255,255,.97) !important;
}

.panel h2,
.panel h3{
  color:#14213d;
  font-weight:800;
}

.pipeline-row{
  margin:2px 0;
  padding:10px 9px !important;
  border-radius:9px !important;
  border-bottom:1px solid #edf1f5 !important;
  transition:background .14s ease,transform .14s ease;
}

.pipeline-row:hover{
  background:#f4f8fc !important;
  transform:translateX(2px);
}

.filters{
  border:1px solid var(--se-border) !important;
  border-radius:16px !important;
  box-shadow:var(--se-shadow) !important;
  padding:19px !important;
  background:#fff !important;
}

.filters input,
.filters select,
.filters button,
.filter-grid input,
.filter-grid select{
  min-height:42px;
  border-color:#cbd7e4 !important;
  border-radius:9px !important;
  outline:none;
  transition:border-color .15s ease,box-shadow .15s ease;
}

.filters input:focus,
.filters select:focus,
.filter-grid input:focus,
.filter-grid select:focus{
  border-color:#2388c7 !important;
  box-shadow:0 0 0 3px rgba(35,136,199,.10);
}

button{
  border-radius:9px !important;
  font-weight:800 !important;
  background:linear-gradient(135deg,#14213d,#1769aa) !important;
  box-shadow:0 5px 13px rgba(23,105,170,.18);
}

.table-wrap{
  border:1px solid var(--se-border) !important;
  border-radius:16px !important;
  box-shadow:var(--se-shadow) !important;
  background:#fff !important;
  overflow:hidden;
}

.table-wrap table{
  border-collapse:separate;
  border-spacing:0;
}

.table-wrap th{
  background:#f5f8fc !important;
  color:#506078 !important;
  font-weight:800;
  letter-spacing:.2px;
}

.table-wrap td{
  border-bottom-color:#edf1f5 !important;
}

.table-wrap tbody tr:hover td{
  background:#fbfdff;
}

.details,
.view{
  font-weight:800 !important;
}

.notice{
  border-radius:10px !important;
  box-shadow:0 4px 12px rgba(20,33,61,.045);
}

main{
  max-width:1650px !important;
  padding-top:26px !important;
  padding-bottom:36px !important;
}

@media(max-width:1250px){
  .cards{
    grid-template-columns:repeat(3,minmax(0,1fr)) !important;
  }
}

@media(max-width:850px){
  .cards{
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  }
}

@media(max-width:600px){
  .cards{
    grid-template-columns:1fr !important;
  }

  .card{
    min-height:112px;
  }

  main{
    padding:18px !important;
  }
}

/* END BATCH 1 */
"""

MARKER = "SAYYED EDVANTAGE — BATCH 1 PROFESSIONAL UI"

if MARKER in original:
    raise RuntimeError(
        "Batch 1 already exists in the source. Do not apply it twice."
    )

style_close = original.find("</style>")
if style_close == -1:
    raise RuntimeError(
        "Could not find </style> in the working CRM file."
    )

# CRITICAL FIX:
# The HTML page is generated inside a Python f-string.
# Therefore CSS braces MUST become {{ and }} in the Python source.
CSS_ESCAPED_FOR_FSTRING = CSS.replace("{", "{{").replace("}", "}}")

updated = (
    original[:style_close]
    + "\n"
    + CSS_ESCAPED_FOR_FSTRING
    + "\n"
    + original[style_close:]
)

# 4. Validate the generated Python BEFORE writing it.
try:
    ast.parse(updated, filename=str(OUTPUT))
except SyntaxError as e:
    print("=" * 72)
    print("PATCH ABORTED — GENERATED FILE HAS A PYTHON SYNTAX ERROR")
    print("=" * 72)
    print(f"Line : {e.lineno}")
    print(f"Text : {e.text}")
    print(f"Error: {e.msg}")
    print()
    print("The original CRM was NOT changed.")
    print(f"Backup remains: {BACKUP.name}")
    raise

# 5. Write only after validation succeeds.
OUTPUT.write_text(updated, encoding="utf-8")

print("=" * 72)
print("SAYYED EDVANTAGE CRM — BATCH 1 SUCCESS")
print("=" * 72)
print(f"Original : {SOURCE.name}")
print(f"Backup   : {BACKUP.name}")
print(f"New file : {OUTPUT.name}")
print()
print("6 grouped improvements added:")
print("  1. Professional dashboard card layout")
print("  2. Premium gold/blue card styling")
print("  3. Pipeline and Lead Sources polish")
print("  4. Search/filter polish")
print("  5. Lead table polish")
print("  6. Responsive layout")
print()
print("LOGO / BRANDING : UNCHANGED")
print("DATA             : UNCHANGED")
print("CRM LOGIC        : UNCHANGED")
print("PYTHON SYNTAX    : PASSED")
print("=" * 72)
