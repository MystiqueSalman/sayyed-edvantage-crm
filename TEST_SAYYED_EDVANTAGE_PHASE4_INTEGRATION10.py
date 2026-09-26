from Sayyed_EdVantage_PHASE4_INTEGRATION10 import (
    LIVE_BOUNDARY_READY,
    LIVE_BOUNDARY_CLARIFICATION,
    LIVE_BOUNDARY_REVIEW,
    LIVE_BOUNDARY_BLOCKED,
    LIVE_BOUNDARY_UNKNOWN,
    MODE_RESPOND,
    MODE_CLARIFY,
    MODE_HUMAN_REVIEW,
    MODE_NO_RESPONSE,
    LiveBoundaryResult,
    build_live_boundary_result,
    run_live_agent_boundary,
    validate_live_boundary_result,
    validate_serialized_live_boundary,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS: {name}")


def main():
    ready = build_live_boundary_result(
        session_id="TEST_SESSION_10",
        lead_id="SE-00001",
        user_message="What is Data Science?",
        raw_result={"response_text": "Data Science is a professional program."},
        provenance=["TEST"],
    )
    check("ready status", ready.status == LIVE_BOUNDARY_READY)
    check("ready mode", ready.mode == MODE_RESPOND)
    check("ready response allowed", ready.response_allowed is True)
    check("ready response preserved", ready.response_text.startswith("Data Science"))
    check("ready validates", validate_live_boundary_result(ready) == [])

    no_message = run_live_agent_boundary(
        "",
        "TEST_SESSION_10",
        agent_callable=lambda *_: "unused",
    )
    check("empty message clarifies", no_message.status == LIVE_BOUNDARY_CLARIFICATION)
    check("empty message mode", no_message.mode == MODE_CLARIFY)

    no_session = run_live_agent_boundary(
        "Hello",
        "",
        agent_callable=lambda *_: "unused",
    )
    check("missing session blocks", no_session.status == LIVE_BOUNDARY_BLOCKED)
    check("missing session mode", no_session.mode == MODE_NO_RESPONSE)

    missing_result = build_live_boundary_result(
        session_id="TEST_SESSION_10",
        raw_result=None,
    )
    check("missing result is unknown", missing_result.status == LIVE_BOUNDARY_UNKNOWN)
    check("missing result does not respond", missing_result.response_allowed is False)

    conflict = build_live_boundary_result(
        session_id="TEST_SESSION_10",
        raw_result={
            "response_text": "should not pass",
            "conflicts": ["CRM and conversation course conflict"],
        },
    )
    check("conflict requires review", conflict.status == LIVE_BOUNDARY_REVIEW)
    check("conflict uses human review", conflict.mode == MODE_HUMAN_REVIEW)
    check("conflict enables handoff", conflict.human_handoff is True)
    check("conflict hides response", conflict.response_text == "")

    error_result = build_live_boundary_result(
        session_id="TEST_SESSION_10",
        raw_result={"errors": ["upstream verification failed"]},
    )
    check("upstream error requires review", error_result.status == LIVE_BOUNDARY_REVIEW)
    check("upstream error uses handoff", error_result.human_handoff is True)

    fake_calls = []

    def fake_agent(message, session_id):
        fake_calls.append((message, session_id))
        return {"response": "Test response from injected agent."}

    injected = run_live_agent_boundary(
        "Hello",
        "TEST_SESSION_10",
        "SE-00001",
        agent_callable=fake_agent,
    )
    check("injected agent called once", fake_calls == [("Hello", "TEST_SESSION_10")])
    check("injected agent ready", injected.status == LIVE_BOUNDARY_READY)
    check("injected lead preserved", injected.lead_id == "SE-00001")

    serialized = injected.to_dict()
    check("serialization validates",
          validate_serialized_live_boundary(serialized) == [])

    bad_crm = LiveBoundaryResult(
        status=LIVE_BOUNDARY_READY,
        mode=MODE_RESPOND,
        session_id="TEST_SESSION_10",
        response_text="unsafe",
        response_allowed=True,
        crm_write_occurred=True,
    )
    check("CRM write rejected",
          any("CRM writes" in x for x in validate_live_boundary_result(bad_crm)))

    bad_message = LiveBoundaryResult(
        status=LIVE_BOUNDARY_READY,
        mode=MODE_RESPOND,
        session_id="TEST_SESSION_10",
        response_text="unsafe",
        response_allowed=True,
        message_sent=True,
    )
    check("message send rejected",
          any("message sending" in x for x in validate_live_boundary_result(bad_message)))

    bad_external = LiveBoundaryResult(
        status=LIVE_BOUNDARY_READY,
        mode=MODE_RESPOND,
        session_id="TEST_SESSION_10",
        response_text="unsafe",
        response_allowed=True,
        external_action_occurred=True,
    )
    check("external action rejected",
          any("external actions" in x for x in validate_live_boundary_result(bad_external)))

    bad_executor = LiveBoundaryResult(
        status=LIVE_BOUNDARY_READY,
        mode=MODE_RESPOND,
        session_id="TEST_SESSION_10",
        response_text="unsafe",
        response_allowed=True,
        executor_invoked=True,
    )
    check("executor invocation rejected",
          any("executor invocation" in x for x in validate_live_boundary_result(bad_executor)))

    bad_execution = LiveBoundaryResult(
        status=LIVE_BOUNDARY_READY,
        mode=MODE_RESPOND,
        session_id="TEST_SESSION_10",
        response_text="unsafe",
        response_allowed=True,
        execution_occurred=True,
    )
    check("execution rejected",
          any("execution is prohibited" in x for x in validate_live_boundary_result(bad_execution)))

    invalid_nonready = LiveBoundaryResult(
        status=LIVE_BOUNDARY_UNKNOWN,
        mode=MODE_NO_RESPONSE,
        session_id="TEST_SESSION_10",
        response_text="must be hidden",
        response_allowed=False,
    )
    check("non-ready response text rejected",
          any("must not expose response text" in x
              for x in validate_live_boundary_result(invalid_nonready)))

    print("PHASE 4 INTEGRATION 10 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")


if __name__ == "__main__":
    main()
