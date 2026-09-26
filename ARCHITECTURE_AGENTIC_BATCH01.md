# Agentic AI architecture — Batch 01

The existing counselling agent, CRM, Master KB, memory, and API remain intact.
Batch 01 adds a side-effect-safe foundation under `app/agentic/`.

## Components

- `models.py`: typed task, context, agent message, authorization, and agent specification models.
- `registry.py`: central registry for the orchestrator and specialized agent identities.
- `authorization.py`: one boundary for THINK/PREPARE/EXECUTE decisions.
- `audit.py`: append-only in-memory audit foundation for later durable storage.
- `computer_action.py`: computer-use interface and safe unconfigured implementation.
- `orchestrator.py`: handler registration, authorization checkpoints, execution, failure state, and audit events.

EXECUTE tasks always enter `WAITING_AUTHORIZATION` until `run_authorized` receives
an explicit approval identifier. The default computer-action implementation never
pretends to control a browser or operating system.

## Next batches

1. Connect SALES and COUNSELLING handlers to the existing `app.ai.agent`.
2. Add CRM/MEMORY/FOLLOW-UP handlers through explicit read/write boundaries.
3. Add marketing and creative planning agents.
4. Add social, ads, analytics, research, and durable authorization/audit storage.
