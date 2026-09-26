import unittest

from app.agentic.batch02_integration import build_batch02_orchestrator, run_agentic_workflow
from app.agentic.models import ActionLevel, AgentContext, Task
from app.agentic.safety_auth import classify_action
from app.agentic.workflow import TaskGraph, decompose_request


class AgenticBatch08Tests(unittest.TestCase):
    def test_orchestrator_registration(self):
        ids = {agent.agent_id for agent in build_batch02_orchestrator().registry.list()}
        self.assertTrue({"ANALYTICS", "RESEARCH", "SAFETY_AUTH", "MARKETING", "SOCIAL_MEDIA"} <= ids)

    def test_task_creation_and_graph(self):
        graph = TaskGraph()
        first = graph.add_task("MARKETING", "strategy")
        second = graph.add_task("CONTENT", "copy", dependencies=[first.task_id], execution_level=ActionLevel.PREPARE)
        self.assertEqual(second.status, "PENDING")
        self.assertEqual(graph.validate(), [])

    def test_dependency_handling(self):
        graph = decompose_request("Create a complete Data Science admission campaign")
        ready = graph.ready_tasks()
        self.assertEqual({task.agent for task in ready}, {"MARKETING"})

    def test_parallel_planning(self):
        graph = decompose_request("Create a complete Data Science admission campaign")
        marketing = next(task for task in graph.tasks.values() if task.agent == "MARKETING")
        group = graph.parallel_groups()
        self.assertTrue(any({task.agent for task in graph.tasks.values() if task.task_id in ids} >= {"CONTENT", "IMAGE_AD", "VIDEO_AD"} for ids in group))
        self.assertEqual(marketing.dependencies, [])

    def test_sequential_planning(self):
        graph = decompose_request("Handle this student's enquiry and prepare the next follow-up")
        by_agent = {task.agent: task for task in graph.tasks.values()}
        self.assertIn(by_agent["SALES"].task_id, by_agent["COUNSELLING"].dependencies)
        self.assertIn(by_agent["COUNSELLING"].task_id, by_agent["MEMORY"].dependencies)
        self.assertIn(by_agent["MEMORY"].task_id, by_agent["CRM"].dependencies)

    def test_agent_selection(self):
        self.assertIn("RESEARCH", {task.agent for task in decompose_request("Research Data Science trends").tasks.values()})
        self.assertIn("ANALYTICS", {task.agent for task in decompose_request("Analyze my leads").tasks.values()})

    def test_complex_task_decomposition(self):
        agents = {task.agent for task in decompose_request("Create a complete Data Science admission campaign").tasks.values()}
        self.assertTrue({"MARKETING", "CONTENT", "IMAGE_AD", "VIDEO_AD", "SOCIAL_MEDIA", "ADS", "LEAD_GENERATION"} <= agents)

    def test_marketing_workflow(self):
        result = run_agentic_workflow("Create a complete Data Science campaign")
        self.assertIn("MARKETING", {item["agent"] for item in result["agent_results"]})

    def test_admission_workflow(self):
        result = run_agentic_workflow("Handle this student's enquiry and prepare the next follow-up")
        self.assertIn("FOLLOW_UP", {item["agent"] for item in result["agent_results"]})

    def test_crm_workflow(self):
        result = run_agentic_workflow("Analyze this lead and prepare the next follow-up")
        self.assertIn("ANALYTICS", {item["agent"] for item in result["agent_results"]})

    def test_analytics_research_workflow(self):
        graph = decompose_request("Analyze campaign and research why performance changed")
        self.assertEqual({task.agent for task in graph.tasks.values()}, {"ANALYTICS", "RESEARCH"})

    def test_research_workflow(self):
        result = run_agentic_workflow("Research current Data Science education trends")
        self.assertEqual(result["final_status"], "COMPLETED")

    def test_result_aggregation(self):
        result = run_agentic_workflow("Analyze current admissions funnel")
        for key in ("workflow_id", "objective", "completed_tasks", "blocked_tasks", "failed_tasks", "agent_results", "observations", "recommendations", "final_status"):
            self.assertIn(key, result)

    def test_conflict_detection(self):
        graph = TaskGraph()
        first = graph.add_task("A", "one")
        second = graph.add_task("B", "two")
        first.status = second.status = "COMPLETED"
        first.result = {"claim": "one"}
        second.result = {"claim": "two"}
        from app.agentic.workflow import aggregate_workflow
        result = aggregate_workflow(graph, "conflict")
        self.assertEqual(result["final_status"], "CONFLICT_DETECTED")

    def test_missing_input_handling(self):
        graph = decompose_request("Publish the campaign")
        result = run_agentic_workflow("Publish the campaign")
        self.assertTrue(result["human_handoff_required"] or result["authorization_required"])

    def test_human_handoff(self):
        result = run_agentic_workflow("Publish the campaign")
        self.assertTrue(result["human_handoff_required"])

    def test_safety_gate(self):
        result = run_agentic_workflow("Publish the campaign")
        self.assertIn("SAFETY_AUTH", {item["agent"] for item in result["agent_results"]})
        self.assertEqual(result["final_status"], "WAITING_AUTHORIZATION")

    def test_execution_levels(self):
        self.assertEqual(classify_action("analyze campaign")["action_level"], "THINK")
        self.assertEqual(classify_action("prepare social post")["action_level"], "PREPARE")
        self.assertEqual(classify_action("publish campaign")["action_level"], "EXECUTE")

    def test_authorization_requirement(self):
        result = run_agentic_workflow("Launch a campaign with budget")
        self.assertTrue(result["authorization_required"])

    def test_no_unauthorized_actions(self):
        result = run_agentic_workflow("Publish the campaign")
        self.assertFalse(any(item["result"] and item["result"].get("execution_performed") for item in result["agent_results"]))

    def test_computer_action_boundary(self):
        self.assertNotIn("COMPUTER_ACTION", {task.agent for task in decompose_request("Publish the campaign").tasks.values()})

    def test_workflow_memory_and_audit(self):
        orchestrator = build_batch02_orchestrator()
        result = run_agentic_workflow("Analyze my leads", orchestrator=orchestrator)
        self.assertTrue(result["workflow_id"])
        event_types = {event.event_type for event in orchestrator.audit_log.events()}
        self.assertTrue({"WORKFLOW_CREATED", "TASK_DECOMPOSED", "WORKFLOW_RESULT_AGGREGATED"} <= event_types)

    def test_previous_batch_regression_imports(self):
        from tests.test_agentic_batch01 import AgenticBatch01Tests
        from tests.test_agentic_batch02 import AgenticBatch02Tests
        from tests.test_agentic_batch03 import AgenticBatch03Tests
        from tests.test_agentic_batch04 import AgenticBatch04Tests
        from tests.test_agentic_batch05 import AgenticBatch05Tests
        from tests.test_agentic_batch06 import AgenticBatch06Tests
        from tests.test_agentic_batch07 import AgenticBatch07Tests
        self.assertTrue(all((AgenticBatch01Tests, AgenticBatch02Tests, AgenticBatch03Tests, AgenticBatch04Tests, AgenticBatch05Tests, AgenticBatch06Tests, AgenticBatch07Tests)))


if __name__ == "__main__":
    unittest.main()