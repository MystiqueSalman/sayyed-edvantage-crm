from __future__ import annotations

"""
Sayyed EdVantage CRM - FINAL BRAND HEADER PATCHER

Place this file in:
    SayyedEdVantage-AI-Agent

Run:
    python .\Sayyed_EdVantage_CRM_FINAL_BRAND_HEADER_PATCHER.py

This safely patches the existing professional CRM instead of replacing
your CRM/database/routes with a newly invented application.
"""

from pathlib import Path
from datetime import datetime
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parent

CANDIDATES = [
    ROOT / "Sayyed_EdVantage_CRM_FINAL_PROFESSIONAL.py",
    ROOT / "Sayyed_EdVantage_CRM_FINAL_BRAND_EXACT.py",
    ROOT / "Sayyed_EdVantage_CRM_Branded_FINAL.py",
]


HEADER_OVERRIDE = r"""
/* ============================================================
   SAYYED EDVANTAGE - FINAL PROFESSIONAL BRAND SYSTEM
   Visual-only override. CRM logic is untouched.
   ============================================================ */

:root{
  --sev-navy:#06152f;
  --sev-navy-2:#0a1d3d;
  --sev-blue:#1769aa;
  --sev-bright-blue:#1677b8;
  --sev-gold:#f5c542;
  --sev-white:#ffffff;
}

/* Main brand header */
header.brand-header{
  position:relative !important;
  width:100% !important;
  min-height:248px !important;
  padding:0 !important;
  overflow:hidden !important;
  color:#fff !important;
  background:
    radial-gradient(circle at 82% 45%,
      rgba(37,119,188,.30) 0%,
      rgba(19,70,121,.16) 32%,
      transparent 61%),
    linear-gradient(105deg,
      #06152f 0%,
      #0a1d3d 42%,
      #123d69 73%,
      #1769a1 100%) !important;
  border-bottom:2px solid rgba(72,168,235,.72) !important;
  box-shadow:none !important;
}

/* Premium background rings */
header.brand-header:after{
  content:"" !important;
  position:absolute !important;
  width:520px !important;
  height:520px !important;
  right:70px !important;
  top:-138px !important;
  border-radius:50% !important;
  border:1px solid rgba(117,190,239,.12) !important;
  box-shadow:
    0 0 0 85px rgba(117,190,239,.035),
    0 0 0 170px rgba(117,190,239,.022) !important;
  pointer-events:none !important;
  background:transparent !important;
}

/* Header content */
header.brand-header .brand-inner{
  position:relative !important;
  z-index:2 !important;
  width:100% !important;
  max-width:1650px !important;
  min-height:248px !important;
  margin:0 auto !important;
  padding:0 42px !important;
  display:flex !important;
  align-items:center !important;
  gap:36px !important;
  box-sizing:border-box !important;
}

/* Large transparent logo zone - no crop/card */
header.brand-header .brand-mark{
  position:relative !important;
  flex:0 0 520px !important;
  width:520px !important;
  min-width:520px !important;
  height:210px !important;
  display:flex !important;
  align-items:center !important;
  justify-content:center !important;
  background:transparent !important;
  border:0 !important;
  box-shadow:none !important;
  overflow:visible !important;
}

/* Preserve the existing official logo */
header.brand-header .brand-mark img,
header.brand-header .brand-logo{
  display:block !important;
  width:100% !important;
  max-width:520px !important;
  height:100% !important;
  max-height:210px !important;
  object-fit:contain !important;
  object-position:center !important;
  background:transparent !important;
  border:0 !important;
  outline:0 !important;
  box-shadow:none !important;
}

/* Divider */
header.brand-header .brand-copy{
  position:relative !important;
  flex:1 1 auto !important;
  min-width:0 !important;
  padding:12px 0 12px 38px !important;
  border-left:1px solid rgba(255,255,255,.24) !important;
  background:transparent !important;
}

/* Gold label */
header.brand-header .brand-kicker{
  margin:0 0 14px !important;
  font-family:"Segoe UI",Arial,sans-serif !important;
  font-size:15px !important;
  line-height:1.2 !important;
  font-weight:800 !important;
  letter-spacing:4px !important;
  color:var(--sev-gold) !important;
  text-transform:uppercase !important;
}

/* Command title */
header.brand-header .brand-copy h1,
header.brand-header .brand-title h1{
  margin:0 !important;
  color:#fff !important;
  font-family:"Segoe UI",Arial,sans-serif !important;
  font-size:clamp(34px,3vw,50px) !important;
  line-height:1.12 !important;
  font-weight:800 !important;
  letter-spacing:-1px !important;
  text-shadow:0 2px 8px rgba(0,0,0,.22) !important;
}

/* Subtitle */
header.brand-header .brand-copy p,
header.brand-header .brand-title p{
  margin:14px 0 0 !important;
  color:rgba(255,255,255,.82) !important;
  font-family:"Segoe UI",Arial,sans-serif !important;
  font-size:clamp(16px,1.35vw,20px) !important;
  line-height:1.55 !important;
}

/* Responsive */
@media(max-width:1200px){
  header.brand-header .brand-inner{
    padding:0 28px !important;
    gap:24px !important;
  }
  header.brand-header .brand-mark{
    flex-basis:430px !important;
    width:430px !important;
    min-width:430px !important;
    height:185px !important;
  }
  header.brand-header .brand-mark img,
  header.brand-header .brand-logo{
    max-width:430px !important;
    max-height:185px !important;
  }
  header.brand-header .brand-copy{
    padding-left:28px !important;
  }
  header.brand-header .brand-kicker{
    font-size:13px !important;
    letter-spacing:3px !important;
  }
}

@media(max-width:850px){
  header.brand-header{
    min-height:auto !important;
  }
  header.brand-header .brand-inner{
    min-height:auto !important;
    padding:22px 24px 26px !important;
    flex-direction:column !important;
    align-items:stretch !important;
    gap:18px !important;
  }
  header.brand-header .brand-mark{
    width:100% !important;
    min-width:0 !important;
    flex-basis:auto !important;
    height:165px !important;
  }
  header.brand-header .brand-mark img,
  header.brand-header .brand-logo{
    width:min(100%,620px) !important;
    max-width:620px !important;
    height:165px !important;
    max-height:165px !important;
    margin:auto !important;
  }
  header.brand-header .brand-copy{
    padding:20px 0 0 !important;
    border-left:0 !important;
    border-top:1px solid rgba(255,255,255,.22) !important;
  }
  header.brand-header .brand-copy h1,
  header.brand-header .brand-title h1{
    font-size:32px !important;
  }
}

@media(max-width:600px){
  header.brand-header .brand-inner{
    padding:16px 16px 22px !important;
  }
  header.brand-header .brand-mark{
    height:135px !important;
  }
  header.brand-header .brand-mark img,
  header.brand-header .brand-logo{
    height:135px !important;
  }
  header.brand-header .brand-kicker{
    font-size:11px !important;
    letter-spacing:2.2px !important;
  }
  header.brand-header .brand-copy h1,
  header.brand-header .brand-title h1{
    font-size:27px !important;
  }
  header.brand-header .brand-copy p,
  header.brand-header .brand-title p{
    font-size:15px !important;
  }
}
"""


def find_target() -> Path:
    for candidate in CANDIDATES:
        if candidate.exists():
            return candidate

    matches = sorted(
        ROOT.glob("Sayyed_EdVantage_CRM*.py"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for path in matches:
        if path.name != Path(__file__).name:
            return path

    raise FileNotFoundError(
        "No Sayyed EdVantage CRM Python file was found in this folder."
    )


def create_backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(
        f"{path.stem}_BACKUP_{stamp}{path.suffix}"
    )
    shutil.copy2(path, backup_path)
    return backup_path


def patch_css(text: str) -> tuple[str, bool]:
    # Current professional CRM format:
    # CSS = """ ... """
    pattern = re.compile(
        r'(?ms)^CSS\s*=\s*(""").*?(""")\s*\n\s*\n\s*def\s+page\s*\('
    )

    match = pattern.search(text)

    if match:
        new_css = match.group(1) + HEADER_OVERRIDE + "\n" + match.group(2)
        replacement = new_css + "\n\n\ndef page("
        updated = text[:match.start()] + replacement + text[match.end():]
        return updated, True

    # Fallback for older versions.
    if "SAYYED EDVANTAGE - FINAL PROFESSIONAL BRAND SYSTEM" in text:
        return text, True

    pos = text.find("</style>")

    if pos != -1:
        updated = text[:pos] + "\n" + HEADER_OVERRIDE + "\n" + text[pos:]
        return updated, True

    return text, False


def main() -> None:
    target = find_target()
    original = target.read_text(encoding="utf-8")

    updated, recognized = patch_css(original)

    if not recognized:
        raise RuntimeError(
            "CRM file format was not recognized. No changes were made."
        )

    if updated == original:
        print("The professional brand header is already applied.")
        return

    backup_path = create_backup(target)
    target.write_text(updated, encoding="utf-8")

    print("=" * 72)
    print("SAYYED EDVANTAGE CRM - FINAL BRAND HEADER")
    print("=" * 72)
    print(f"Updated : {target.name}")
    print(f"Backup  : {backup_path.name}")
    print()
    print("Preserved:")
    print("  - Lead Manager")
    print("  - Counselling Manager")
    print("  - Follow-up Manager")
    print("  - Lead profiles")
    print("  - Payments")
    print("  - Database / leads.json")
    print("  - Existing official logo")
    print("  - Existing CRM routes")
    print()
    print("Now run:")
    print(f"python .\\{target.name}")
    print()
    print("Open:")
    print("http://127.0.0.1:8000")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("PATCH FAILED - NO CRM FILE WAS MODIFIED")
        print(f"Reason: {exc}")
        sys.exit(1)
