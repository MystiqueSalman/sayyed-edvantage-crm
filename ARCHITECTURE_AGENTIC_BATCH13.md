# Agentic AI architecture - Batch 13

Batch 13 adds a provider-neutral operational control interface over the frozen
Batch 01-12 architecture. It does not replace the orchestrator, workflow engine,
durable store, scheduler, monitoring, Safety/Auth, CRM, Master KB, or Computer
Action planning layer.

## Control surface

`OperationalControl` exposes read-only system/agent/monitoring/authorization
status and controlled workflow operations: create, inspect, history, pause,
resume, cancel, retry, approve, and reject. It uses the existing scheduler and
`WorkflowStateStore`; no second workflow database is created.

## Authorization and human control

External-action objectives remain pending authorization. Approval is explicit,
persisted through the existing scheduler record, and auditable. Rejection moves
the workflow to `WAITING_HUMAN` with a persisted reason. Resume and retry do not
bypass pending or denied authorization. Approval changes state only; it does not
execute providers, browsers, messages, ads, CRM writes, or computer actions.

## Audit and provider neutrality

Every control request creates a deterministic `CONTROL_REQUEST` audit event with
workflow, agent, authorization, execution, correlation, and metadata fields.
The interface returns existing monitoring snapshots and scheduler events without
fabricating external responses or creating credentials.

## Limitations

This is an internal Python control interface, not a network server. Authentication,
network transport, RBAC, distributed locks, rate limiting, real provider
execution, and external notification delivery remain future integration work.
