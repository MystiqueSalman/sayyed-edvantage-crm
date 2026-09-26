# Agentic AI architecture - Batch 10

Batch 10 adds durable scheduling and operational monitoring around the Batch 09
workflow and persistence layers. It is opt-in and provider-neutral; previous
workflow APIs and agents remain unchanged.

## Scheduler and registry

`DurableWorkflowScheduler` stores workflow scheduling metadata in
`scheduler_workflows.json` and operational events in `operational_events.json`
under the configured `data/agentic` root. Workflow IDs are deterministic when
an idempotency key or explicit workflow ID is supplied. Repeating the same
schedule operation returns the existing record.

The registry records type, objective, owner, priority, current status, next run,
retry metadata, authorization state, last error, handoff state, and audit
references. `list()` supports status, type, owner, priority, and authorization
filters.

## Lifecycle

Supported statuses are `CREATED`, `QUEUED`, `RUNNING`, `WAITING`, `SCHEDULED`,
`PAUSED`, `WAITING_AUTHORIZATION`, `WAITING_HUMAN`, `RETRY_PENDING`, `FAILED`,
`COMPLETED`, and `CANCELLED`.

`start_due()` only considers queued, scheduled, or retry-pending records whose
`next_run_at` is due. Pause, resume, cancel, complete, and retry transitions are
idempotent. Recurring workflows calculate the next run after completion.

## Retry and stalled detection

Retryable failures use bounded exponential-compatible delays and stop at
`max_retries`; non-retryable failures move directly to `FAILED`. Stalled
`RUNNING` and `WAITING` workflows are reported with elapsed time and a
recommended inspection/pause action. Detection never performs recovery itself.

## Authorization and safety

Objectives containing external-action signals are recorded as pending
authorization. Starting such a workflow produces `WAITING_AUTHORIZATION`; a
restart, retry, or recurring schedule cannot turn it into execution. No
publishing, messaging, ad spending, CRM mutation, browser action, credentials,
or external provider is configured by Batch 10.

## Monitoring and limitations

`monitor()` and `operational_snapshot()` provide read-only counts, stalled
records, and per-workflow state. Storage is JSON with atomic replacement and
process-local locking. A real distributed scheduler, process-wide lock, queue,
cron service, and external provider integrations remain future work.

## Tests

Batch 10 tests cover one-time and recurring schedules, persistence/restart,
pause/resume/cancel, retry exhaustion, stalled detection, authorization and
human-handoff persistence, workflow isolation, idempotency, operational events,
monitoring, orchestration integration, and no-external-action safety.