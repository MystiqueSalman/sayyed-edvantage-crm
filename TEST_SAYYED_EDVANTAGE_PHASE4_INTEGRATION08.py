"""Phase 4 Integration 08 verification."""
import sys, types, importlib

p = types.ModuleType("Sayyed_EdVantage_PHASE4_INTEGRATION07")
p.GATEWAY_READY="LIVE_GATEWAY_READY"
p.GATEWAY_REVIEW="LIVE_GATEWAY_REVIEW"
p.GATEWAY_BLOCKED="LIVE_GATEWAY_BLOCKED"
p.GATEWAY_CLARIFICATION="LIVE_GATEWAY_CLARIFICATION"
p.GATEWAY_UNKNOWN="LIVE_GATEWAY_UNKNOWN"
p.RESPOND="RESPOND"

class R:
    def __init__(self,sid,lid,text="Verified session response.",status=p.GATEWAY_READY):
        self.status=status; self.mode=p.RESPOND; self.session_id=sid
        self.lead_id=lid; self.response_text=text; self.turn_count=1
        self.crm_profile={"lead_id":lid,"name":"Test Student"} if lid else None
        self.errors=[]
        self.executor_invoked=False; self.execution_authorized=False
        self.crm_write=False; self.message_sent=False; self.external_action=False

def ask_live_agent(msg,sid,lid=None):
    if lid=="SE-99999":
        x=R(sid,lid,"",p.GATEWAY_REVIEW); x.errors=["CRM lead not found"]; return x
    return R(sid,lid)

def gateway_snapshot(sid): return None
def reset_live_session(sid): pass
def validate_gateway_result(r): return []

p.ask_live_agent=ask_live_agent
p.gateway_snapshot=gateway_snapshot
p.reset_live_session=reset_live_session
p.validate_gateway_result=validate_gateway_result
sys.modules[p.__name__]=p

m=importlib.import_module("Sayyed_EdVantage_PHASE4_INTEGRATION08")

def check(name, condition):
    if not condition: raise AssertionError(name)
    print("PASS:", name)

def main():
    m.clear_session("LIVE_INT_08")
    s=m.start_session("LIVE_INT_08","SE-00001")
    check("session created",s.session_id=="LIVE_INT_08")
    check("lead bound",s.lead_id=="SE-00001")

    r, e=m.send_turn("Hello","LIVE_INT_08")
    check("first turn ready",r.status=="LIVE_GATEWAY_READY")
    check("first turn no errors",e==[])
    check("session state stores gateway status",m.get_session("LIVE_INT_08").last_status=="LIVE_GATEWAY_READY")
    check("turn counted",m.get_session("LIVE_INT_08").turn_count==1)

    r2,e2=m.send_turn("What is the fee?","LIVE_INT_08")
    check("follow-up uses same session",r2.session_id=="LIVE_INT_08")
    check("lead remains bound",r2.lead_id=="SE-00001")
    check("second turn counted",m.get_session("LIVE_INT_08").turn_count==2)

    try:
        m.start_session("LIVE_INT_08","SE-00002")
        conflict=False
    except ValueError:
        conflict=True
    check("different lead is rejected",conflict)

    r3,e3=m.send_turn("Hello","LIVE_INT_08","SE-00002")
    check("lead conflict fails closed",r3 is None)
    check("lead conflict has error",e3==["session lead_id conflict"])

    bad,e4=m.send_turn("Hello","LIVE_INT_08_MISSING","SE-99999")
    check("missing CRM lead returns review",bad is not None and bad.status=="LIVE_GATEWAY_REVIEW")
    check("missing CRM lead has no response",bad.response_text=="")

    m.end_session("LIVE_INT_08")
    ended,e5=m.send_turn("Another turn","LIVE_INT_08")
    check("ended session rejects turns",ended is None)
    check("ended session reports error",e5==["session is not active"])

    m.clear_session("LIVE_INT_08")
    check("clear removes managed session",m.get_session("LIVE_INT_08") is None)

    print()
    print("PHASE 4 INTEGRATION 08 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")

if __name__=="__main__": main()
