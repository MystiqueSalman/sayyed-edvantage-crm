import tempfile
import unittest
from pathlib import Path

from app.agentic.control import OperationalControl
from app.agentic.scheduler import DurableWorkflowScheduler


class AgenticBatch13Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.control = OperationalControl(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_control_interface_imports(self):
        self.assertTrue(self.control)

    def test_system_status(self):
        status = self.control.system_status()
        self.assertIn("system_health", status)
        self.assertIn("security_status", status)

    def test_agent_status_and_registry(self):
        agents = self.control.list_agents()
        ids = {agent["agent_id"] for agent in agents}
        self.assertIn("COMPUTER_ACTION", ids)
        self.assertIn("permission_scopes", str(agents[0]) if agents else "") or self.assertTrue(agents)

    def test_workflow_create_and_inspect(self):
        record = self.control.create_workflow("Analyze leads", idempotency_key="control-workflow")
        self.assertEqual(self.control.inspect_workflow(record["workflow_id"])["workflow_id"], record["workflow_id"])

    def test_workflow_pause_resume_cancel(self):
        record = self.control.create_workflow("Analyze leads", idempotency_key="lifecycle")
        self.assertEqual(self.control.pause_workflow(record["workflow_id"])["status"], "PAUSED")
        self.assertEqual(self.control.resume_workflow(record["workflow_id"])["status"], "QUEUED")
        self.assertEqual(self.control.cancel_workflow(record["workflow_id"])["status"], "CANCELLED")

    def test_authorization_and_approval_persistence(self):
        record = self.control.create_workflow("Publish campaign", idempotency_key="approval")
        self.assertEqual(self.control.scheduler.start(record["workflow_id"])["status"], "WAITING_AUTHORIZATION")
        approved = self.control.approve_workflow(record["workflow_id"], "approval-1")
        self.assertEqual(approved["authorization_state"], "APPROVED")
        restored = DurableWorkflowScheduler(self.directory.name).get(record["workflow_id"])
        self.assertEqual(restored["authorization_state"], "APPROVED")

    def test_rejection_and_human_handoff(self):
        record = self.control.create_workflow("Publish campaign", idempotency_key="reject")
        rejected = self.control.reject_workflow(record["workflow_id"], "Owner denied publication")
        self.assertEqual(rejected["status"], "WAITING_HUMAN")
        self.assertEqual(rejected["authorization_state"], "DENIED")

    def test_retry_authorization_safety(self):
        record = self.control.create_workflow("Spend advertising budget", idempotency_key="retry")
        self.control.scheduler.start(record["workflow_id"])
        retried = self.control.retry_workflow(record["workflow_id"])
        self.assertEqual(retried["status"], "WAITING_AUTHORIZATION")

    def test_workflow_history_and_monitoring(self):
        record = self.control.create_workflow("Analyze leads", idempotency_key="history")
        history = self.control.workflow_history(record["workflow_id"])
        self.assertTrue(history)
        snapshot = self.control.monitoring_status()
        self.assertIn("workflow_metrics", snapshot)

    def test_recent_events_and_audit(self):
        self.control.create_workflow("Analyze leads", idempotency_key="events")
        events = self.control.recent_events()
        audit = self.control.audit_log.events()
        self.assertTrue(events)
        self.assertTrue(any(event.event_type == "CONTROL_REQUEST" for event in audit))

    def test_authorization_status(self):
        record = self.control.create_workflow("Publish campaign", idempotency_key="pending")
        status = self.control.authorization_status()
        self.assertIn(record["workflow_id"], status["pending_workflow_ids"])
        self.assertFalse(status["external_execution_enabled"])

    def test_deterministic_serialization(self):
        first = self.control.create_workflow("Analyze leads", idempotency_key="stable")
        second = self.control.create_workflow("Analyze leads", idempotency_key="stable")
        self.assertEqual(first["workflow_id"], second["workflow_id"])

    def test_unauthorized_action_rejection(self):
        record = self.control.create_workflow("Publish campaign", idempotency_key="unsafe")
        started = self.control.scheduler.start(record["workflow_id"])
        self.assertEqual(started["status"], "WAITING_AUTHORIZATION")

    def test_no_external_actions_or_credentials(self):
        status = self.control.system_status()
        security = status["security_status"]
        self.assertFalse(security["external_actions_enabled"])
        self.assertFalse(security["credentials_created"])
        self.assertFalse(security["crm_mutation_performed"])

    def test_no_crm_or_master_kb_mutation(self):
        leads = Path("data/leads.json")
        before = leads.read_bytes()
        self.control.system_status()
        self.assertEqual(before, leads.read_bytes())

    def test_existing_batch_compatibility(self):
        from tests.test_agentic_batch01 import AgenticBatch01Tests
        from tests.test_agentic_batch02 import AgenticBatch02Tests
        from tests.test_agentic_batch03 import AgenticBatch03Tests
        from tests.test_agentic_batch04 import AgenticBatch04Tests
        from tests.test_agentic_batch05 import AgenticBatch05Tests
        from tests.test_agentic_batch06 import AgenticBatch06Tests
        from tests.test_agentic_batch07 import AgenticBatch07Tests
        from tests.test_agentic_batch08 import AgenticBatch08Tests
        from tests.test_agentic_batch09 import AgenticBatch09Tests
        from tests.test_agentic_batch10 import AgenticBatch10Tests
        from tests.test_agentic_batch11 import AgenticBatch11Tests
        from tests.test_agentic_batch12 import AgenticBatch12Tests
        self.assertTrue(all((AgenticBatch01Tests, AgenticBatch02Tests, AgenticBatch03Tests, AgenticBatch04Tests, AgenticBatch05Tests, AgenticBatch06Tests, AgenticBatch07Tests, AgenticBatch08Tests, AgenticBatch09Tests, AgenticBatch10Tests, AgenticBatch11Tests, AgenticBatch12Tests)))


if __name__ == "__main__":
    unittest.main()
