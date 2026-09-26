import json
import tempfile
import unittest
from pathlib import Path

from app.agentic.batch02_integration import (
    build_durable_orchestrator,
    build_batch02_orchestrator,
    resume_agentic_workflow,
    run_agentic_workflow,
)
from app.agentic.durable import PersistentAuditLog, WorkflowStateStore
from app.agentic.models import ActionLevel, AgentContext, TaskStatus
from app.agentic.workflow import TaskGraph, execute_workflow


class AgenticBatch09Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = WorkflowStateStore(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_durable_workflow_creation_and_checkpoint(self):
        result = run_agentic_workflow("Analyze current admissions funnel", state_store=self.store)
        self.assertTrue(result["workflow_id"])
        self.assertIsNotNone(self.store.get(result["workflow_id"]))
        self.assertTrue(self.store.history(result["workflow_id"]))
        self.assertEqual(self.store.latest_checkpoint(result["workflow_id"])["event_type"], "workflow_completed")

    def test_task_persistence(self):
        graph = TaskGraph()
        task = graph.add_task("ANALYTICS", "analyze")
        self.store.save(graph.snapshot("analyze"))
        loaded = TaskGraph.from_snapshot(self.store.get(graph.workflow_id))
        self.assertIn(task.task_id, loaded.tasks)
        self.assertEqual(loaded.tasks[task.task_id].status, "READY")

    def test_resume_preserves_completed_and_continues_pending(self):
        graph = TaskGraph()
        first = graph.add_task("ANALYTICS", "first")
        second = graph.add_task("RESEARCH", "second", dependencies=[first.task_id])
        calls = []
        handlers = {
            "ANALYTICS": lambda task, context: calls.append("ANALYTICS") or {"ok": True},
            "RESEARCH": lambda task, context: calls.append("RESEARCH") or {"ok": True},
        }
        orchestrator = build_batch02_orchestrator()
        first_result = execute_workflow(graph, "resume test", handlers, orchestrator, state_store=self.store, max_tasks=1)
        self.assertEqual(first_result["final_status"], "PAUSED")
        self.assertEqual(calls, ["ANALYTICS"])
        resumed = __import__("app.agentic.workflow", fromlist=["resume_workflow"]).resume_workflow(graph.workflow_id, "resume test", handlers, orchestrator, self.store)
        self.assertEqual(resumed["final_status"], "COMPLETED")
        self.assertEqual(calls, ["ANALYTICS", "RESEARCH"])

    def test_idempotency_does_not_rerun_completed_tasks(self):
        graph = TaskGraph()
        task = graph.add_task("ANALYTICS", "first")
        calls = []
        handlers = {"ANALYTICS": lambda task, context: calls.append(task.task_id) or {"ok": True}}
        execute_workflow(graph, "idempotent", handlers, build_batch02_orchestrator(), state_store=self.store)
        __import__("app.agentic.workflow", fromlist=["resume_workflow"]).resume_workflow(graph.workflow_id, "idempotent", handlers, build_batch02_orchestrator(), self.store)
        self.assertEqual(len(calls), 1)

    def test_failure_and_retry_state(self):
        graph = TaskGraph()
        task = graph.add_task("ANALYTICS", "fails")
        handlers = {"ANALYTICS": lambda task, context: (_ for _ in ()).throw(RuntimeError("boom"))}
        result = execute_workflow(graph, "failure", handlers, build_batch02_orchestrator(), state_store=self.store)
        self.assertEqual(result["final_status"], "FAILED")
        self.assertEqual(graph.tasks[task.task_id].status, "FAILED")
        graph.retry_task(task.task_id)
        self.assertEqual(graph.tasks[task.task_id].retry_count, 1)

    def test_blocked_state_is_persisted(self):
        graph = TaskGraph()
        task = graph.add_task("MISSING", "blocked")
        result = execute_workflow(graph, "blocked", {}, build_batch02_orchestrator(), state_store=self.store)
        self.assertEqual(result["final_status"], "WAITING_HUMAN")
        self.assertEqual(self.store.get(graph.workflow_id)["blocked_steps"], [task.task_id])

    def test_authorization_state_survives_restart(self):
        graph = TaskGraph()
        task = graph.add_task("SOCIAL_MEDIA", "publish", execution_level=ActionLevel.EXECUTE, input={"action": "publish"})
        calls = []
        handlers = {"SOCIAL_MEDIA": lambda task, context: calls.append(True) or {"published": True}}
        result = execute_workflow(graph, "publish", handlers, build_batch02_orchestrator(), state_store=self.store)
        self.assertEqual(result["final_status"], "WAITING_AUTHORIZATION")
        self.assertEqual(calls, [])
        recovered = __import__("app.agentic.workflow", fromlist=["resume_workflow"]).resume_workflow(graph.workflow_id, "publish", handlers, build_batch02_orchestrator(), self.store)
        self.assertEqual(recovered["final_status"], "WAITING_AUTHORIZATION")
        self.assertEqual(calls, [])

    def test_human_handoff_persistence(self):
        graph = TaskGraph()
        task = graph.add_task("HUMAN", "review")
        task.status = "WAITING_HUMAN"
        self.store.checkpoint(graph.workflow_id, "human_handoff", graph.snapshot("review"), reason="review required")
        loaded = self.store.get(graph.workflow_id)
        self.assertIn(task.task_id, loaded["human_handoff_state"])

    def test_persistent_audit_round_trip(self):
        path = self.root / "audit.json"
        log = PersistentAuditLog(path)
        event = log.record("TASK_COMPLETED", "ANALYTICS", workflow_id="w1", task_id="t1", execution_state="NOT_EXECUTED")
        restored = PersistentAuditLog(path)
        self.assertEqual(len(restored.events()), 1)
        self.assertEqual(restored.events()[0].event_id, event.event_id)
        self.assertFalse(restored.events()[0].details["execution_state"] == "EXECUTED")

    def test_workflow_history_is_read_only(self):
        result = run_agentic_workflow("Research Data Science trends", state_store=self.store)
        history = self.store.history(result["workflow_id"])
        self.assertGreaterEqual(len(history), 3)
        self.assertEqual(history[0]["event_type"], "workflow_created")

    def test_restart_recovery_from_disk(self):
        result = run_agentic_workflow("Analyze my leads", state_store=self.store)
        restarted_store = WorkflowStateStore(self.root)
        recovered = restarted_store.get(result["workflow_id"])
        self.assertEqual(recovered["workflow_id"], result["workflow_id"])
        self.assertTrue(recovered["completed_steps"])

    def test_external_retry_is_rejected(self):
        graph = TaskGraph()
        task = graph.add_task("SOCIAL_MEDIA", "publish", execution_level=ActionLevel.EXECUTE)
        task.status = "FAILED"
        with self.assertRaises(ValueError):
            graph.retry_task(task.task_id)

    def test_safety_regression_no_external_action(self):
        result = run_agentic_workflow("Publish the campaign", state_store=self.store)
        self.assertEqual(result["final_status"], "WAITING_AUTHORIZATION")
        self.assertFalse(any(item["result"] and item["result"].get("execution_performed") for item in result["agent_results"]))


if __name__ == "__main__":
    unittest.main()
