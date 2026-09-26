import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agentic.batch02_integration import (
    build_batch02_orchestrator,
    route_agent_id,
    run_agentic_request,
    run_cross_agent_follow_up,
)
from app.agentic.models import ActionLevel, AgentContext, Task, TaskStatus
from app.agentic.crm import crm_handler
from app.agentic.follow_up import follow_up_handler
from app.agentic.memory import memory_handler
from app.leads import lead_manager


class AgenticBatch03Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.leads_path = Path(self.temp_dir.name) / "leads.json"
        self.memory_path = Path(self.temp_dir.name) / "conversations.json"
        self.leads_patch = patch.object(lead_manager, "LEADS_FILE", self.leads_path)
        self.memory_patch = patch("app.ai.memory.MEMORY_FILE", self.memory_path)
        self.leads_patch.start()
        self.memory_patch.start()
        self.lead = lead_manager.create_lead(
            name="Batch Three Student",
            phone="9999999998",
            country="India",
            course_interest="Data Science",
            education="Graduate",
        )

    def tearDown(self):
        self.memory_patch.stop()
        self.leads_patch.stop()
        self.temp_dir.cleanup()

    def _context(self):
        return AgentContext(user_request="CRM request", lead_id=self.lead["lead_id"])

    def test_agent_registration(self):
        ids = {agent.agent_id for agent in build_batch02_orchestrator().registry.list()}
        self.assertTrue({"CRM", "MEMORY", "FOLLOW_UP"} <= ids)

    def test_crm_read(self):
        result = crm_handler(Task("status", "CRM", input={"operation": "crm_context"}), self._context())
        self.assertEqual(result["data"]["lead_id"], self.lead["lead_id"])
        self.assertFalse(result["execution_performed"])

    def test_crm_write_protection_preserves_all_data(self):
        before = self.leads_path.read_bytes()
        task = Task(
            "Update pipeline",
            "CRM",
            input={"action": "change_pipeline_stage", "lead_id": self.lead["lead_id"], "status": "Interested"},
            action_level=ActionLevel.EXECUTE,
        )
        result = build_batch02_orchestrator().run(task, self._context())
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertEqual(before, self.leads_path.read_bytes())

    def test_authorized_crm_write_verifies_and_audits(self):
        orchestrator = build_batch02_orchestrator()
        task = Task(
            "Update pipeline",
            "CRM",
            input={"action": "change_pipeline_stage", "lead_id": self.lead["lead_id"], "status": "Interested"},
            action_level=ActionLevel.EXECUTE,
        )
        waiting = orchestrator.run(task, self._context())
        waiting_status = waiting.status
        result = orchestrator.run_authorized(task, self._context(), "batch03-approval")
        self.assertIs(waiting_status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertEqual(result.output["execution_performed"], True)
        self.assertEqual(lead_manager.get_lead(self.lead["lead_id"])["status"], "Interested")
        self.assertEqual([event.event_type for event in orchestrator.audit_log.events()], [
            "TASK_AUTHORIZATION_EVALUATED", "TASK_AUTHORIZATION_EVALUATED", "TASK_COMPLETED"
        ])

    def test_memory_retrieval_and_continuity(self):
        from app.ai.memory import save_message
        save_message("batch03", "user", "I asked about Data Science")
        result = memory_handler(Task("previous", "MEMORY"), AgentContext(user_request="previous", session_id="batch03"))
        self.assertEqual(result["previous_questions"], ["I asked about Data Science"])

    def test_memory_crm_reconciliation_and_conflict(self):
        from app.ai.memory import save_message
        save_message("batch03", "user", "I live in Canada")
        result = memory_handler(
            Task("reconcile", "MEMORY"),
            AgentContext(user_request="reconcile", session_id="batch03", crm_state={"country": "India", "course_interest": "Data Science"}),
        )
        self.assertIn("crm_country_not_present_in_conversation", result["conflicts"])
        self.assertEqual(result["crm_context"]["country"], "India")

    def test_missing_memory_and_privacy_boundary(self):
        result = memory_handler(Task("missing", "MEMORY"), AgentContext(user_request="missing", session_id="empty"))
        self.assertEqual(result["conversation_context"], [])
        self.assertNotIn("phone", result["student_context"])

    def test_memory_write_protection(self):
        result = memory_handler(Task("save", "MEMORY", input={"action": "save_message", "content": "secret"}), AgentContext(user_request="save", session_id="batch03"))
        self.assertEqual(result["authorization_required"], True)
        self.assertFalse(result["execution_performed"])

    def test_follow_up_discovery(self):
        lead_manager.update_lead(self.lead["lead_id"], follow_up_date="2000-01-01")
        result = follow_up_handler(Task("discover", "FOLLOW_UP"), AgentContext(user_request="discover"))
        self.assertEqual(result["follow_up_candidates"][0]["lead_id"], self.lead["lead_id"])
        self.assertIn("overdue_or_due", result["follow_up_candidates"][0]["reasons"])

    def test_follow_up_preparation(self):
        result = follow_up_handler(Task("prepare", "FOLLOW_UP", input={"action": "prepare", "lead_id": self.lead["lead_id"]}), self._context())
        self.assertEqual(result["status"], "prepared")
        self.assertFalse(result["execution_performed"])
        self.assertIn("Data Science", result["draft_message"])

    def test_follow_up_send_protection(self):
        result = run_agentic_request("Send the follow-up", input={"agent_id": "FOLLOW_UP", "action": "send", "lead_id": self.lead["lead_id"]})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        result = build_batch02_orchestrator().run_authorized(result, AgentContext(user_request="Send", lead_id=self.lead["lead_id"]), "send-approval")
        self.assertFalse(result.output["message_sent"])
        self.assertIn("provider", result.output["errors"][0])

    def test_routing(self):
        self.assertEqual(route_agent_id("What is the status of SE-00001?"), "CRM")
        self.assertEqual(route_agent_id("What did this student ask previously?"), "MEMORY")
        self.assertEqual(route_agent_id("Which leads need follow-up?"), "FOLLOW_UP")

    def test_cross_agent_workflow(self):
        result = run_cross_agent_follow_up(self.lead["lead_id"], session_id="batch03")
        self.assertEqual(result["CRM"]["status"], "completed")
        self.assertEqual(result["MEMORY"]["status"], "completed")
        self.assertEqual(result["FOLLOW_UP"]["status"], "prepared")

    def test_existing_crm_regression(self):
        self.assertEqual(lead_manager.get_lead(self.lead["lead_id"])["course_interest"], "Data Science")

    def test_existing_master_kb_regression(self):
        from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge
        bridge = build_authoritative_live_bridge(project_root=".", require_offerings=True)
        self.assertEqual(bridge.status, "BRIDGE_READY")
        self.assertIn("SE-DSP-001", bridge.course_ids)

    def test_commercial_bridge_gap_is_explicit(self):
        from Sayyed_EdVantage_PHASE4_INTEGRATION04 import build_authoritative_live_bridge
        bridge = build_authoritative_live_bridge(project_root=".", require_offerings=True)
        self.assertNotIn("SE-DA-001", bridge.course_ids)
        self.assertNotIn("SE-OFFER-DA-INDIA", bridge.offering_ids)

    def test_existing_ai_regression_imports(self):
        from app.ai.agent import ask_agent
        self.assertTrue(callable(ask_agent))


if __name__ == "__main__":
    unittest.main()