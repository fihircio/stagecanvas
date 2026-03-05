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
