from __future__ import annotations
import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
B4_FILE = ROOT / "Sayyed_EdVantage_AI_Agent_BATCH4.py"

def load_b4():
    spec = importlib.util.spec_from_file_location("batch4", B4_FILE)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load Batch 4")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

B4 = load_b4()

def s(v: Any) -> str:
    return str(v or "").strip()

def text(lead, a):
    w = a["workflow_intelligence"]
    mem = w.get("conversation_memory", {})
    return " ".join([
        s(lead.get("name")), s(lead.get("course_interest")),
        s(lead.get("status")), s(lead.get("source")),
        s(lead.get("notes")), s(lead.get("remarks")),
        s(lead.get("last_outcome")), s(lead.get("next_action")),
        " ".join(mem.get("recent_interactions", []))
    ]).lower()

def persona_engine(lead, a):
    t = text(lead,a)
    groups = {
        "Career Focused": ("career","job","placement","salary"),
        "Skill Builder": ("skill","upskill","training","learn"),
        "Information Seeker": ("details","information","brochure","syllabus"),
        "Decision Focused": ("admission","enroll","register","join"),
    }
    hits = [(k,sum(x in t for x in v)) for k,v in groups.items()]
    hits = sorted([x for x in hits if x[1]], key=lambda x:(-x[1],x[0]))
    return {"primary_persona": hits[0][0] if hits else "Unclassified Prospect",
            "confidence": min(95,55+(hits[0][1]*10 if hits else 0)),
            "signals":[x[0] for x in hits]}

def decision_maker_engine(lead,a):
    t=text(lead,a)
    p=sum(x in t for x in ("parent","parents","father","mother","guardian","family"))
    j=sum(x in t for x in ("discuss with","talk to parents","family decision"))
    role="Joint Decision" if j else ("Parent / Family Influenced" if p else "Student-Led")
    return {"decision_role":role,"parent_family_signals":p,
            "recommendation":"Include family decision-makers where indicated." if role!="Student-Led"
            else "Keep discussion student-centered."}

def readiness_engine(lead,a):
    stage=a["workflow_intelligence"]["stage_intelligence"]["inferred_stage"]
    pts={"New":10,"Contacted":25,"Counselling":45,"Interested":65,
         "Application":82,"Payment Pending":95,"Enrolled":100,"Lost":0}
    score=pts.get(stage,20)+min(15,len(a["buying_signals"]["strong_signals"])*5)
    if a["workflow_intelligence"]["follow_up_timing"]["urgency"] in ("Immediate","High"): score+=5
    score=min(100,score)
    level="Admission Ready" if score>=80 else ("Near Ready" if score>=60 else ("Developing" if score>=35 else "Early Stage"))
    return {"readiness_score":score,"readiness_level":level,
            "readiness_gap":max(0,70-score)}

def followup_message_engine(lead,a,persona,decision,ready):
    name=s(lead.get("name")) or "there"
    course=s(lead.get("course_interest")) or "the programme"
    obj=a["objection_detection"]["primary_objection"]
    body={
        "Fees / Budget":"I can walk you through the fee structure and payment options.",
        "Timing / Schedule":"I can help you find a suitable batch or schedule.",
        "Course Fit":"I can clarify the syllabus, duration and programme fit.",
        "Career / Outcome":"I can discuss realistic skills and career outcomes relevant to your goal.",
        "Parent / Family Decision":"I can share concise programme and fee information for your family discussion.",
        "Trust / Information":"I can provide the programme details and answer your questions before you decide."
    }.get(obj,"I would like to understand your goal and help with the right next step.")
    return {"channel":a["next_best_action"]["channel"],
            "tone":"Personalized, concise, consultative",
            "message":f"Hi {name}, following up regarding {course}. {body} Please share a suitable time or reply with your questions."}

def call_preparation_engine(lead,a,persona,decision,ready):
    qs=["What is the main outcome you want from this programme?",
        "What is the most important factor before you decide?"]
    if a["objection_detection"]["primary_objection"]!="None":
        qs.append("What is your main concern about "+a["objection_detection"]["primary_objection"]+"?")
    if decision["decision_role"]!="Student-Led":
        qs.append("Who else should be included before the final decision?")
    return {"opening_goal":"Understand the goal, resolve the blocker and secure one concrete next step.",
            "questions":qs,
            "talking_points":[f"Persona: {persona['primary_persona']}",
                              f"Readiness: {ready['readiness_level']} ({ready['readiness_score']}/100)"],
            "avoid":["Generic sales pitch","Unsupported promises"]}

def blocker_map(lead,a,ready):
    b=[]
    obj=a["objection_detection"]["primary_objection"]
    if obj!="None": b.append(obj)
    if a["decision_maker"]["decision_role"]!="Student-Led": b.append("Decision-maker alignment")
    if ready["readiness_score"]<60: b.append("Insufficient admission readiness")
    if not b: b=["No major blocker detected"]
    return {"blockers":b,"primary_blocker":b[0],
            "severity":"High" if obj!="None" and ready["readiness_score"]>=60 else ("Medium" if len(b)>1 else "Low")}

def analyze_lead(lead):
    a=B4.analyze_lead(lead)
    persona=persona_engine(lead,a)
    decision=decision_maker_engine(lead,a)
    a["decision_maker"]=decision
    ready=readiness_engine(lead,a)
    return {**a,"persona":persona,"decision_maker":decision,
            "admission_readiness":ready,
            "followup_message":followup_message_engine(lead,a,persona,decision,ready),
            "call_preparation":call_preparation_engine(lead,a,persona,decision,ready),
            "conversion_blocker_map":blocker_map(lead,a,ready)}

def all_analysis():
    return [analyze_lead(x) for x in B4.B3.all_leads()]

if __name__=="__main__":
    print("="*78)
    print("SAYYED EDVANTAGE AI AGENT - PHASE 1 / BATCH 5")
    print("="*78)
    print(f"Data file: {B4.B3.LEADS_FILE}")
    print(f"Leads loaded: {len(B4.B3.all_leads())}")
    print("READ-ONLY MODE: leads.json will not be modified.")
    print("-"*78)
    for x in all_analysis():
        print(f"{x['lead_id']:<10} {x['name'][:20]:<20} Persona={x['persona']['primary_persona']:<20} Readiness={x['admission_readiness']['readiness_score']:<3} Blocker={x['conversion_blocker_map']['primary_blocker']}")
    print("="*78)
