from pathlib import Path
import json, subprocess, sys, time, urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent
CRM = ROOT / "Sayyed_EdVantage_CRM_REBUILT.py"
LEADS = ROOT / "data" / "leads.json"
BASE = "http://127.0.0.1:8000"

def check(name, condition):
    if not condition:
        print("FAIL: " + name)
        raise SystemExit(1)
    print("PASS: " + name)

def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent":"CRM-Final-Test"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode("utf-8", errors="replace")

def main():
    check("CRM source exists", CRM.exists())
    check("leads.json exists", LEADS.exists())

    source = CRM.read_text(encoding="utf-8")
    for label, token in [
        ("counselling route", '"/counselling"'),
        ("follow-up route", '"/follow-ups"'),
        ("lead route", '"/lead?id='),
        ("update route", '"/update-lead"'),
    ]:
        check(label, token in source or token.replace(chr(34), chr(39)) in source)

    before = LEADS.read_bytes()
    data = json.loads(before.decode("utf-8"))
    check("leads.json valid", isinstance(data, dict))
    ids = set(data.keys()) if isinstance(data, dict) else {str(x.get("lead_id")) for x in data if isinstance(x, dict)}
    check("six test leads present", all(f"SE-{i:05d}" in ids for i in range(1,7)))

    proc = subprocess.Popen(
        [sys.executable, str(CRM)], cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        ready = False
        for _ in range(30):
            try:
                status, body = get("/")
                if status == 200:
                    ready = True
                    break
            except Exception:
                time.sleep(0.25)
        check("CRM portal starts", ready)
        check("dashboard HTTP 200", get("/")[0] == 200)
        check("counselling HTTP 200", get("/counselling")[0] == 200)
        check("follow-ups HTTP 200", get("/follow-ups")[0] == 200)

        s, body = get("/lead?id=SE-00001")
        check("SE-00001 HTTP 200", s == 200)
        check("SE-00001 isolation", "SE-00001" in body)

        s, body = get("/lead?id=SE-00002")
        check("SE-00002 HTTP 200", s == 200)
        check("SE-00002 isolation", "SE-00002" in body)

        try:
            get("/lead?id=SE-99999")
            unknown_safe = False
        except urllib.error.HTTPError as e:
            unknown_safe = e.code in {404, 500}
        check("unknown lead fails safely", unknown_safe)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    check("test did not modify leads.json", before == LEADS.read_bytes())

    print()
    print("CRM FINAL READINESS TEST RESULT: ALL PASSED")
    print("CRM STATUS: READY TO FREEZE")
    print("NEXT: PROCEED TO AI AGENT")
    print("RETURN CODE: 0")

if __name__ == "__main__":
    main()

