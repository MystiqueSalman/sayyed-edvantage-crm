import unittest

from app.agentic.batch02_integration import (
    build_batch02_orchestrator,
    route_agent_id,
    run_agentic_request,
    run_complete_creative_workflow,
)
from app.agentic.creative_provider import (
    CreativeGenerationRequest,
    UnconfiguredImageGenerationProvider,
    UnconfiguredVideoGenerationProvider,
)
from app.agentic.image_ad import image_ad_handler
from app.agentic.models import AgentContext, Task, TaskStatus
from app.agentic.video_ad import video_ad_handler


class AgenticBatch05Tests(unittest.TestCase):
    def test_agent_registration(self):
        ids = {agent.agent_id for agent in build_batch02_orchestrator().registry.list()}
        self.assertTrue({"IMAGE_AD", "VIDEO_AD"} <= ids)

    def test_routing(self):
        self.assertEqual(route_agent_id("Create a poster for Data Science"), "IMAGE_AD")
        self.assertEqual(route_agent_id("Create a 10-second Data Science video"), "VIDEO_AD")

    def test_image_prompt_and_variants(self):
        result = image_ad_handler(Task("Create a poster for Data Science", "IMAGE_AD"), AgentContext(user_request="poster"))
        self.assertEqual(result["creative_type"], "IMAGE_AD")
        self.assertTrue(result["visual_prompt"])
        self.assertEqual(len(result["variants"]), 3)
        self.assertFalse(result["asset_generated"])

    def test_image_format_handling(self):
        result = image_ad_handler(Task("Create a vertical Instagram advertisement for Data Science", "IMAGE_AD"), AgentContext(user_request="image"))
        self.assertEqual(result["aspect_ratio"], "9:16")
        self.assertEqual(result["dimensions"], "1080x1920")

    def test_video_script_and_scenes(self):
        result = video_ad_handler(Task("Create a 10-second vertical promotional video for Data Science", "VIDEO_AD"), AgentContext(user_request="video"))
        self.assertEqual(result["duration"], 10)
        self.assertEqual(result["format"], "VERTICAL")
        self.assertTrue(result["scenes"])
        self.assertTrue({"scene_number", "duration", "visual_description", "camera_direction", "on_screen_text", "voiceover", "audio_direction", "transition", "branding", "CTA"} <= set(result["scenes"][0]))

    def test_video_durations(self):
        for duration in (10, 15, 30):
            result = video_ad_handler(Task(f"Create a {duration}-second video for Python", "VIDEO_AD"), AgentContext(user_request="video"))
            self.assertEqual(result["duration"], duration)

    def test_video_format_handling(self):
        result = video_ad_handler(Task("Create a landscape video for Linux", "VIDEO_AD", input={"format": "LANDSCAPE"}), AgentContext(user_request="video"))
        self.assertEqual(result["format"], "LANDSCAPE")

    def test_provider_abstraction(self):
        image = UnconfiguredImageGenerationProvider().generate_image(CreativeGenerationRequest("IMAGE_AD", "prompt"))
        video = UnconfiguredVideoGenerationProvider().generate_video(CreativeGenerationRequest("VIDEO_AD", "prompt"))
        self.assertEqual(image.status, "GENERATION_REQUEST_READY")
        self.assertEqual(video.status, "GENERATION_REQUEST_READY")

    def test_missing_provider_no_fake_generation(self):
        result = video_ad_handler(Task("Create a video for Python", "VIDEO_AD"), AgentContext(user_request="video"))
        self.assertEqual(result["generation_status"], "GENERATION_REQUEST_READY")
        self.assertFalse(result["asset_generated"])

    def test_course_grounding_and_unsupported_course(self):
        result = image_ad_handler(Task("Create an image for Ethical Hacking", "IMAGE_AD"), AgentContext(user_request="image"))
        self.assertIn("Ethical Hacking", result["course"])
        blocked = image_ad_handler(Task("Create an image for Quantum Computing", "IMAGE_AD"), AgentContext(user_request="image"))
        self.assertEqual(blocked["status"], "blocked")

    def test_pricing_and_international_safety(self):
        result = image_ad_handler(Task("Create an international image ad for Data Science", "IMAGE_AD", input={"audience": "international students"}), AgentContext(user_request="image"))
        self.assertNotIn("₹", str(result))
        self.assertNotIn("50000", str(result))

    def test_no_publishing(self):
        result = image_ad_handler(Task("Create an image for Data Science", "IMAGE_AD"), AgentContext(user_request="image"))
        self.assertFalse(result["published"])
        self.assertFalse(result["external_action"])

    def test_authorization_boundary(self):
        result = run_agentic_request("Upload the Data Science image to Instagram", input={"agent_id": "IMAGE_AD"})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertTrue(result.authorization_required)

    def test_orchestrator_integration(self):
        result = run_agentic_request("Create a poster for Data Science")
        self.assertIs(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.output["agent_id"], "IMAGE_AD")

    def test_complete_creative_workflow(self):
        result = run_complete_creative_workflow("Create a complete promotional campaign with caption, image and video for Data Science")
        self.assertEqual(result["MARKETING"]["status"], "prepared")
        self.assertEqual(result["CONTENT"]["status"], "prepared")
        self.assertEqual(result["IMAGE_AD"]["status"], "prepared")
        self.assertEqual(result["VIDEO_AD"]["status"], "prepared")

    def test_previous_batch_regression_imports(self):
        from tests.test_agentic_batch01 import AgenticBatch01Tests
        from tests.test_agentic_batch02 import AgenticBatch02Tests
        from tests.test_agentic_batch03 import AgenticBatch03Tests
        from tests.test_agentic_batch04 import AgenticBatch04Tests
        self.assertTrue(all((AgenticBatch01Tests, AgenticBatch02Tests, AgenticBatch03Tests, AgenticBatch04Tests)))


if __name__ == "__main__":
    unittest.main()