from __future__ import annotations

import re

from app.agentic.counselling import counselling_handler
from app.agentic.content import content_handler
from app.agentic.crm import crm_handler
from app.agentic.follow_up import follow_up_handler
from app.agentic.image_ad import image_ad_handler
from app.agentic.marketing import marketing_handler
from app.agentic.memory import memory_handler
from app.agentic.models import ActionLevel, AgentContext, Task
from app.agentic.orchestrator import Orchestrator
from app.agentic.sales import sales_handler
from app.agentic.social_media import social_media_handler
from app.agentic.ads import ads_handler
from app.agentic.analytics import analytics_handler
from app.agentic.lead_generation import lead_generation_handler
from app.agentic.research import research_handler
from app.agentic.safety_auth import safety_auth_handler
from app.agentic.video_ad import video_ad_handler
from app.agentic.workflow import decompose_request, execute_workflow
from app.agentic.workflow import resume_workflow
from app.agentic.durable import PersistentAuditLog, WorkflowStateStore
from app.agentic.scheduler import DurableWorkflowScheduler
from app.agentic.computer_action import computer_action_handler


def route_agent_id(user_request: str) -> str:
    """Choose an agent deterministically from the request's primary intent."""
    value = str(user_request or "").lower()
    if any(marker in value for marker in ("previously", "conversation history", "what did this student ask", "memory")):
        return "MEMORY"
    if any(marker in value for marker in ("open browser", "browser navigation", "navigate browser", "click", "type into", "upload file", "download file", "computer action", "screenshot")):
        return "COMPUTER_ACTION"
    if any(marker in value for marker in ("is this action safe", "safety", "authorization", "permission")):
        return "SAFETY_AUTH"
    if any(marker in value for marker in ("research", "market research", "competitor research", "technology trends", "education trends")):
        return "RESEARCH"
    if any(marker in value for marker in ("analyze", "analyse", "analytics", "funnel", "metrics", "kpi", "why are", "performance changed")):
        return "ANALYTICS"
    if any(marker in value for marker in ("follow-up", "follow up", "followup", "overdue", "which leads need")):
        return "FOLLOW_UP"
    if any(marker in value for marker in ("post this", "post plan", "upload", "publish", "schedule post", "social media", "social-media", "instagram content", "facebook content", "youtube content", "linkedin content", "whatsapp content", "content calendar", "hashtag strategy")):
        return "SOCIAL_MEDIA"
    if any(marker in value for marker in ("advertising", "paid campaign", "facebook lead campaign", "budget", "retargeting", "run facebook")):
        return "ADS"
    if any(marker in value for marker in ("lead generation", "lead campaign", "lead form", "capture leads", "lead flow")):
        return "LEAD_GENERATION"
    if any(marker in value for marker in ("video ad", "video advertisement", "video", "reel", "shorts")) and not any(marker in value for marker in ("image", "poster")):
        return "VIDEO_AD"
    if any(marker in value for marker in ("image ad", "image advertisement", "poster", "image creative")):
        return "IMAGE_AD"
    if any(marker in value for marker in ("campaign", "marketing", "promote all", "promotional plan", "content plan")):
        return "MARKETING"
    if any(marker in value for marker in ("caption", "hashtag", "headline", "hook", "instagram content", "social-media content", "reel script", "youtube description", "whatsapp draft", "email draft")):
        return "CONTENT"
    if re.search(r"\b(status|lead|pipeline|counselling history|follow-up history|admission status|crm|SE-\d{5})\b", value, re.IGNORECASE):
        return "CRM"
    counselling_markers = (
        r"which course", r"suitable", r"recommend", r"eligible", r"eligibility",
        r"compare", r"don't know", r"do not know", r"qualification",
    )
    if any(re.search(marker, value) for marker in counselling_markers):
        return "COUNSELLING"
    return "SALES"


def register_batch02_handlers(orchestrator: Orchestrator) -> Orchestrator:
    orchestrator.register_handler("SALES", sales_handler)
    orchestrator.register_handler("COUNSELLING", counselling_handler)
    orchestrator.register_handler("CRM", crm_handler)
    orchestrator.register_handler("MEMORY", memory_handler)
    orchestrator.register_handler("FOLLOW_UP", follow_up_handler)
    orchestrator.register_handler("MARKETING", marketing_handler)
    orchestrator.register_handler("CONTENT", content_handler)
    orchestrator.register_handler("IMAGE_AD", image_ad_handler)
    orchestrator.register_handler("VIDEO_AD", video_ad_handler)
    orchestrator.register_handler("SOCIAL_MEDIA", social_media_handler)
    orchestrator.register_handler("ADS", ads_handler)
    orchestrator.register_handler("LEAD_GENERATION", lead_generation_handler)
    orchestrator.register_handler("ANALYTICS", analytics_handler)
    orchestrator.register_handler("RESEARCH", research_handler)
    orchestrator.register_handler("SAFETY_AUTH", safety_auth_handler)
    orchestrator.register_handler("COMPUTER_ACTION", computer_action_handler)
    return orchestrator


def build_batch02_orchestrator() -> Orchestrator:
    return register_batch02_handlers(Orchestrator())


def run_agentic_request(user_request: str, *, session_id: str | None = None, input: dict | None = None, orchestrator: Orchestrator | None = None):
    orchestrator = orchestrator or build_batch02_orchestrator()
    task_input = dict(input or {})
    agent_id = str(task_input.pop("agent_id", "") or route_agent_id(user_request)).upper()
    action = str(task_input.get("action", "")).lower()
    protected_actions = {
        "update_lead", "change_pipeline_stage", "change_admission_status", "add_follow_up",
        "add_counselling", "delete_lead", "send", "schedule", "save_message",
    }
    external_request = re.search(r"\b(login|upload|publish|post|delete|edit|send|follow|unfollow|comment|like|react|capture|submit|connect|import|launch|spend|purchase|change budget|start|click|type|select|scroll|navigate|open browser|open application|download)\b", user_request, re.IGNORECASE)
    if action in protected_actions or external_request:
        action_level = ActionLevel.EXECUTE
    elif agent_id in {"MARKETING", "CONTENT", "IMAGE_AD", "VIDEO_AD", "SOCIAL_MEDIA", "ADS", "LEAD_GENERATION", "RESEARCH"}:
        action_level = ActionLevel.PREPARE
    else:
        action_level = ActionLevel.THINK
    task = Task(user_request=user_request, agent_id=agent_id, input=task_input, action_level=action_level)
    context = AgentContext(user_request=user_request, session_id=session_id)
    if external_request:
        orchestrator.audit_log.record(
            "EXTERNAL_ACTION_REQUESTED",
            agent_id,
            action=task_input.get("action", "external_action"),
            platform=task_input.get("platform", ""),
            campaign=task_input.get("campaign", ""),
            authorization_state=task.authorization_status.value,
            execution_state="NOT_EXECUTED",
        )
    elif agent_id in {"ANALYTICS", "RESEARCH", "SAFETY_AUTH"}:
        orchestrator.audit_log.record(
            "AGENT_REQUEST_RECORDED",
            agent_id,
            request_type=agent_id.lower(),
            authorization_state=task.authorization_status.value,
            execution_state="NOT_EXECUTED",
        )
    return orchestrator.run(task, context)


def run_marketing_content_workflow(user_request: str, *, session_id: str | None = None, input: dict | None = None, orchestrator: Orchestrator | None = None) -> dict:
    """Prepare a marketing brief and hand its approved course context to Content."""
    orchestrator = orchestrator or build_batch02_orchestrator()
    task_input = dict(input or {})
    marketing_task = Task(user_request=user_request, agent_id="MARKETING", input=task_input, action_level=ActionLevel.PREPARE)
    context = AgentContext(user_request=user_request, session_id=session_id)
    marketing_result = orchestrator.run(marketing_task, context)
    content_task = Task(user_request=user_request, agent_id="CONTENT", input=task_input, action_level=ActionLevel.PREPARE, parent_task_id=marketing_task.task_id)
    content_context = AgentContext(user_request=user_request, session_id=session_id, agent_outputs={"MARKETING": marketing_result.output or {}})
    content_result = orchestrator.run(content_task, content_context)
    return {"MARKETING": marketing_result.output, "CONTENT": content_result.output}


def run_complete_creative_workflow(user_request: str, *, session_id: str | None = None, input: dict | None = None, orchestrator: Orchestrator | None = None) -> dict:
    """Prepare Marketing, Content, Image, and Video outputs without external actions."""
    orchestrator = orchestrator or build_batch02_orchestrator()
    task_input = dict(input or {})
    context = AgentContext(user_request=user_request, session_id=session_id)
    outputs = {}
    for agent_id, handler in (("MARKETING", marketing_handler), ("CONTENT", content_handler), ("IMAGE_AD", image_ad_handler), ("VIDEO_AD", video_ad_handler)):
        task = Task(user_request=user_request, agent_id=agent_id, input=task_input, action_level=ActionLevel.PREPARE)
        result = orchestrator.run(task, context)
        outputs[agent_id] = result.output
    return outputs


def run_complete_campaign_workflow(user_request: str, *, session_id: str | None = None, input: dict | None = None, orchestrator: Orchestrator | None = None) -> dict:
    """Prepare the full marketing, creative, social, ads, and lead package."""
    orchestrator = orchestrator or build_batch02_orchestrator()
    task_input = dict(input or {})
    context = AgentContext(user_request=user_request, session_id=session_id)
    outputs = {}
    handlers = (("MARKETING", marketing_handler), ("CONTENT", content_handler), ("IMAGE_AD", image_ad_handler), ("VIDEO_AD", video_ad_handler), ("SOCIAL_MEDIA", social_media_handler), ("ADS", ads_handler), ("LEAD_GENERATION", lead_generation_handler))
    for agent_id, handler in handlers:
        task = Task(user_request=user_request, agent_id=agent_id, input=task_input, action_level=ActionLevel.PREPARE)
        result = orchestrator.run(task, context)
        outputs[agent_id] = result.output
    return outputs


def build_durable_orchestrator(storage_root: str = "data/agentic") -> Orchestrator:
    """Build an orchestrator with append-only audit persistence for Batch 09."""
    return register_batch02_handlers(Orchestrator(audit_log=PersistentAuditLog(f"{storage_root}/audit_events.json")))


def build_workflow_scheduler(storage_root: str = "data/agentic") -> DurableWorkflowScheduler:
    """Create the opt-in durable multi-workflow scheduler."""
    return DurableWorkflowScheduler(storage_root, audit_log=PersistentAuditLog(f"{storage_root}/audit_events.json"))


def schedule_agentic_workflow(objective: str, *, storage_root: str = "data/agentic", workflow_type: str = "agentic_workflow", run_at=None, recurring_seconds: int | None = None, priority: int = 50, owner: str = "system", idempotency_key: str | None = None) -> dict:
    scheduler = build_workflow_scheduler(storage_root)
    return scheduler.schedule(objective, workflow_type=workflow_type, run_at=run_at, recurring_seconds=recurring_seconds, priority=priority, owner=owner, idempotency_key=idempotency_key)


def run_agentic_workflow(user_request: str, *, session_id: str | None = None, orchestrator: Orchestrator | None = None, state_store: WorkflowStateStore | None = None, max_tasks: int | None = None) -> dict:
    """Decompose and coordinate existing agents into a validated workflow result."""
    orchestrator = orchestrator or build_batch02_orchestrator()
    graph = decompose_request(user_request)
    handlers = {
        "SALES": sales_handler, "COUNSELLING": counselling_handler, "CRM": crm_handler,
        "MEMORY": memory_handler, "FOLLOW_UP": follow_up_handler, "MARKETING": marketing_handler,
        "CONTENT": content_handler, "IMAGE_AD": image_ad_handler, "VIDEO_AD": video_ad_handler,
        "SOCIAL_MEDIA": social_media_handler, "ADS": ads_handler, "LEAD_GENERATION": lead_generation_handler,
        "ANALYTICS": analytics_handler, "RESEARCH": research_handler, "SAFETY_AUTH": safety_auth_handler,
        "COMPUTER_ACTION": computer_action_handler,
    }
    return execute_workflow(graph, user_request, handlers, orchestrator, session_id=session_id, state_store=state_store, max_tasks=max_tasks)


def resume_agentic_workflow(workflow_id: str, objective: str, *, state_store: WorkflowStateStore, session_id: str | None = None, orchestrator: Orchestrator | None = None, max_tasks: int | None = None) -> dict:
    orchestrator = orchestrator or build_batch02_orchestrator()
    handlers = {
        "SALES": sales_handler, "COUNSELLING": counselling_handler, "CRM": crm_handler,
        "MEMORY": memory_handler, "FOLLOW_UP": follow_up_handler, "MARKETING": marketing_handler,
        "CONTENT": content_handler, "IMAGE_AD": image_ad_handler, "VIDEO_AD": video_ad_handler,
        "SOCIAL_MEDIA": social_media_handler, "ADS": ads_handler, "LEAD_GENERATION": lead_generation_handler,
        "ANALYTICS": analytics_handler, "RESEARCH": research_handler, "SAFETY_AUTH": safety_auth_handler,
        "COMPUTER_ACTION": computer_action_handler,
    }
    return resume_workflow(workflow_id, objective, handlers, orchestrator, state_store, session_id=session_id, max_tasks=max_tasks)


def run_analytics_research_workflow(user_request: str, *, session_id: str | None = None, input: dict | None = None, orchestrator: Orchestrator | None = None) -> dict:
    """Prepare an internal analytics result and an optional external research request."""
    orchestrator = orchestrator or build_batch02_orchestrator()
    task_input = dict(input or {})
    context = AgentContext(user_request=user_request, session_id=session_id)
    analytics_task = Task(user_request=user_request, agent_id="ANALYTICS", input=task_input, action_level=ActionLevel.THINK)
    analytics_result = orchestrator.run(analytics_task, context)
    research_task = Task(user_request=user_request, agent_id="RESEARCH", input=task_input, action_level=ActionLevel.PREPARE)
    research_context = AgentContext(user_request=user_request, session_id=session_id, agent_outputs={"ANALYTICS": analytics_result.output or {}})
    research_result = orchestrator.run(research_task, research_context)
    return {"ANALYTICS": analytics_result.output, "RESEARCH": research_result.output}


def run_cross_agent_follow_up(lead_id: str, *, session_id: str | None = None, orchestrator: Orchestrator | None = None) -> dict:
    """Read CRM, reconcile memory, then prepare a follow-up without sending it."""
    orchestrator = orchestrator or build_batch02_orchestrator()
    crm_task = Task(user_request=f"Retrieve CRM context for {lead_id}", agent_id="CRM", input={"lead_id": lead_id, "operation": "crm_context"})
    crm_result = orchestrator.run(crm_task, AgentContext(user_request=crm_task.user_request, lead_id=lead_id, session_id=session_id))
    crm_state = crm_result.output.get("data", {}) if crm_result.output else {}
    memory_task = Task(user_request="Retrieve previous conversation", agent_id="MEMORY", input={"action": "retrieve"})
    memory_result = orchestrator.run(memory_task, AgentContext(user_request=memory_task.user_request, lead_id=lead_id, session_id=session_id, crm_state=crm_state))
    follow_task = Task(user_request=f"Prepare a follow-up for {lead_id}", agent_id="FOLLOW_UP", input={"action": "prepare", "lead_id": lead_id})
    follow_result = orchestrator.run(follow_task, AgentContext(user_request=follow_task.user_request, lead_id=lead_id, session_id=session_id, crm_state=crm_state, agent_outputs={"CRM": crm_result.output or {}, "MEMORY": memory_result.output or {}}))
    return {"CRM": crm_result.output, "MEMORY": memory_result.output, "FOLLOW_UP": follow_result.output}