"""Tests for Phase 4 Integration 09 — Live Conversation API."""

from Sayyed_EdVantage_PHASE4_INTEGRATION09 import (
    LiveConversationResult,
    LIVE_API_READY,
    LIVE_API_CLARIFICATION,
    LIVE_API_BLOCKED,
    LIVE_API_UNKNOWN,
    validate_live_conversation_result,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS: {name}")


def main():
    r = LiveConversationResult(
        status=LIVE_API_READY,
        session_id="TEST_SESSION_09",
        lead_id="SE-00001",
        response_text="Hello",
        response_allowed=True,
    )

    check("result object created", isinstance(r, LiveConversationResult))
    check("session id retained", r.session_id == "TEST_SESSION_09")
    check("lead id retained", r.lead_id == "SE-00001")
    check("ready response allowed", r.response_allowed is True)
    check("ready response has text", bool(r.response_text))
    check("clean result validates", validate_live_conversation_result(r) == [])

    blocked = LiveConversationResult(
        status=LIVE_API_BLOCKED,
        session_id="TEST_SESSION_09",
        lead_id=None,
        response_allowed=False,
    )
    check("blocked result validates", validate_live_conversation_result(blocked) == [])

    clarification = LiveConversationResult(
        status=LIVE_API_CLARIFICATION,
        session_id="TEST_SESSION_09",
        lead_id=None,
    )
    check("clarification result validates",
          validate_live_conversation_result(clarification) == [])

    unknown = LiveConversationResult(
        status=LIVE_API_UNKNOWN,
        session_id="TEST_SESSION_09",
        lead_id=None,
    )
    check("unknown result validates",
          validate_live_conversation_result(unknown) == [])

    unsafe = LiveConversationResult(
        status=LIVE_API_READY,
        session_id="TEST_SESSION_09",
        response_text="Unsafe",
        response_allowed=True,
        crm_write_occurred=True,
    )
    check("unsafe CRM write is rejected",
          any("CRM writes" in x for x in validate_live_conversation_result(unsafe)))

    unsafe2 = LiveConversationResult(
        status=LIVE_API_READY,
        session_id="TEST_SESSION_09",
        response_text="Unsafe",
        response_allowed=True,
        message_sent=True,
    )
    check("unsafe message send is rejected",
          any("message sending" in x for x in validate_live_conversation_result(unsafe2)))

    unsafe3 = LiveConversationResult(
        status=LIVE_API_READY,
        session_id="TEST_SESSION_09",
        response_text="Unsafe",
        response_allowed=True,
        external_action_occurred=True,
    )
    check("unsafe external action is rejected",
          any("external actions" in x for x in validate_live_conversation_result(unsafe3)))

    print("PHASE 4 INTEGRATION 09 TEST RESULT: ALL PASSED")
    print("RETURN CODE: 0")


if __name__ == "__main__":
    main()
