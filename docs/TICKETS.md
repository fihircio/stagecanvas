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

## SC-030 Diagnostics Sampling + Log Stream Split

Ticket: SC-030
Scope: reduce diagnostics noise and split info/warn/error output streams.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/tests/test_agent.py`
- `render-node/README.md`
Out of scope:
- protocol/schema changes
Acceptance:
- [x] diagnostics sampling control added (`--diagnostics-sample-every`)
- [x] diagnostics snapshot includes emit/skip counters
- [x] info logs route to stdout and warn/error logs route to stderr
Checks:
- [x] `make render-test`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-031 Warn Log Backpressure / Rate Limiting

Ticket: SC-031
Scope: rate-limit repeated warn events to reduce log flood during unstable network/runtime conditions.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/tests/test_agent.py`
- `render-node/README.md`
Out of scope:
- protocol/schema changes
Acceptance:
- [x] repeated warn events are rate-limited per event key
- [x] suppression summary emitted when rate-limit window rolls over
- [x] diagnostics snapshot includes warn emitted/suppressed counters
- [x] runtime flags added for rate-limit tuning
Checks:
- [x] `make render-test`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-032 Render Node End-to-End Smoke Gate

Ticket: SC-032
Scope: add a one-command bounded runtime smoke check for render-node against local orchestration.
Owner: lead-agent (this chat)
Files allowed:
- `scripts/render-smoke.sh`
- `Makefile`
- `render-node/README.md`
Out of scope:
- orchestration runtime behavior changes
- protocol/schema changes
Acceptance:
- [x] smoke script starts orchestration, runs bounded render-node session, and validates diagnostics output
- [x] root target `make render-smoke` added
- [x] smoke artifacts stored under `.sanity-logs/render-smoke`
Checks:
- [x] `make render-smoke`
- [x] `make render-test`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-033 Drift Classification in Runtime

Ticket: SC-033
Scope: enforce per-node `drift_ms -> OK/WARN/CRITICAL` classification in orchestration snapshots per determinism spec.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_drift_classification.py`
Out of scope:
- protocol/schema version changes
Acceptance:
- [x] classification boundaries match `docs/DETERMINISM.md` (`<2 OK`, `>=2 WARN`, `>=8 CRITICAL`)
- [x] snapshot node views expose classified `drift_level`
- [x] SLO aggregate counts align with per-node classification
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-034 Operator Drift Alerting UI

Ticket: SC-034
Scope: surface drift level counts and per-node alert badges in control UI (WATCHNET-like observability).
Owner: lead-agent (this chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/app/globals.css`
Out of scope:
- command dispatch behavior changes
Acceptance:
- [x] visible drift level counts (`OK/WARN/CRITICAL`) in node status panel
- [x] per-node drift level badge with distinct visual severity
- [x] node card alert styling triggers on non-OK drift level
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-038 Per-node Replay Counters in Operator Snapshot

Ticket: SC-038
Scope: add per-node reliability counters (replay/queued/reconnect + queue depth) to operator snapshots.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_operator_snapshot_reliability.py`
Out of scope:
- protocol major-version changes
Acceptance:
- [x] operator snapshots include per-node replay counter
- [x] operator snapshots include queued/reconnect counters and queue depth
- [x] websocket operator snapshot test validates counter presence/behavior
Checks:
- [x] `cd orchestration-server && python -m unittest discover -s tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-039 Reliability Panel in Control UI

Ticket: SC-039
Scope: show replay counters, reconnect counts, and queue depth badges in control UI.
Owner: lead-agent (this chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- `control-ui/app/globals.css`
Out of scope:
- command dispatch behavior changes
Acceptance:
- [x] panel-level reliability totals visible
- [x] per-node queue depth badge visible
- [x] per-node replay/reconnect counters visible
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-040 Preload Lifecycle Contract v2

Ticket: SC-040
Scope: update preload cache contract to v2 lifecycle states and progress fields.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_preload_contract_v2.py`
Out of scope:
- non-cache command schema changes
Acceptance:
- [x] lifecycle states normalized to `EMPTY/LOADING/READY/FAILED`
- [x] progress fields present (`progress_assets_pct`, `progress_bytes_pct`, `progress_message`)
- [x] legacy heartbeat states accepted and normalized for backward compatibility
Checks:
- [x] `cd orchestration-server && python -m unittest discover -s tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-041 Preload Integration Reliability Tests

Ticket: SC-041
Scope: multi-node preload success/partial-failure/retry tests.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/tests/test_preload_reliability.py`
Out of scope:
- UI changes beyond SC-043
Acceptance:
- [x] multi-node preload success and partial-failure states covered
- [x] retry with new request_id dispatches again
Checks:
- [x] `cd orchestration-server && python -m unittest discover -s tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-042 Play Gating by Preload Readiness

Ticket: SC-042
Scope: PLAY_AT rejected with reason code when target nodes not ready.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_play_at_preload_gate.py`
Out of scope:
- protocol major-version changes
Acceptance:
- [x] `PLAY_AT` rejects with `PLAY_AT_PRELOAD_NOT_READY` when any target node not READY
- [x] `PLAY_AT` allowed when all targets READY for the show
Checks:
- [x] `cd orchestration-server && python -m unittest discover -s tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-043 Operator Preload Controls

Ticket: SC-043
Scope: preload action + per-node readiness in UI + actionable errors.
Owner: lead-agent (this chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- `control-ui/app/globals.css`
Out of scope:
- orchestration runtime changes beyond SC-041/042
Acceptance:
- [x] operator can trigger preload for all nodes or selected targets
- [x] node cards show cache lifecycle state and progress
- [x] actionable preload errors surface through existing command result panel
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-035 Two-Node Sync Proof Test

Ticket: SC-035
Scope: add deterministic integration proof that two nodes execute `PLAY_AT` under drift SLO.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/tests/test_two_node_sync_proof.py`
Out of scope:
- protocol/schema version changes
Acceptance:
- [x] test verifies both nodes receive identical `PLAY_AT` `target_time_ms` and sequence
- [x] test verifies both nodes report `PLAYING` drift within `OK` threshold (`< warn_ms`)
- [x] test ties directly to MVP acceptance in `docs/ARCHITECTURE.md`
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-036 Media Preload + Local Cache Contract (MVP Stub)

Ticket: SC-036
Scope: define additive orchestration->node preload flow and node cache state reporting.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/models.py`
- `orchestration-server/app/main.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_preload_contract.py`
- `render-node/app/state.py`
- `render-node/tests/test_state.py`
- docs tied to these files
Out of scope:
- breaking changes to existing command protocol
Acceptance:
- [x] `POST /api/v1/shows/preload` endpoint added
- [x] preload dispatch uses additive payload contract (`LOAD_SHOW` + `preload_only`)
- [x] heartbeat and node snapshot include optional cache contract fields
- [x] render-node state updates cache contract on preload command
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-037 Reconnect Replay Reliability

Ticket: SC-037
Scope: prove offline queued command replay behavior across disconnect/reconnect cycles.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/tests/test_reconnect_replay_reliability.py`
Out of scope:
- websocket schema changes
Acceptance:
- [x] offline command is queued and replayed on first reconnect
- [x] reconnect without new commands does not replay old command again
- [x] command ordering remains monotonic across reconnect cycles
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-044 Drift History Ring Buffer API

Ticket: SC-044
Scope: persist short rolling drift history for trend analysis and alerting.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_drift_history.py`
- docs tied to these files
Out of scope:
- long-term metrics storage backend
- UI chart implementation
Acceptance:
- [x] per-node rolling drift history buffer exposed via snapshot/additive endpoint field
- [x] history window size is bounded and configurable
- [x] deterministic tests verify eviction order and data integrity
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-045 Sustained Drift Alert Policy

Ticket: SC-045
Scope: add sustained WARN/CRITICAL alert policy to reduce one-off drift noise.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_sustained_drift_alerts.py`
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- docs tied to these files
Out of scope:
- PTP/genlock implementation
- breaking protocol changes
Acceptance:
- [x] alert raised only after configurable consecutive WARN/CRITICAL windows
- [x] alert clears after sustained return to `OK`
- [x] operator UI surfaces sustained alert state distinctly from instantaneous drift level
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-046 Drift History Summary in Operator Snapshot

Ticket: SC-046
Scope: expose compact drift history summaries via operator websocket snapshots.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_operator_drift_history_summary.py`
- docs tied to these files
Out of scope:
- UI chart implementation
- long-term metrics storage
Acceptance:
- [ ] operator snapshot includes per-node drift history summary fields (min/avg/max + sample count)
- [ ] summary derives from existing ring buffer without extra storage
- [ ] deterministic tests validate summary math for edge cases (empty/history size 1)
Checks:
- [ ] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [ ] `make sanity`
Deliverable:
- [ ] branch + handoff note

## SC-047 Media Ingest Registry v1

Ticket: SC-047
Scope: add media registry metadata model and endpoints for ingest tracking.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/models.py`
- `orchestration-server/app/main.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_media_registry.py`
- docs tied to these files
Out of scope:
- actual media upload/transfer implementation
- UI ingestion workflow
Acceptance:
- [x] media registry supports create/list/get/update status for assets
- [x] asset entries include codec profile, duration, and size metadata fields
- [x] tests cover idempotent asset registration by stable `asset_id`
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [ ] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-048 Node Asset Transfer Stub

Ticket: SC-048
Scope: add orchestration-to-node asset transfer stub and status reporting.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_asset_transfer_stub.py`
- `render-node/app/state.py`
- `render-node/tests/test_state.py`
- docs tied to these files
Out of scope:
- real file transfer implementation
- protocol major-version changes
Acceptance:
- [x] transfer command stub emitted per asset with progress callbacks simulated in tests
- [x] node cache state updates for transfer in-progress and completed states
- [x] orchestration surfaces transfer status in node snapshots
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-049 Render Bridge Integration Path v1

Ticket: SC-049
Scope: define and validate render-node bridge integration path for real renderer hook-in.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/bridge.py`
- `render-node/app/agent.py`
- `render-node/tests/test_bridge_integration.py`
- `render-node/README.md`
Out of scope:
- production Unity project integration
- GPU pipeline implementation
Acceptance:
- [x] bridge interface supports load/play/pause/seek/stop with error propagation
- [x] mock bridge test validates call order for `LOAD_SHOW` + `PLAY_AT`
- [x] integration test validates error path marks node `ERROR`
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [ ] `make render-compile`
- [ ] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-050 Warp/Blend Pipeline Skeleton

Ticket: SC-050
Scope: introduce mapping config wiring and render-node pipeline hooks for warp/blend.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/state.py`
- `render-node/app/bridge.py`
- `render-node/tests/test_warp_blend_pipeline.py`
- `docs/ARCHITECTURE.md`
Out of scope:
- real shader/mesh processing
- UI mapping editor
Acceptance:
- [x] mapping config can be loaded per node and attached to state
- [x] render bridge receives mapping config on `LOAD_SHOW`
- [x] tests validate config propagation and error handling
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-051 Timeline Editor MVP

Ticket: SC-051
Scope: add basic timeline editor actions in control UI (tracks + clips CRUD).
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- `control-ui/app/globals.css`
- `control-ui/app/page.tsx`
Out of scope:
- complex snapping/drag reordering
- audio/effects lane features
Acceptance:
- [x] create/update/delete tracks and clips via existing orchestration endpoints
- [x] timeline list updates immediately after mutations
- [x] optimistic UI errors surfaced with actionable reason
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-052 Mapping Config Model + Validation

Ticket: SC-052
Scope: define mapping configuration schema and validation rules for warp/blend.
Owner: lead-agent (this chat)
Files allowed:
- `shared-protocol/messages.v1.json`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_mapping_config_schema.py`
- docs tied to these files
Out of scope:
- UI editor for mapping configuration
- render-node shader implementation
Acceptance:
- [x] mapping config schema supports per-output mesh + blend params
- [x] orchestration validates schema on show update/load
- [x] tests cover invalid/missing fields and version compatibility
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [ ] `make sanity`
Deliverable:
- [x] branch + handoff note
