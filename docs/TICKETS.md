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
