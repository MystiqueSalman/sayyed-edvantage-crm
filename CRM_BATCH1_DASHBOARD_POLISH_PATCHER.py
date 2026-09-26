from pathlib import Path
from datetime import datetime
import shutil
import ast

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Sayyed_EdVantage_CRM_REBUILT.py"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"Sayyed_EdVantage_CRM_REBUILT_BACKUP_{STAMP}.py"
OUTPUT = ROOT / "Sayyed_EdVantage_CRM_BATCH1.py"

if not SOURCE.exists():
    raise FileNotFoundError(
        f"Could not find {SOURCE.name}. Put this patcher in the same Agent folder."
    )

original = SOURCE.read_text(encoding="utf-8")
ast.parse(original, filename=str(SOURCE))
shutil.copy2(SOURCE, BACKUP)

BATCH1_CSS = r"""
/* SAYYED EDVANTAGE — BATCH 1 PROFESSIONAL DASHBOARD POLISH */

:root{
  --se-navy:#0b1730;
  --se-dark:#14213d;
  --se-blue:#1769aa;
  --se-blue-2:#2388c7;
  --se-gold:#d8b64c;
  --se-bg:#f3f7fc;
  --se-border:#dbe4ee;
  --se-muted:#68768a;
  --se-shadow:0 8px 24px rgba(20,33,61,.075);
}

html{scroll-behavior:smooth}

body{
  background:
    radial-gradient(circle at 92% 8%,rgba(35,136,199,.045),transparent 24%),
    linear-gradient(180deg,#f6f9fd 0%,var(--se-bg) 100%);
  color:#172033;
  font-family:"Segoe UI",Inter,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}

header.brand-header,
header{
  box-shadow:0 8px 25px rgba(20,33,61,.13);
}

nav{
  box-shadow:0 3px 14px rgba(20,33,61,.055);
  backdrop-filter:blur(8px);
}

.nav-link{
  transition:transform .16s ease,box-shadow .16s ease,background .16s ease;
}
.nav-link:hover{transform:translateY(-1px)}
.nav-link.active{box-shadow:0 6px 15px rgba(23,105,170,.20)}

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
  background:linear-gradient(180deg,var(--se-gold),var(--se-blue-2));
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

.card.money strong{font-size:25px !important}

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

.pipeline-row b{font-weight:800}

.filters{
  border:1px solid var(--se-border) !important;
  border-radius:16px !important;
  box-shadow:var(--se-shadow) !important;
  padding:19px !important;
  background:#fff !important;
}

.filters h2{
  color:#14213d;
  font-size:18px !important;
  font-weight:800;
}

.filter-grid{gap:10px !important}

.filter-grid input,
.filter-grid select,
.filters input,
.filters select,
.filters button{
  min-height:42px;
  border-color:#cbd7e4 !important;
  border-radius:9px !important;
  outline:none;
  transition:border-color .15s ease,box-shadow .15s ease;
}

.filter-grid input:focus,
.filter-grid select:focus,
.filters input:focus,
.filters select:focus{
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

.table-wrap td{border-bottom-color:#edf1f5 !important}
.table-wrap tbody tr:hover td{background:#fbfdff}
.details,.view{font-weight:800 !important}

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
  .cards{grid-template-columns:repeat(3,minmax(0,1fr)) !important}
}

@media(max-width:850px){
  .cards{grid-template-columns:repeat(2,minmax(0,1fr)) !important}
}

@media(max-width:600px){
  .cards{grid-template-columns:1fr !important}
  .card{min-height:112px}
  main{padding:18px !important}
}
"""

# The current CRM source uses f-string HTML templates with doubled CSS braces.
# Detect that style and preserve the correct Python escaping.
if ":root{{" in original or "body{{" in original:
    css_to_insert = BATCH1_CSS.replace("{", "{{").replace("}", "}}")
else:
    css_to_insert = BATCH1_CSS

if "SAYYED EDVANTAGE — BATCH 1 PROFESSIONAL DASHBOARD POLISH" in original:
    raise RuntimeError("Batch 1 is already present in the source.")

style_pos = original.find("</style>")
if style_pos < 0:
    raise RuntimeError("Could not find </style> in the CRM source.")

updated = original[:style_pos] + "\n" + css_to_insert + "\n" + original[style_pos:]
ast.parse(updated, filename=str(OUTPUT))
OUTPUT.write_text(updated, encoding="utf-8")

print("=" * 72)
print("SAYYED EDVANTAGE CRM — BATCH 1 READY")
print("=" * 72)
print(f"Working source : {SOURCE.name}")
print(f"Backup created : {BACKUP.name}")
print(f"New build      : {OUTPUT.name}")
print()
print("Batch 1 contains 6 grouped improvements:")
print("1. Professional 4-column dashboard card layout")
print("2. Premium card borders, gold/blue accents and depth")
print("3. Cleaner Pipeline and Lead Sources panels")
print("4. Improved Advanced Search & Filters presentation")
print("5. Improved lead-table readability and hover behavior")
print("6. Responsive desktop/tablet/mobile layout")
print()
print("Logo, data, routes and CRM business logic were NOT changed.")
print("Python syntax validation: PASSED")
print("=" * 72)
