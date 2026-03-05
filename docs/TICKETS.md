# StageCanvas Ticket Queue

## SC-001 Deterministic Dev Bootstrap

Ticket: SC-001
Scope: make local sanity checks reproducible across parallel agents.
Owner: lead-agent (this chat)
Files allowed:
- `Makefile`
- `scripts/dev-sanity.sh`
- `control-ui/package.json`
- `control-ui/package-lock.json`
- `docs/MULTI_AGENT_WORKFLOW.md`
- `docs/AGENT_SYNC_PACKET.md`
- `README.md`
Out of scope:
- feature behavior changes in UI/server/render runtime
Acceptance:
- [x] one shared command: `make sanity`
- [x] sanity script uses collision-safe ports by default
- [x] dependency conflict (`@types/react` mismatch) resolved
- [x] sanity gate passes end-to-end
Checks:
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-004 Persistent Idempotency Ledger

Ticket: SC-004
Scope: move command idempotency and sequence generation from memory to persistent storage.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/app/command_ledger.py`
- docs tied to these files
Out of scope:
- UI behavior changes beyond existing SC-003 confidence panel
Acceptance:
- [x] idempotency survives process restarts
- [x] duplicate retry with same `request_id` does not redispatch command
- [x] payload mismatch for same `request_id` returns actionable reason code
- [x] command sequence generation is monotonic and persistent
Checks:
- [x] `make sanity`
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-002 Orchestration Resilience Guards

Ticket: SC-002
Scope: harden orchestration command dispatch path for duplicate/retry safety.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- tests/docs directly tied to these files
Out of scope:
- `shared-protocol/messages.v1.json` unless additive contract change is approved
Acceptance:
- [x] duplicate command idempotency validated in handler path
- [x] retry path does not emit duplicated node actions
- [x] failure responses contain actionable reason codes
Checks:
- [x] `make sanity`
- [x] orchestration server boots and endpoints respond
Deliverable:
- [x] branch + handoff note

## SC-003 Control UI Operator Confidence

Ticket: SC-003
Scope: improve operator visibility for orchestration connectivity and command result state.
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- minimal supporting files under `control-ui/app/`
Out of scope:
- no protocol/schema changes
Acceptance:
- [x] explicit connection state visible (`connected`, `reconnecting`, `disconnected`)
- [x] recent command result or error shown in UI
- [x] no regressions in existing node list/render flow
Checks:
- [x] `make sanity`
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-005 Orchestration Idempotency Integration Tests

Ticket: SC-005
Scope: verify persistent idempotency/replay and sequence monotonicity via API-level tests.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/tests/test_idempotency_integration.py`
Out of scope:
- protocol schema changes
Acceptance:
- [x] duplicate `request_id` returns replay marker without redispatch
- [x] payload mismatch for same `request_id` returns `REQUEST_ID_PAYLOAD_MISMATCH`
- [x] monotonic sequence remains increasing after ledger re-open
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-006 UI Request-ID Propagation + Result Reason Codes

Ticket: SC-006
Scope: ensure operator UI emits `request_id` and surfaces actionable command outcomes.
Owner: lead-agent (this chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
Out of scope:
- orchestration API contract changes
Acceptance:
- [x] command POSTs include `request_id`
- [x] UI displays request id and server reason/error detail for last command
- [x] no regression in existing control actions
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-007 Timeline Repository Reliability Tests

Ticket: SC-007
Scope: add deterministic tests for timeline track/clip ordering, cascade delete, and persistence.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/tests/test_timeline_repository.py`
Out of scope:
- UI layout changes
Acceptance:
- [x] track and clip ordering assertions
- [x] show delete cascades dependent rows
- [x] data survives repository re-open with same DB path
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-008 Operator API Contract Tests

Ticket: SC-008
Scope: enforce actionable reason-code behavior for operator-facing orchestration endpoints.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/tests/test_operator_contracts.py`
Out of scope:
- render-node runtime changes
Acceptance:
- [x] short-lead `PLAY_AT` returns `PLAY_AT_LEAD_TIME_TOO_SHORT`
- [x] no-target broadcast returns `NO_TARGETS`
- [x] replay response includes `DUPLICATE_REQUEST`
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-009 Unified Local Quality Gate

Ticket: SC-009
Scope: provide one command for full local validation across services.
Owner: lead-agent (this chat)
Files allowed:
- `Makefile`
- `README.md`
Out of scope:
- feature behavior changes
Acceptance:
- [x] `make check` runs orchestration tests, render-node tests, and UI lint/build
- [x] root docs mention `make check`
Checks:
- [x] `make check`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-010 Render Node Diagnostics + Resilience

Ticket: SC-010
Scope: improve render-node observability and startup robustness without protocol changes.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/app/state.py`
- `render-node/README.md`
Out of scope:
- orchestration server command schema changes
Acceptance:
- [x] registration retry with backoff
- [x] diagnostics snapshot support in node state
- [x] optional periodic diagnostics output from CLI flag
- [x] command history captures applied/ignored/error outcomes
Checks:
- [x] `python -m compileall render-node/app`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-011 Render Node State Tests

Ticket: SC-011
Scope: add repeatable tests for render-node state machine behavior.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/tests/test_state.py`
- `render-node/README.md`
Out of scope:
- protocol changes
- orchestration server runtime files
Acceptance:
- [x] duplicate/old sequence handling covered by test
- [x] PLAY_AT scheduling transition covered by test
- [x] diagnostics snapshot fields covered by test
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-012 Render Node Bridge Integration Tests

Ticket: SC-012
Scope: verify bridge call sequencing and error propagation in render-node state machine.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/tests/test_state_bridge.py`
Out of scope:
- orchestration server runtime files
Acceptance:
- [x] bridge call order assertions for command flow
- [x] bridge failure path marks node as `ERROR`
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-013 Render Node WS Command Guard

Ticket: SC-013
Scope: ignore unsupported websocket commands without crashing apply path.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/tests/test_agent.py`
Out of scope:
- protocol schema changes
Acceptance:
- [x] unsupported commands are ignored and tracked
- [x] valid commands still flow to state machine
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-014 Render Node Runtime Tuning Flags

Ticket: SC-014
Scope: expose interval tuning flags for heartbeat/tick loops.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/README.md`
Out of scope:
- orchestration server behavior
Acceptance:
- [x] heartbeat interval configurable
- [x] playback tick interval configurable
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-015 Render Node WS Reconnect Backoff

Ticket: SC-015
Scope: improve websocket reconnect from fixed delay to bounded exponential backoff.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
Out of scope:
- websocket protocol payload changes
Acceptance:
- [x] reconnect delay grows and caps by config
- [x] reconnect delay resets after successful connect
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-016 Render Node Bounded Runtime Mode

Ticket: SC-016
Scope: add optional auto-stop runtime budget for smoke runs.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/README.md`
Out of scope:
- service orchestration lifecycle changes
Acceptance:
- [x] `--max-runtime-sec` cleanly stops loops
- [x] cleanup still closes http client and bridge
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-017 Render Node Diagnostics Counters

Ticket: SC-017
Scope: include transport/command counters in periodic diagnostics output.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/README.md`
Out of scope:
- protocol schema changes
Acceptance:
- [x] heartbeat ok/error counters included
- [x] command received/ignored counters included
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-018 Render Node Diagnostics Snapshot Enrichment

Ticket: SC-018
Scope: include command history size metadata in diagnostics snapshots.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/state.py`
- `render-node/tests/test_state.py`
Out of scope:
- command schema changes
Acceptance:
- [x] `command_history_size` present
- [x] `command_history_limit` present
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-019 Render Node Reliability Test Suite Expansion

Ticket: SC-019
Scope: extend test coverage for agent/runtime guards and state+bridge interactions.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/tests/test_agent.py`
- `render-node/tests/test_state_bridge.py`
- `render-node/README.md`
Out of scope:
- orchestration server runtime files
Acceptance:
- [x] agent constructor guardrail tests
- [x] unsupported command guard test
- [x] bridge integration + failure tests
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-020 Render Node Unified Diagnostics Snapshot

Ticket: SC-020
Scope: centralize agent-level diagnostics snapshot generation.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
Acceptance:
- [x] `diagnostics_snapshot()` method added and used by diagnostics loop
- [x] includes agent + state metrics in one payload
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-021 Diagnostics File Output

Ticket: SC-021
Scope: support writing diagnostics snapshots to a local JSONL file.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/README.md`
Acceptance:
- [x] `--diagnostics-file` CLI flag added
- [x] diagnostics loop appends snapshots to file
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-022 Heartbeat Consecutive Failure Counter

Ticket: SC-022
Scope: expose consecutive heartbeat failure count in diagnostics.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
Acceptance:
- [x] counter increments on failures and resets on success
- [x] value present in diagnostics payload
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-023 WS Reconnect Attempt Counter

Ticket: SC-023
Scope: track reconnect attempts for websocket command channel.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
Acceptance:
- [x] reconnect attempts tracked and exported in diagnostics
- [x] counter reset on successful reconnect
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-024 Command Sequence Validation Guard

Ticket: SC-024
Scope: validate ws command `seq` before applying to state.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/tests/test_agent.py`
Acceptance:
- [x] non-integer and negative seq values are ignored safely
- [x] ignored counters and errors are updated
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-025 Malformed WS Frame Tolerance

Ticket: SC-025
Scope: keep ws loop alive when malformed JSON frames are received.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
Acceptance:
- [x] invalid JSON frame is ignored and tracked
- [x] loop continues without crashing
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-026 Agent Command Processing Tests

Ticket: SC-026
Scope: expand agent tests for command guard and valid command behavior.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/tests/test_agent.py`
Acceptance:
- [x] valid command path covered
- [x] invalid seq path covered
- [x] unsupported command path covered
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-027 Diagnostics Snapshot Contract Tests

Ticket: SC-027
Scope: ensure diagnostics snapshot exposes expected counters.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/tests/test_agent.py`
Acceptance:
- [x] snapshot contains heartbeat/reconnect/command counters
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-028 Command History Cap Coverage

Ticket: SC-028
Scope: verify command history cap behavior remains intact.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/tests/test_state.py`
Acceptance:
- [x] history remains capped at configured limit
- [x] newest command retained after overflow
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-029 Root Test Entrypoints

Ticket: SC-029
Scope: add root-level Make targets for render-node compile/test flows.
Owner: lead-agent (this chat)
Files allowed:
- `Makefile`
- `render-node/README.md`
Acceptance:
- [x] `make render-test` added
- [x] `make render-compile` added
Checks:
- [x] `make render-test`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note
