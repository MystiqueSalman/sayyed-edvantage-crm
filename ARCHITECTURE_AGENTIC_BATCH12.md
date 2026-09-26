# Agentic AI architecture - Batch 12

Batch 12 adds provider-neutral production monitoring, health, observability,
and operational control around the existing Batch 01-11 system. It is read-only
and does not replace orchestration, durable state, scheduling, authorization,
CRM, Master KB, or computer-action planning.

## Health and metrics

`system_health()` checks the orchestrator, workflow engine, scheduler, durable
state, authorization, computer-action planning, CRM read, Master KB read,
analytics, and research components. Research is DEGRADED when no external
provider is configured; no research result is fabricated.

`agent_health()` derives invocation, success, failure, retry, blocked, and
authorization-request counters from existing audit events. No credentials or
sensitive data are exposed.

Workflow and scheduler metrics read existing Batch 09/10 JSON stores. They do
not mutate workflows or execute scheduled work.

## Events and errors

`OperationalEvent` is deterministic and serializable with event ID, timestamp,
event type, component, status, correlation ID, and metadata. Error classification
maps known local error patterns to stable categories without claiming provider
failures when no provider exists.

## Alerts and readiness

`evaluate_alerts()` emits data-only alerts for repeated failures, stalled work,
authorization backlog, unhealthy components, and repeated agent failures.
`production_readiness_snapshot()` combines health, agent counters, workflow and
scheduler metrics, security flags, recent events, and active alerts.

## Safety

Monitoring never publishes, messages, spends, mutates CRM/KB, opens a browser,
controls a PC, calls social APIs, creates credentials, or invents external
metrics. All external action flags remain disabled. Existing authorization and
persistent workflow boundaries remain authoritative.

## Limitations

This batch provides local deterministic observability only. Distributed metrics,
telemetry export, dashboards, alert delivery, real provider health probes, and
external notification integrations remain future work.
