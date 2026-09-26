from Sayyed_EdVantage_PHASE4_FINAL_CLOSURE import *

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS: {name}")

def main():
    ready = build_phase4_closure(
        integration_count=10,
        session_id="PHASE4_SESSION",
        lead_id="SE-00001",
    )
    check("closure result created", isinstance(ready, Phase4ClosureResult))
    check("closure ready", ready.status == PHASE4_CLOSURE_READY)
    check("live testing ready", ready.live_test_status == LIVE_TEST_READY)
    check("integration count retained", ready.integration_count == 10)
    check("session retained", ready.session_id == "PHASE4_SESSION")
    check("lead retained", ready.lead_id == "SE-00001")
    check("master KB verified", "MASTER_KB" in ready.verified_components)
    check("AI cores verified", "AI_CORE_01_30" in ready.verified_components)
    check("CRM read layer verified", "CRM_READ_LAYER" in ready.verified_components)
    check("integration 01 verified", "PHASE4_INTEGRATION_01" in ready.verified_components)
    check("integration 10 verified", "PHASE4_INTEGRATION_10" in ready.verified_components)
    check("live boundary verified", "LIVE_AGENT_BOUNDARY" in ready.verified_components)
    check("no closure errors", ready.errors == [])
    check("clean validation", validate_phase4_closure(ready) == [])

    blocked = build_phase4_closure(integration_count=9)
    check("incomplete integrations blocked", blocked.status == PHASE4_CLOSURE_BLOCKED)
    check("incomplete integrations block live test", blocked.live_test_status == LIVE_TEST_BLOCKED)

    review = build_phase4_closure(
        integration_count=10,
        component_results={"PHASE4_INTEGRATION_07": False},
    )
    check("component failure reviewed", review.status == PHASE4_CLOSURE_REVIEW)
    check("component failure blocks live test", review.live_test_status == LIVE_TEST_BLOCKED)
    check("component failure handoff", review.human_handoff is True)

    serialized = ready.to_dict()
    check("serialization validates", validate_serialized_phase4_closure(serialized) == [])

    unsafe = Phase4ClosureResult(
        status=PHASE4_CLOSURE_READY,
        live_test_status=LIVE_TEST_READY,
        integration_count=10,
        crm_write_occurred=True,
    )
    check("CRM write safety gate", any("CRM writes" in e for e in validate_phase4_closure(unsafe)))

    unsafe2 = Phase4ClosureResult(
        status=PHASE4_CLOSURE_READY,
        live_test_status=LIVE_TEST_READY,
        integration_count=10,
        message_sent=True,
    )
    check("message safety gate", any("message sending" in e for e in validate_phase4_closure(unsafe2)))

    unsafe3 = Phase4ClosureResult(
        status=PHASE4_CLOSURE_READY,
        live_test_status=LIVE_TEST_READY,
        integration_count=10,
        external_action_occurred=True,
    )
    check("external action safety gate", any("external actions" in e for e in validate_phase4_closure(unsafe3)))

    print("PHASE 4 FINAL CLOSURE TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")

if __name__ == "__main__":
    main()
