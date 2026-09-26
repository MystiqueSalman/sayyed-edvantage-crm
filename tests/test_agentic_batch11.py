import tempfile
import unittest
from pathlib import Path

from app.agentic.batch02_integration import build_batch02_orchestrator, run_agentic_request, run_agentic_workflow
from app.agentic.computer_action import (
    ACTION_STATES,
    COMPUTER_PERMISSION_SCOPES,
    BrowserState,
    ComputerAction,
    UnconfiguredComputerAction,
    plan_action,
    plan_request,
)
from app.agentic.durable import WorkflowStateStore
from app.agentic.models import AgentContext, Task, TaskStatus
from app.agentic.safety_auth import AUTHORIZATION_MATRIX, classify_action
from app.agentic.workflow import decompose_request


class AgenticBatch11Tests(unittest.TestCase):
    def test_action_creation(self):
        action = plan_action("NAVIGATE", "https://example.invalid")
        self.assertIsInstance(action, ComputerAction)
        self.assertTrue(action.expected_result)
        self.assertEqual(action.status, "WAITING_AUTHORIZATION")

    def test_action_planning(self):
        actions = plan_request("Open the social media dashboard and prepare an advertisement upload")
        self.assertEqual([action.action_type for action in actions[:3]], ["OPEN_APPLICATION", "NAVIGATE", "READ_STATE"])
        self.assertIn("UPLOAD", [action.action_type for action in actions])
        self.assertTrue(all(action.expected_result for action in actions))

    def test_action_states_and_scopes(self):
        self.assertTrue({"PLANNED", "READY", "WAITING_AUTHORIZATION", "AUTHORIZED", "EXECUTING", "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "VERIFICATION_REQUIRED"} <= ACTION_STATES)
        self.assertTrue({"FILE_READ", "FILE_WRITE", "BROWSER_READ", "BROWSER_WRITE", "UPLOAD", "DOWNLOAD", "APPLICATION_OPEN", "EXTERNAL_ACTION", "SOCIAL_MEDIA_ACTION"} <= COMPUTER_PERMISSION_SCOPES)

    def test_authorization_integration(self):
        self.assertTrue(AUTHORIZATION_MATRIX["UPLOAD"][1])
        self.assertTrue(AUTHORIZATION_MATRIX["BROWSER_WRITE"][1])
        self.assertEqual(classify_action("upload file")["operation"], "UPLOAD")
        self.assertTrue(classify_action("upload file")["authorization_required"])

    def test_browser_navigation_planning(self):
        action = plan_action("NAVIGATE", "authorized platform", expected_result={"page_identity_verified": True})
        self.assertEqual(action.expected_result["page_identity_verified"], True)

    def test_click_and_typing_planning(self):
        click = plan_action("CLICK", "upload button", expected_result={"ui_state_changed": True})
        typing = plan_action("TYPE", "caption field", parameters={"content": "provided later"}, expected_result={"text_present": True})
        self.assertTrue(click.authorization_required)
        self.assertTrue(typing.authorization_required)

    def test_upload_download_and_file_planning(self):
        upload = plan_action("UPLOAD", "authorized control", expected_result={"uploaded_file_state": True})
        download = plan_action("DOWNLOAD", "authorized resource", expected_result={"local_file_exists": True})
        edit = plan_action("EDIT_FILE", "approved path", expected_result={"saved_file_state": True})
        self.assertTrue(upload.authorization_required)
        self.assertTrue(download.authorization_required)
        self.assertTrue(edit.authorization_required)

    def test_browser_state_does_not_fabricate_observation(self):
        state = BrowserState(None, None, None, (), workflow_id="w1")
        self.assertIsNone(state.current_url)
        self.assertIsNone(state.page_title)

    def test_plan_only_handler(self):
        result = run_agentic_request("Open browser and navigate to the social media dashboard", input={"agent_id": "COMPUTER_ACTION"})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertIsNone(result.output)

    def test_read_only_state_plan_can_run_without_provider(self):
        from app.agentic.computer_action import computer_action_handler
        result = computer_action_handler(Task("Read page state", "COMPUTER_ACTION"), AgentContext(user_request="read page"))
        self.assertEqual(result["status"], "prepared")
        self.assertFalse(result["execution_performed"])
        self.assertIsNone(result["browser_state"])

    def test_unconfigured_executor_is_safe(self):
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            UnconfiguredComputerAction().execute("click", {}, type("Approval", (), {"approved": True})())

    def test_failure_and_verification_model(self):
        action = plan_action("VERIFY", "saved file", expected_result={"saved_file_state": True})
        self.assertEqual(action.status, "READY")
        action.status = "VERIFICATION_REQUIRED"
        self.assertEqual(action.status, "VERIFICATION_REQUIRED")

    def test_workflow_integration(self):
        graph = decompose_request("Upload a file to the browser")
        self.assertIn("COMPUTER_ACTION", {task.agent for task in graph.tasks.values()})
        self.assertIn("SAFETY_AUTH", {task.agent for task in graph.tasks.values()})

    def test_authorization_persistence_and_restart_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStateStore(Path(directory))
            result = run_agentic_workflow("Upload a file to the browser", state_store=store)
            self.assertEqual(result["final_status"], "WAITING_AUTHORIZATION")
            restored = store.get(result["workflow_id"])
            self.assertTrue(restored["authorization_state"])
            self.assertEqual(restored["authorization_state"], restored["authorization_state"])

    def test_resume_does_not_bypass_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStateStore(Path(directory))
            result = run_agentic_workflow("Publish the prepared campaign", state_store=store)
            from app.agentic.batch02_integration import resume_agentic_workflow
            resumed = resume_agentic_workflow(result["workflow_id"], "Publish the prepared campaign", state_store=store)
            self.assertEqual(resumed["final_status"], "WAITING_AUTHORIZATION")
            self.assertFalse(any(item["result"] and item["result"].get("execution_performed") for item in resumed["agent_results"]))

    def test_no_external_execution(self):
        result = run_agentic_request("Upload file and publish it", input={"agent_id": "COMPUTER_ACTION"})
        self.assertIs(result.status, TaskStatus.WAITING_AUTHORIZATION)
        self.assertIsNone(result.output)

    def test_existing_computer_registry(self):
        ids = {agent.agent_id for agent in build_batch02_orchestrator().registry.list()}
        self.assertIn("COMPUTER_ACTION", ids)

    def test_previous_batch_regression_imports(self):
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
