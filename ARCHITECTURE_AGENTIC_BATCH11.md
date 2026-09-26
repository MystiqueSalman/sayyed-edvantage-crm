# Agentic AI architecture - Batch 11

Batch 11 adds a provider-neutral Computer Action Agent foundation. It creates
structured plans for browser, application, file, upload, download, and state
verification actions while preserving the existing unconfigured executor and
authorization boundary.

## Action model

`ComputerAction` records contain an action ID, workflow reference, type, target,
parameters, expected result, authorization state, lifecycle status, timestamp,
and audit reference. Planned states include `PLANNED`, `READY`,
`WAITING_AUTHORIZATION`, `AUTHORIZED`, `EXECUTING`, `SUCCEEDED`, `FAILED`,
`BLOCKED`, `CANCELLED`, and `VERIFICATION_REQUIRED`.

Read-only state planning can be prepared without external authorization. Click,
type, select, scroll, upload, download, file writes, application opening, and
external/social actions require explicit authorization. The handler only returns
plans; it never invokes a browser, PC, file provider, upload provider, or
screenshot provider.

## Providers and browser state

`FileOperationProvider` is a future interface for bounded file operations.
`BrowserState` is a data model for verified observations. No browser state,
screenshot, upload confirmation, download confirmation, or external result is
fabricated when a provider is absent.

## Workflow and persistence

Computer requests are routed through the existing orchestrator and Batch 08
workflow graph. Execute-level computer requests enter the existing authorization
boundary and remain waiting across durable workflow restart/resume. Batch 09/10
JSON persistence and scheduler retry rules remain authoritative; no second state
or audit database is introduced.

## Limitations and future integration

The project does not have physical PC access, browser automation, credentials,
platform APIs, or a real file-operation provider. A later integration may supply
an explicitly authorized executor and verification adapter. That executor must
preserve action scopes, expected-result verification, audit events, and the
existing Safety/Auth gate.
