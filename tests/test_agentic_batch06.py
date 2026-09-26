import unittest

from app.agentic.ads import ads_handler
from app.agentic.batch02_integration import (
    build_batch02_orchestrator,
    route_agent_id,
    run_agentic_request,
    run_complete_campaign_workflow,
)
from app.agentic.lead_generation import lead_generation_handler
from app.agentic.models import AgentContext, Task, TaskStatus
from app.agentic.platform_provider import (
    PlatformActionRequest,
    UnconfiguredPlatformProvider,
)
from app.agentic.social_media import social_media_handler


class AgenticBatch06Tests(unittest.TestCase):
    def test_agent_registration(self):
        ids = {agent.agent_id for agent in build_batch02_orchestrator().registry.list()}
        self.assertTrue({"SOCIAL_MEDIA", "ADS", "LEAD_GENERATION"} <= ids)

    def test_platform_routing(self):
        self.assertEqual(route_agent_id("Create Instagram campaign"), "MARKETING")
        self.assertEqual(route_agent_id("Create Facebook lead campaign"), "ADS")
        self.assertEqual(route_agent_id("Post this video to Instagram"), "SOCIAL_MEDIA")
        self.assertEqual(route_agent_id("Create a YouTube content calendar"), "SOCIAL_MEDIA")
        self.assertEqual(route_agent_id("Create a LinkedIn post plan"), "SOCIAL_MEDIA")

    def test_social_content_and_hashtags(self):
        result = social_media_handler(Task("Create Instagram content for Data Science", "SOCIAL_MEDIA"), AgentContext(user_request="social"))
        self.assertEqual(result["status"], "prepared")
        self.assertIn("#DataScience", result["hashtags"])
        self.assertEqual(result["publication_status"], "PREPARED")

    def test_content_calendar(self):
        result = social_media_handler(Task("Create a weekly Instagram content calendar for Python", "SOCIAL_MEDIA", input={"schedule": "weekly"}), AgentContext(user_request="calendar"))
        self.assertEqual(result["schedule"], "weekly")

    def test_advertisement_planning(self):
        result = ads_handler(Task("Create a Facebook lead campaign for Data Science", "ADS"), AgentContext(user_request="ads"))
        self.assertEqual(result["status"], "prepared")
        self.assertFalse(result["campaign_launched"])
        self.assertFalse(result["spend_performed"])
        self.assertTrue(result["authorization_required"])

    def test_lead_generation_planning(self):
        result = lead_generation_handler(Task("Create a lead generation flow for Data Science from Instagram", "LEAD_GENERATION"), AgentContext(user_request="leads"))
        self.assertEqual(result["lead_source"], "Instagram")
        self.assertEqual(result["lead_record_template"]["status"], "NEW")
        self.assertFalse(result["crm_mutation_performed"])

    def test_complete_campaign_workflow(self):
        result = run_complete_campaign_workflow("Create a complete Instagram admission campaign for Sayyed EdVantage Data Science")
        self.assertEqual(set(result), {"MARKETING", "CONTENT", "IMAGE_AD", "VIDEO_AD", "SOCIAL_MEDIA", "ADS", "LEAD_GENERATION"})
        self.assertTrue(all(value["status"] == "prepared" for value in result.values()))

    def test_creative_integration(self):
        result = run_complete_campaign_workflow("Create a complete campaign for Data Science")
        self.assertEqual(result["IMAGE_AD"]["creative_type"], "IMAGE_AD")
        self.assertEqual(result["VIDEO_AD"]["creative_type"], "VIDEO_AD")

    def test_provider_abstraction_and_missing_provider(self):
        provider = UnconfiguredPlatformProvider("social_media")
        response = provider.execute(PlatformActionRequest("PUBLISH_POST", "Instagram"))
        self.assertEqual(response.status, "PROVIDER_NOT_CONFIGURED")
        self.assertFalse(response.execution_performed)

    def test_no_publishing_without_authorization(self):
        result = run_agentic_request("Post this video to Instagram", input={"agent_id": "SOCIAL_MEDIA"})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertTrue(result.authorization_required)
        self.assertIsNone(result.output)

    def test_no_external_messaging(self):
        result = social_media_handler(Task("Send this message to Instagram", "SOCIAL_MEDIA"), AgentContext(user_request="message"))
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["publication_status"], "NOT_EXECUTED")

    def test_no_ad_spending_or_launch(self):
        result = run_agentic_request("Launch and spend budget on Facebook campaign for Data Science", input={"agent_id": "ADS"})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertIsNone(result.output)

    def test_no_unauthorized_crm_mutation(self):
        result = lead_generation_handler(Task("Capture leads for Data Science", "LEAD_GENERATION"), AgentContext(user_request="lead"))
        self.assertFalse(result["crm_mutation_performed"])
        self.assertFalse(result["execution_performed"])

    def test_pricing_safety(self):
        result = ads_handler(Task("Create an Indian ad campaign for Data Science", "ADS"), AgentContext(user_request="ads"))
        self.assertNotIn("₹", str(result))
        self.assertNotIn("50000", str(result))

    def test_international_pricing_safety(self):
        result = social_media_handler(Task("Create an international campaign for Data Science", "SOCIAL_MEDIA", input={"audience": "international students"}), AgentContext(user_request="social"))
        self.assertNotIn("₹", str(result))
        self.assertNotIn("50000", str(result))

    def test_unsupported_fact_safety(self):
        result = ads_handler(Task("Create a campaign for Quantum Computing", "ADS"), AgentContext(user_request="ads"))
        self.assertEqual(result["status"], "blocked")

    def test_audit_creation(self):
        orchestrator = build_batch02_orchestrator()
        result = run_agentic_request("Publish a Data Science post to Instagram", input={"agent_id": "SOCIAL_MEDIA"}, orchestrator=orchestrator)
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        events = orchestrator.audit_log.events()
        self.assertTrue(any(event.event_type == "EXTERNAL_ACTION_REQUESTED" for event in events))

    def test_orchestrator_integration(self):
        result = run_agentic_request("Create Instagram content for Data Science")
        self.assertIs(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output["agent_id"], "SOCIAL_MEDIA")

    def test_previous_batch_regression_imports(self):
        from tests.test_agentic_batch01 import AgenticBatch01Tests
        from tests.test_agentic_batch02 import AgenticBatch02Tests
        from tests.test_agentic_batch03 import AgenticBatch03Tests
        from tests.test_agentic_batch04 import AgenticBatch04Tests
        from tests.test_agentic_batch05 import AgenticBatch05Tests
        self.assertTrue(all((AgenticBatch01Tests, AgenticBatch02Tests, AgenticBatch03Tests, AgenticBatch04Tests, AgenticBatch05Tests)))


if __name__ == "__main__":
    unittest.main()