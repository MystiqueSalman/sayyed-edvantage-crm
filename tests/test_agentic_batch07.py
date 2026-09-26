import unittest
from unittest.mock import patch

from app.agentic.analytics import analytics_handler
from app.agentic.batch02_integration import (
    build_batch02_orchestrator,
    route_agent_id,
    run_agentic_request,
    run_analytics_research_workflow,
)
from app.agentic.models import AgentContext, Task, TaskStatus
from app.agentic.research import ResearchRequest, UnconfiguredResearchProvider, research_handler
from app.agentic.safety_auth import AUTHORIZATION_MATRIX, classify_action, safety_auth_handler


class AgenticBatch07Tests(unittest.TestCase):
    def test_agent_registration(self):
        ids = {agent.agent_id for agent in build_batch02_orchestrator().registry.list()}
        self.assertTrue({"ANALYTICS", "RESEARCH", "SAFETY_AUTH"} <= ids)

    def test_lead_funnel_analytics(self):
        result = analytics_handler(Task("Analyze current admissions funnel", "ANALYTICS"), AgentContext(user_request="analytics"))
        names = {metric["name"] for metric in result["metrics"]}
        self.assertIn("total_leads", names)
        self.assertIn("leads_enrolled", names)
        self.assertEqual(result["data_sources"], ["existing CRM read"])

    def test_course_analytics(self):
        result = analytics_handler(Task("Analyze course interest", "ANALYTICS"), AgentContext(user_request="analytics"))
        self.assertTrue(all("course" in item for item in result["course_interest_distribution"]))

    def test_conversion_calculation(self):
        result = analytics_handler(Task("Analyze conversions", "ANALYTICS"), AgentContext(user_request="analytics"))
        conversion = next(metric for metric in result["metrics"] if metric["name"] == "enrollment_conversion_rate")
        self.assertIsInstance(conversion["value"], (int, float))
        self.assertEqual(conversion["evidence_type"], "CALCULATED_METRIC")

    def test_missing_data_handling(self):
        with patch("app.agentic.analytics.get_all_leads", return_value=[]):
            result = analytics_handler(Task("Analyze funnel", "ANALYTICS"), AgentContext(user_request="analytics"))
        conversion = next(metric for metric in result["metrics"] if metric["name"] == "enrollment_conversion_rate")
        self.assertIsNone(conversion["value"])
        self.assertEqual(conversion["evidence_type"], "UNKNOWN")

    def test_observed_vs_inference_separation(self):
        result = analytics_handler(Task("Analyze funnel", "ANALYTICS"), AgentContext(user_request="analytics"))
        self.assertTrue(all(item["evidence_type"] == "OBSERVED_DATA" for item in result["observations"]))
        self.assertTrue(all(item["evidence_type"] == "INFERENCE" for item in result["inferences"]))

    def test_trend_detection(self):
        result = analytics_handler(Task("Analyze trend", "ANALYTICS", input={"previous_metrics": {"total_leads": 0}}), AgentContext(user_request="analytics"))
        self.assertTrue(result["trends"])
        self.assertIn("Observed", result["trends"][0]["description"])

    def test_anomaly_detection_and_unknowns(self):
        result = analytics_handler(Task("Analyze campaign", "ANALYTICS"), AgentContext(user_request="analytics"))
        self.assertTrue(result["unknowns"])
        self.assertIsInstance(result["anomalies"], list)

    def test_research_request(self):
        result = research_handler(Task("Research current Data Science education trends", "RESEARCH"), AgentContext(user_request="research"))
        self.assertEqual(result["status"], "RESEARCH_REQUEST_READY")
        self.assertEqual(result["sources"], [])

    def test_research_source_structure(self):
        provider = UnconfiguredResearchProvider()
        self.assertEqual(provider.search(ResearchRequest("query", "scope"))["sources"], [])

    def test_missing_research_provider(self):
        result = research_handler(Task("Research trends", "RESEARCH"), AgentContext(user_request="research"))
        self.assertIn("provider", result["limitations"][0])
        self.assertFalse(result["execution_performed"])

    def test_no_fabricated_sources_and_competitor_safety(self):
        result = research_handler(Task("Research best competitor", "RESEARCH"), AgentContext(user_request="research"))
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["findings"], [])

    def test_authorization_matrix(self):
        self.assertTrue(AUTHORIZATION_MATRIX["PUBLISH"][1])
        self.assertTrue(AUTHORIZATION_MATRIX["AD_SPEND"][1])
        self.assertFalse(AUTHORIZATION_MATRIX["CRM_READ"][1])

    def test_action_classification(self):
        self.assertEqual(classify_action("analyze campaign")["action_level"], "THINK")
        self.assertEqual(classify_action("prepare social post")["operation"], "SOCIAL_WRITE")
        self.assertEqual(classify_action("prepare social post")["action_level"], "PREPARE")
        self.assertEqual(classify_action("publish campaign")["action_level"], "EXECUTE")

    def test_publish_message_ad_spend_crm_protection(self):
        for request in ("Publish campaign", "Send message", "Spend advertising budget", "Modify CRM lead"):
            result = safety_auth_handler(Task(request, "SAFETY_AUTH"), AgentContext(user_request=request))
            self.assertTrue(result["authorization_required"], request)
            self.assertFalse(result["execution_performed"], request)

    def test_external_request_protection(self):
        result = run_agentic_request("Publish the prepared Instagram campaign")
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertIsNone(result.output)

    def test_human_handoff(self):
        result = safety_auth_handler(Task("Launch campaign", "SAFETY_AUTH"), AgentContext(user_request="Launch campaign"))
        self.assertTrue(result["handoff_required"])
        self.assertTrue(result["recommended_human_role"])

    def test_audit_integration(self):
        orchestrator = build_batch02_orchestrator()
        result = run_agentic_request("Analyze my leads", orchestrator=orchestrator)
        self.assertIs(result.status, TaskStatus.COMPLETED)
        self.assertTrue(any(event.event_type == "AGENT_REQUEST_RECORDED" for event in orchestrator.audit_log.events()))

    def test_orchestrator_and_workflow(self):
        result = run_agentic_request("Research Data Science trends")
        self.assertIs(result.status, TaskStatus.COMPLETED)
        workflow = run_analytics_research_workflow("Analyze admissions and research trends")
        self.assertEqual(workflow["ANALYTICS"]["agent_id"], "ANALYTICS")
        self.assertEqual(workflow["RESEARCH"]["agent_id"], "RESEARCH")

    def test_no_crm_mutation(self):
        result = analytics_handler(Task("Analyze leads", "ANALYTICS"), AgentContext(user_request="analytics"))
        self.assertFalse(result["crm_mutation_performed"])

    def test_previous_batch_regression_imports(self):
        from tests.test_agentic_batch01 import AgenticBatch01Tests
        from tests.test_agentic_batch02 import AgenticBatch02Tests
        from tests.test_agentic_batch03 import AgenticBatch03Tests
        from tests.test_agentic_batch04 import AgenticBatch04Tests
        from tests.test_agentic_batch05 import AgenticBatch05Tests
        from tests.test_agentic_batch06 import AgenticBatch06Tests
        self.assertTrue(all((AgenticBatch01Tests, AgenticBatch02Tests, AgenticBatch03Tests, AgenticBatch04Tests, AgenticBatch05Tests, AgenticBatch06Tests)))


if __name__ == "__main__":
    unittest.main()