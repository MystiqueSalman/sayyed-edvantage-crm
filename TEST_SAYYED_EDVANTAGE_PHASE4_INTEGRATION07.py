"""Phase 4 Integration 07 contract test."""
import sys, types, importlib

p = types.ModuleType("Sayyed_EdVantage_PHASE4_INTEGRATION06")
p.LIVE_READY="LIVE_PIPELINE_READY"; p.LIVE_CLARIFICATION="LIVE_PIPELINE_CLARIFICATION"
p.LIVE_REVIEW="LIVE_PIPELINE_REVIEW"; p.LIVE_BLOCKED="LIVE_PIPELINE_BLOCKED"; p.LIVE_UNKNOWN="LIVE_PIPELINE_UNKNOWN"
p.RESPOND="RESPOND"; p.CLARIFY="CLARIFY"; p.HUMAN_REVIEW="HUMAN_REVIEW"; p.NO_RESPONSE="NO_RESPONSE"

class R:
    def __init__(self,sid,lid,text="",status=None,errors=None):
        self.status=status or p.LIVE_READY; self.session_id=sid; self.lead_id=lid
        self.response_text=text; self.turn_count=1
        self.crm_profile={"lead_id":lid,"name":"Test Student"} if lid else None
        self.errors=errors or []
        self.executor_invoked=False; self.execution_authorized=False
        self.crm_write=False; self.message_sent=False; self.external_action=False

class S:
    def __init__(self,sid,lid): self.session_id=sid; self.lead_id=lid; self.user_messages=["hello"]; self.response_history=["ok"]; self.turn_count=1
    def snapshot(self): return {"session_id":self.session_id,"lead_id":self.lead_id,"user_messages":list(self.user_messages),"response_history":list(self.response_history),"turn_count":self.turn_count}

sessions={}
def run_live_turn(msg,sid,lid=None):
    if lid=="SE-99999": return R(sid,lid,status=p.LIVE_REVIEW,errors=["CRM lead not found"])
    sessions.setdefault(sid,S(sid,lid))
    return R(sid,lid,"Verified live response.")
def get_live_session(sid): return sessions.get(sid)
def reset_live_session(sid): sessions.pop(sid,None)
p.run_live_turn=run_live_turn; p.get_live_session=get_live_session; p.reset_live_session=reset_live_session
sys.modules[p.__name__]=p

g=importlib.import_module("Sayyed_EdVantage_PHASE4_INTEGRATION07")
def check(n,x):
    if not x: raise AssertionError(n)
    print("PASS:",n)

def main():
    g.reset_live_session("LIVE_INT_07")
    r=g.ask_live_agent("Hello","LIVE_INT_07","SE-00001")
    check("gateway ready",r.status==g.GATEWAY_READY)
    check("respond mode",r.mode=="RESPOND")
    check("session preserved",r.session_id=="LIVE_INT_07")
    check("lead preserved",r.lead_id=="SE-00001")
    check("CRM profile",r.crm_profile["name"]=="Test Student")
    check("response exposed",r.response_text=="Verified live response.")
    check("safety",not any([r.executor_invoked,r.execution_authorized,r.crm_write,r.message_sent,r.external_action]))
    check("validation",g.validate_gateway_result(r)==[])
    check("query wrapper",g.live_agent_query("Fee?","LIVE_INT_07")=="Verified live response.")
    check("snapshot",g.gateway_snapshot("LIVE_INT_07")["lead_id"]=="SE-00001")
    bad=g.ask_live_agent("Continue","LIVE_INT_07_MISSING","SE-99999")
    check("missing lead review",bad.status==g.GATEWAY_REVIEW)
    check("missing lead no response",bad.response_text=="")
    g.reset_live_session("LIVE_INT_07")
    check("reset local session",g.gateway_snapshot("LIVE_INT_07") is None)
    print()
    print("PHASE 4 INTEGRATION 07 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")
if __name__=="__main__": main()
