from pathlib import Path
import py_compile, importlib.util

ROOT=Path(__file__).resolve().parent
B5=ROOT/"Sayyed_EdVantage_AI_Agent_BATCH5.py"
DATA=ROOT/"data"/"leads.json"

def load(p):
    spec=importlib.util.spec_from_file_location("b5",p)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def ok(label):
    print(f"{label:<34}: PASSED")

print("="*82)
print("PHASE 1 / BATCH 5 - VERIFICATION")
print("="*82)
py_compile.compile(str(B5),doraise=True); ok("Python syntax")
before=DATA.read_bytes()
m=load(B5); leads=m.B4.B3.all_leads(); assert leads; ok(f"Leads checked ({len(leads)})")
results=[m.analyze_lead(x) for x in leads]; assert len(results)==len(leads); ok("Analysis coverage")
for x in results:
    assert x["persona"]["primary_persona"]; ok("Persona/profile engine")
    assert x["decision_maker"]["decision_role"]; ok("Decision-maker detection")
    assert 0<=x["admission_readiness"]["readiness_score"]<=100; ok("Admission readiness")
    assert x["followup_message"]["message"]; ok("Personalized follow-up")
    assert len(x["call_preparation"]["questions"])>=2; ok("Call preparation")
    assert x["conversion_blocker_map"]["blockers"]; ok("Conversion blocker map")
assert DATA.read_bytes()==before; ok("Data integrity / read-only")
print()
print("BATCH 5 VERIFICATION PASSED")
print("="*82)
