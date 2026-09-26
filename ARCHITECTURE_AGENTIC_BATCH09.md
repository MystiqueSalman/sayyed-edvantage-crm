# Agentic AI architecture - Batch 09

Batch 09 adds opt-in durable workflow state, checkpoints, resumable task graphs,
retry tracking, and persistent audit storage around the Batch 08 orchestration
layer. Existing agents and the default in-memory workflow behavior are preserved.

## Persistence model

`WorkflowStateStore` stores JSON snapshots in `data/agentic/workflows.json` and
append-only checkpoint records in `data/agentic/workflow_checkpoints.json`.
Snapshots include workflow/task IDs, statuses, dependencies, results, retry
counts, pending/completed/failed/blocked steps, authorization state, handoff
state, and workflow context. Writes use a temporary file replacement.

`PersistentAuditLog` stores append-only audit events in
`data/agentic/audit_events.json`. It implements the existing `record()` and
`events()` interface, so the orchestrator does not need a second audit model.

## Lifecycle and checkpoints

Meaningful transitions create checkpoints: workflow creation, task start,
completion, failure, blocking, authorization required, pause, and completion.
The latest snapshot is sufficient to inspect current state; checkpoint history
is read-only through `WorkflowStateStore.history()` and
`latest_checkpoint()`.

## Resume and idempotency

`resume_agentic_workflow()` loads the persisted graph. Completed tasks remain
completed and are skipped; paused/running tasks are made ready only when their
dependencies are satisfied. A task is therefore not rerun merely because the
process restarted. Failed tasks track `retry_count`; automatic retry is refused
for EXECUTE-level tasks.

## Authorization and safety

Authorization state is persisted as task metadata. A restart never converts a
waiting authorization task into an executable task. External actions continue
to pass through the existing orchestrator authorization boundary. No provider,
CRM mutation, browser action, message, publication, or ad spend is performed by
Batch 09 tests.

## Recovery states

Tasks support pending, ready, running, completed, failed, blocked, paused,
cancelled, waiting-authorization, and waiting-human state labels. Failed and
blocked tasks are retained in the aggregate result and audit history.

## Verification

Batch 09 tests cover persistence, checkpoint history, crash/resume behavior,
completed-task preservation, pending continuation, retry state, authorization
preservation, idempotency, persistent audit, and safety regressions.