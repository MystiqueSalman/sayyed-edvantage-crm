import unittest

from app.agentic.batch02_integration import (
    build_batch02_orchestrator,
    route_agent_id,
    run_agentic_request,
    run_marketing_content_workflow,
)
from app.agentic.models import ActionLevel, AgentContext, Task, TaskStatus
from app.agentic.marketing import approved_catalog, find_courses, marketing_handler
from app.agentic.content import content_handler


class AgenticBatch04Tests(unittest.TestCase):
    def test_marketing_agent_registration(self):
        self.assertIn("MARKETING", {agent.agent_id for agent in build_batch02_orchestrator().registry.list()})

    def test_content_agent_registration(self):
        self.assertIn("CONTENT", {agent.agent_id for agent in build_batch02_orchestrator().registry.list()})

    def test_marketing_routing(self):
        self.assertEqual(route_agent_id("Create an ad campaign for Data Science"), "MARKETING")

    def test_content_routing(self):
        self.assertEqual(route_agent_id("Give me 5 captions for AI"), "CONTENT")

    def test_course_campaigns(self):
        for phrase in ("Data Science", "Data Analytics", "AI + Generative AI", "Python", "Linux", "DevOps", "Ethical Hacking"):
            self.assertTrue(find_courses(f"Create a campaign for {phrase}"), phrase)

    def test_multi_course_campaign(self):
        courses = find_courses("Create a campaign promoting all Sayyed EdVantage courses")
        names = " ".join(item["course"] for item in courses)
        for expected in ("Data Science", "Data Analytics", "Python", "Linux", "DevOps"):
            self.assertIn(expected, names)

    def test_caption_hashtag_cta_and_variants(self):
        result = content_handler(Task("Give me 5 captions for Data Science", "CONTENT", input={"variant_count": 3}), AgentContext(user_request="captions"))
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(len(result["variants"]), 3)
        self.assertTrue(all(item["hook"] and item["hashtags"] and item["cta"] for item in result["variants"]))

    def test_platform_specific_content(self):
        result = content_handler(Task("Create Instagram content for Python", "CONTENT"), AgentContext(user_request="content"))
        self.assertEqual(result["platform"], "Instagram")

    def test_indian_audience_content(self):
        result = content_handler(Task("Create Indian audience content for Data Science", "CONTENT", input={"audience": "Indian students"}), AgentContext(user_request="content"))
        self.assertEqual(result["audience"], "Indian students")
        self.assertNotIn("₹", str(result))

    def test_international_pricing_safety(self):
        result = marketing_handler(Task("Create an international campaign for Data Science", "MARKETING", input={"audience": "international students"}), AgentContext(user_request="campaign"))
        self.assertNotIn("₹", str(result))
        self.assertIn("admissions confirmation", str(result))

    def test_unsupported_fact_safety(self):
        result = content_handler(Task("Create content for Quantum Computing", "CONTENT"), AgentContext(user_request="content"))
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["execution_performed"])

    def test_no_duplicate_pricing_source(self):
        source = open("app/agentic/marketing.py", encoding="utf-8").read() + open("app/agentic/content.py", encoding="utf-8").read()
        self.assertNotIn("50000", source)
        self.assertNotIn("40000", source)

    def test_no_publishing_or_external_action(self):
        result = content_handler(Task("Create Instagram content for Data Science", "CONTENT"), AgentContext(user_request="content"))
        self.assertFalse(result["published"])
        self.assertFalse(result["external_action"])

    def test_publish_request_waits_for_authorization(self):
        result = run_agentic_request("Create an Instagram campaign and publish it", input={"agent_id": "CONTENT"})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertTrue(result.authorization_required)
        self.assertFalse(result.output is not None)

    def test_orchestrator_integration(self):
        result = run_agentic_request("Create a campaign for Data Science")
        self.assertIs(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output["agent_id"], "MARKETING")

    def test_marketing_content_workflow(self):
        result = run_marketing_content_workflow("Create Instagram content for Data Science")
        self.assertEqual(result["MARKETING"]["status"], "prepared")
        self.assertEqual(result["CONTENT"]["status"], "prepared")

    def test_master_kb_grounding(self):
        catalog = approved_catalog()
        self.assertGreaterEqual(len(catalog), 7)
        self.assertTrue(all(item["source_ids"] for item in catalog))

    def test_previous_batch_regressions(self):
        from tests.test_agentic_batch01 import AgenticBatch01Tests
        from tests.test_agentic_batch02 import AgenticBatch02Tests
        from tests.test_agentic_batch03 import AgenticBatch03Tests
        self.assertTrue(AgenticBatch01Tests)
        self.assertTrue(AgenticBatch02Tests)
        self.assertTrue(AgenticBatch03Tests)


if __name__ == "__main__":
    unittest.main()