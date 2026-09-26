import unittest

from app.agentic.audit import AuditLog
from app.agentic.computer_action import UnconfiguredComputerAction
from app.agentic.models import (
    ActionLevel,
    AgentContext,
    Task,
    TaskStatus,
)
from app.agentic.orchestrator import Orchestrator
from app.agentic.registry import build_default_registry


class AgenticBatch01Tests(unittest.TestCase):
    def test_default_registry_contains_required_control_agents(self):
        registry = build_default_registry()
        agent_ids = {agent.agent_id for agent in registry.list()}
        self.assertTrue({"ORCHESTRATOR", "SAFETY_AUTH", "COMPUTER_ACTION"} <= agent_ids)
        self.assertEqual(
            registry.get("computer_action").permission_scopes,
            ("computer.use",),
        )

    def test_think_task_runs_and_is_audited(self):
        audit = AuditLog()
        orchestrator = Orchestrator(audit_log=audit)
        orchestrator.register_handler(
            "RESEARCH", lambda task, context: {"answer": "grounded"}
        )
        task = Task(user_request="Research course demand", agent_id="RESEARCH")

        result = orchestrator.run(task, AgentContext(user_request=task.user_request))

        self.assertIs(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output, {"answer": "grounded"})
        self.assertEqual(
            [event.event_type for event in audit.events()],
            ["TASK_AUTHORIZATION_EVALUATED", "TASK_COMPLETED"],
        )

    def test_execute_task_waits_for_authorization_then_runs(self):
        orchestrator = Orchestrator()
        calls = []
        orchestrator.register_handler(
            "CRM",
            lambda task, context: calls.append(task.task_id) or {"updated": True},
        )
        task = Task(
            user_request="Update the CRM",
            agent_id="CRM",
            action_level=ActionLevel.EXECUTE,
            input={"action": "update_crm"},
        )

        waiting = orchestrator.run(task, AgentContext(user_request=task.user_request))
        self.assertIs(waiting.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertEqual(calls, [])

        completed = orchestrator.run_authorized(
            task, AgentContext(user_request=task.user_request), "human-approval-1"
        )
        self.assertIs(completed.status, TaskStatus.COMPLETED)
        self.assertEqual(calls, [task.task_id])

    def test_computer_action_is_not_faked(self):
        action = UnconfiguredComputerAction()
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            action.execute(
                "open_browser",
                {},
                authorization=type("Approval", (), {"approved": True})(),
            )


if __name__ == "__main__":
    unittest.main()
