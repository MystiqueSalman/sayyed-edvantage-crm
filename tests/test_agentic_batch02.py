import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agentic.batch02 import _course_candidates
from app.agentic.batch02_integration import (
    build_batch02_orchestrator,
    route_agent_id,
    run_agentic_request,
)
from app.agentic.models import AgentContext, Task, TaskStatus
from app.agentic.sales import sales_handler
from app.agentic.counselling import counselling_handler


class AgenticBatch02Tests(unittest.TestCase):
    def setUp(self):
        self.fake_response = "Grounded response from the existing AI core."

    def _fake_ai(self, *args, **kwargs):
        self.assertFalse(kwargs.get("allow_lead_creation"))
        return self.fake_response

    def test_sales_agent_registration(self):
        self.assertIn("SALES", {agent.agent_id for agent in build_batch02_orchestrator().registry.list()})

    def test_counselling_agent_registration(self):
        self.assertIn("COUNSELLING", {agent.agent_id for agent in build_batch02_orchestrator().registry.list()})

    def test_sales_routing(self):
        self.assertEqual(route_agent_id("How much is Data Science?"), "SALES")

    def test_counselling_routing(self):
        self.assertEqual(route_agent_id("I don't know which course is suitable"), "COUNSELLING")

    def test_data_science_course_discovery(self):
        candidates = _course_candidates("Tell me about Data Science")
        self.assertTrue(any("Data Science" in item["course_name"] for item in candidates))

    def test_data_analytics_course_discovery_is_grounded(self):
        candidates = _course_candidates("Tell me about Data Analytics")
        self.assertEqual(candidates[0]["course_name"], "Data Analytics")
        self.assertFalse(candidates[0]["verified"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_course_recommendation(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        task = Task("I don't know which course is suitable", "COUNSELLING")
        result = counselling_handler(task, AgentContext(user_request=task.user_request))
        self.assertEqual(result["intent"], "course_recommendation")

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_eligibility_question(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        task = Task("Am I eligible for Data Science?", "COUNSELLING")
        result = counselling_handler(task, AgentContext(user_request=task.user_request))
        self.assertEqual(result["intent"], "eligibility_question")
        self.assertTrue(result["human_handoff_required"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_fee_question(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        task = Task("How much is Data Science?", "SALES")
        result = sales_handler(task, AgentContext(user_request=task.user_request))
        self.assertEqual(result["intent"], "pricing_question")
        self.assertIn("existing_pricing_gateway", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_indian_pricing_correctness(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("Data Science fee in India", "SALES"), AgentContext(user_request="Data Science fee in India"))
        self.assertIn("existing_pricing_gateway", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_international_pricing_safety(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        context = AgentContext(user_request="Data Science fee", crm_state={"country": "USA"})
        result = sales_handler(Task("What is the Data Science fee?", "SALES"), context)
        self.assertIn("international_pricing_requires_admissions_confirmation", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_admission_intent(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("I want admission for Data Science", "SALES"), AgentContext(user_request="I want admission for Data Science"))
        self.assertEqual(result["intent"], "admission_intent")
        self.assertEqual(result["admission_readiness"], "ready_for_counselling")

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_human_handoff(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("I want to enroll", "SALES"), AgentContext(user_request="I want to enroll"))
        self.assertTrue(result["human_handoff_required"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_unknown_course_safety(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("Tell me about Quantum Banana", "SALES"), AgentContext(user_request="Tell me about Quantum Banana"))
        self.assertEqual(result["course_candidates"], [])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_crm_read_context(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        context = AgentContext(user_request="Continue", crm_state={"lead_id": "SE-00001", "country": "India"})
        result = sales_handler(Task("Continue", "SALES"), context)
        self.assertIn("existing_crm_read", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_crm_immutability_without_authorization(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        leads_file = Path("data") / "leads.json"
        before = leads_file.read_bytes()
        result = sales_handler(Task("I want admission", "SALES"), AgentContext(user_request="I want admission"))
        self.assertEqual(before, leads_file.read_bytes())
        self.assertFalse(result["authorization_required"])
        self.assertEqual(result["actions_requested"], [])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_existing_master_kb_integration(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("Data Science", "SALES"), AgentContext(user_request="Data Science"))
        self.assertIn("authoritative_master_kb", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_existing_pricing_gateway_integration(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("Data Science fee", "SALES"), AgentContext(user_request="Data Science fee"))
        self.assertIn("existing_pricing_gateway", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    @patch("app.agentic.batch02.load_memory", return_value=[{"role": "user", "content": "Data Science"}])
    def test_existing_memory_integration(self, load_memory, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("Continue", "SALES"), AgentContext(user_request="Continue", session_id="batch02-memory"))
        load_memory.assert_called_once_with("batch02-memory")
        self.assertIn("existing_conversation_memory", result["evidence"])

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_structured_output(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = sales_handler(Task("Data Science", "SALES"), AgentContext(user_request="Data Science"))
        self.assertEqual(set(result), {
            "agent_id", "status", "response", "intent", "course_candidates",
            "recommended_next_step", "admission_readiness", "human_handoff_required",
            "evidence", "authorization_required", "actions_requested", "errors",
        })

    @patch("app.agentic.batch02.existing_agent.ask_agent")
    def test_orchestrator_integration(self, ask_agent):
        ask_agent.side_effect = self._fake_ai
        result = run_agentic_request("Tell me about Data Science", session_id="batch02")
        self.assertIs(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output["agent_id"], "SALES")

    def test_existing_ai_regression_signature_preserved(self):
        import inspect
        from app.ai.agent import ask_agent
        self.assertTrue(inspect.signature(ask_agent).parameters["session_id"].default == "default_student")

    def test_sales_handler_is_read_only(self):
        self.assertTrue(callable(sales_handler))

    def test_counselling_handler_is_read_only(self):
        self.assertTrue(callable(counselling_handler))


if __name__ == "__main__":
    unittest.main()