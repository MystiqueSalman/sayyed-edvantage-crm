import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.agentic.batch02_integration import build_workflow_scheduler, schedule_agentic_workflow
from app.agentic.scheduler import DurableWorkflowScheduler, operational_snapshot


class AgenticBatch10Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.scheduler = DurableWorkflowScheduler(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_scheduler_creation(self):
        self.assertIsInstance(self.scheduler, DurableWorkflowScheduler)

    def test_one_time_scheduling_and_persistence(self):
        record = self.scheduler.schedule("Analyze leads", idempotency_key="one")
        self.assertEqual(record["status"], "QUEUED")
        restored = DurableWorkflowScheduler(self.root).get(record["workflow_id"])
        self.assertEqual(restored["objective"], "Analyze leads")

    def test_future_scheduling(self):
        record = self.scheduler.schedule("Research trends", run_at=datetime.now(timezone.utc) + timedelta(hours=1), idempotency_key="future")
        self.assertEqual(record["status"], "SCHEDULED")
        self.assertEqual(self.scheduler.start_due(now=datetime.now(timezone.utc)), [])

    def test_recurring_scheduling(self):
        record = self.scheduler.schedule("Analyze leads", recurring_seconds=60, idempotency_key="recurring")
        completed = self.scheduler.complete(record["workflow_id"], result={"ok": True})
        self.assertEqual(completed["status"], "SCHEDULED")
        self.assertIsNotNone(completed["next_run_at"])

    def test_pause_resume_cancel(self):
        record = self.scheduler.schedule("Analyze leads", idempotency_key="lifecycle")
        self.assertEqual(self.scheduler.pause(record["workflow_id"])["status"], "PAUSED")
        self.assertEqual(self.scheduler.resume(record["workflow_id"])["status"], "QUEUED")
        self.assertEqual(self.scheduler.cancel(record["workflow_id"])["status"], "CANCELLED")

    def test_retry_and_exhaustion(self):
        record = self.scheduler.schedule("Analyze leads", max_retries=1, idempotency_key="retry")
        retry = self.scheduler.fail(record["workflow_id"], "temporary", retryable=True)
        self.assertEqual(retry["status"], "RETRY_PENDING")
        failed = self.scheduler.fail(record["workflow_id"], "again", retryable=True)
        self.assertEqual(failed["status"], "FAILED")

    def test_non_retryable_failure(self):
        record = self.scheduler.schedule("Analyze leads", idempotency_key="fatal")
        self.assertEqual(self.scheduler.fail(record["workflow_id"], "fatal", retryable=False)["status"], "FAILED")

    def test_stalled_detection(self):
        record = self.scheduler.schedule("Analyze leads", idempotency_key="stall")
        self.scheduler.start(record["workflow_id"])
        stalled = self.scheduler.detect_stalled(now=datetime.now(timezone.utc) + timedelta(hours=2), threshold_seconds=60)
        self.assertEqual(stalled[0]["workflow_id"], record["workflow_id"])

    def test_authorization_waiting_and_restart(self):
        record = self.scheduler.schedule("Publish campaign", idempotency_key="publish")
        started = DurableWorkflowScheduler(self.root).start(record["workflow_id"])
        self.assertEqual(started["status"], "WAITING_AUTHORIZATION")
        self.assertEqual(DurableWorkflowScheduler(self.root).start(record["workflow_id"])["status"], "WAITING_AUTHORIZATION")

    def test_human_handoff_persistence(self):
        record = self.scheduler.schedule("Review ambiguous lead", idempotency_key="human")
        updated = self.scheduler._transition(record["workflow_id"], "WAITING_HUMAN", "human_handoff", human_handoff_state={"reason": "review"})
        self.assertEqual(DurableWorkflowScheduler(self.root).get(record["workflow_id"])["status"], "WAITING_HUMAN")

    def test_workflow_isolation(self):
        first = self.scheduler.schedule("Analyze A", idempotency_key="a")
        second = self.scheduler.schedule("Analyze B", idempotency_key="b")
        self.scheduler.pause(first["workflow_id"])
        self.assertEqual(self.scheduler.get(second["workflow_id"])["status"], "QUEUED")

    def test_idempotent_operations(self):
        first = self.scheduler.schedule("Analyze leads", idempotency_key="same")
        second = self.scheduler.schedule("Analyze leads", idempotency_key="same")
        self.assertEqual(first["workflow_id"], second["workflow_id"])
        self.assertEqual(self.scheduler.pause(first["workflow_id"])["status"], "PAUSED")
        self.assertEqual(self.scheduler.pause(first["workflow_id"])["status"], "PAUSED")

    def test_conflicting_idempotency_key_is_rejected(self):
        self.scheduler.schedule("Analyze leads", idempotency_key="conflict")
        with self.assertRaises(ValueError):
            self.scheduler.schedule("Publish campaign", idempotency_key="conflict")

    def test_authorization_approval_is_explicit(self):
        record = self.scheduler.schedule("Publish campaign", idempotency_key="approval")
        self.assertEqual(self.scheduler.start(record["workflow_id"])["status"], "WAITING_AUTHORIZATION")
        approved = self.scheduler.approve(record["workflow_id"], "approval-1")
        self.assertEqual(approved["status"], "QUEUED")
        self.assertEqual(approved["authorization_state"], "APPROVED")

    def test_runner_failure_is_persisted(self):
        record = self.scheduler.schedule("Analyze leads", max_retries=0, idempotency_key="runner-failure")
        result = self.scheduler.start(record["workflow_id"], lambda value: (_ for _ in ()).throw(RuntimeError("runner failed")))
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["last_error"], "runner failed")

    def test_priority_orders_due_workflows(self):
        low = self.scheduler.schedule("Analyze low", priority=1, idempotency_key="low")
        high = self.scheduler.schedule("Analyze high", priority=10, idempotency_key="high")
        order = []
        self.scheduler.start_due(lambda value: order.append(value["workflow_id"]) or {})
        self.assertEqual(order, [high["workflow_id"], low["workflow_id"]])

    def test_operational_events(self):
        record = self.scheduler.schedule("Analyze leads", idempotency_key="events")
        self.scheduler.pause(record["workflow_id"])
        events = self.scheduler._events()
        self.assertTrue(any(event["event_type"] == "workflow_created" for event in events))
        self.assertTrue(any(event["event_type"] == "workflow_paused" for event in events))

    def test_monitoring_snapshot_and_filters(self):
        self.scheduler.schedule("Analyze A", owner="alice", priority=10, idempotency_key="monitor-a")
        self.scheduler.schedule("Analyze B", owner="bob", priority=20, idempotency_key="monitor-b")
        self.assertEqual(len(self.scheduler.list(owner="alice", priority=10)), 1)
        snapshot = operational_snapshot(self.scheduler)
        self.assertEqual(snapshot["total_workflows"], 2)
        self.assertEqual(snapshot["queued"], 2)

    def test_start_due_runner(self):
        record = self.scheduler.schedule("Analyze leads", idempotency_key="runner")
        result = self.scheduler.start_due(lambda value: {"workflow_id": value["workflow_id"], "execution_performed": False})
        self.assertEqual(result[0]["status"], "COMPLETED")

    def test_orchestrator_integration_helper(self):
        record = schedule_agentic_workflow("Analyze leads", storage_root=str(self.root), idempotency_key="helper")
        self.assertTrue(build_workflow_scheduler(str(self.root)).get(record["workflow_id"]))

    def test_no_external_action(self):
        record = self.scheduler.schedule("Spend advertising budget", idempotency_key="spend")
        started = self.scheduler.start(record["workflow_id"], lambda value: {"execution_performed": True})
        self.assertEqual(started["status"], "WAITING_AUTHORIZATION")


if __name__ == "__main__":
    unittest.main()