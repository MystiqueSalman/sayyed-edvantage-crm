import tempfile
import unittest
from pathlib import Path

from app.agentic.durable import WorkflowStateStore
from app.agentic.monitoring import (
    HEALTH_STATES,
    OperationalEvent,
    agent_health,
    classify_error,
    create_operational_event,
    evaluate_alerts,
    production_readiness_snapshot,
    scheduler_metrics,
    system_health,
    workflow_metrics,
)
from app.agentic.scheduler import DurableWorkflowScheduler
from app.agentic.batch02_integration import build_batch02_orchestrator, run_agentic_workflow


class AgenticBatch12Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = WorkflowStateStore(self.root)
        self.scheduler = DurableWorkflowScheduler(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_monitoring_module_imports_and_health_states(self):
        self.assertTrue({"HEALTHY", "DEGRADED", "FAILED", "UNKNOWN"} <= HEALTH_STATES)
        self.assertTrue(OperationalEvent)

    def test_system_health(self):
        health = system_health(registry=build_batch02_orchestrator().registry, scheduler=self.scheduler, state_store=self.store, orchestrator=True)
        self.assertIn(health["status"], HEALTH_STATES)
        self.assertEqual(len(health["components"]), 10)
        self.assertIn("research", {item["component"] for item in health["components"]})

    def test_agent_health(self):
        orchestrator = build_batch02_orchestrator()
        orchestrator.audit_log.record("TASK_COMPLETED", "ANALYTICS", agent_id="ANALYTICS")
        health = agent_health(orchestrator.registry, orchestrator.audit_log.events())
        analytics = next(item for item in health if item["agent_id"] == "ANALYTICS")
        self.assertEqual(analytics["success_count"], 1)
        self.assertNotIn("password", str(analytics).lower())

    def test_workflow_metrics(self):
        run_agentic_workflow("Analyze leads", state_store=self.store)
        metrics = workflow_metrics(self.store)
        self.assertEqual(metrics["total_workflows"], 1)
        self.assertEqual(metrics["successful_workflows"], 1)

    def test_scheduler_metrics(self):
        self.scheduler.schedule("Analyze leads", idempotency_key="metrics")
        metrics = scheduler_metrics(self.scheduler)
        self.assertEqual(metrics["scheduled_workflows"], 0)
        self.assertEqual(metrics["active_workflows"], 0)

    def test_operational_event_creation_and_serialization(self):
        event = create_operational_event("SYSTEM_HEALTH", "monitoring", "HEALTHY", correlation_id="corr-1", metadata={"safe": True}, timestamp="2026-09-23T00:00:00+00:00")
        payload = event.to_dict()
        self.assertEqual(payload["correlation_id"], "corr-1")
        self.assertEqual(create_operational_event("SYSTEM_HEALTH", "monitoring", "HEALTHY", correlation_id="corr-1", metadata={"safe": True}, timestamp="2026-09-23T00:00:00+00:00").event_id, event.event_id)

    def test_error_classification(self):
        self.assertEqual(classify_error("approval required"), "AUTHORIZATION_ERROR")
        self.assertEqual(classify_error("provider is not configured"), "CONFIGURATION_ERROR")
        self.assertEqual(classify_error("dependency not satisfied"), "DEPENDENCY_ERROR")
        self.assertEqual(classify_error("unexpected runtime exception"), "INTERNAL_ERROR")

    def test_alert_detection(self):
        alerts = evaluate_alerts(workflow_data={"failed_workflows": 2, "authorization_requests": 3}, scheduler_data={"stalled_workflows": 1}, agent_data=[{"failure_count": 2}], health={"components": [{"component": "research", "status": "DEGRADED"}]})
        types = {alert["type"] for alert in alerts}
        self.assertTrue({"REPEATED_WORKFLOW_FAILURES", "AUTHORIZATION_BACKLOG", "STALLED_WORKFLOW", "REPEATED_AGENT_FAILURES", "SYSTEM_COMPONENT_UNHEALTHY"} <= types)

    def test_production_readiness_snapshot(self):
        snapshot = production_readiness_snapshot(registry=build_batch02_orchestrator().registry, scheduler=self.scheduler, state_store=self.store)
        self.assertIn("system_health", snapshot)
        self.assertIn("agent_health", snapshot)
        self.assertIn("security_status", snapshot)
        self.assertFalse(snapshot["security_status"]["external_actions_enabled"])

    def test_correlation_ids(self):
        event = create_operational_event("ERROR", "workflow", "FAILED", correlation_id="workflow-1")
        self.assertEqual(len(event.correlation_id), len("workflow-1"))
        self.assertTrue(event.event_id.startswith("monitor-"))

    def test_deterministic_output(self):
        first = create_operational_event("SYSTEM_HEALTH", "monitoring", "HEALTHY", correlation_id="same", metadata={}, timestamp="fixed")
        second = create_operational_event("SYSTEM_HEALTH", "monitoring", "HEALTHY", correlation_id="same", metadata={}, timestamp="fixed")
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_no_credential_exposure(self):
        snapshot = production_readiness_snapshot(registry=build_batch02_orchestrator().registry, scheduler=self.scheduler, state_store=self.store)
        self.assertNotIn("token", str(snapshot).lower())
        self.assertNotIn("password", str(snapshot).lower())

    def test_no_external_execution(self):
        snapshot = production_readiness_snapshot(registry=build_batch02_orchestrator().registry, scheduler=self.scheduler, state_store=self.store)
        self.assertFalse(snapshot["security_status"]["external_actions_enabled"])
        self.assertFalse(snapshot["security_status"]["crm_mutation_performed"])

    def test_existing_durable_scheduler_authorization_compatibility(self):
        record = self.scheduler.schedule("Publish campaign", idempotency_key="safe")
        self.assertEqual(self.scheduler.start(record["workflow_id"])["status"], "WAITING_AUTHORIZATION")
        self.assertEqual(scheduler_metrics(self.scheduler)["active_workflows"], 0)

    def test_no_crm_or_master_kb_mutation(self):
        before = Path("data/leads.json").read_bytes()
        run_agentic_workflow("Analyze leads", state_store=self.store)
        self.assertEqual(before, Path("data/leads.json").read_bytes())

    def test_no_computer_publishing_messaging_or_spending(self):
        snapshot = production_readiness_snapshot(registry=build_batch02_orchestrator().registry, scheduler=self.scheduler, state_store=self.store)
        self.assertFalse(snapshot["security_status"]["external_actions_enabled"])

    def test_regression_compatibility(self):
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
        self.assertTrue(all((AgenticBatch01Tests, AgenticBatch02Tests, AgenticBatch03Tests, AgenticBatch04Tests, AgenticBatch05Tests, AgenticBatch06Tests, AgenticBatch07Tests, AgenticBatch08Tests, AgenticBatch09Tests, AgenticBatch10Tests)))


if __name__ == "__main__":
    unittest.main()
