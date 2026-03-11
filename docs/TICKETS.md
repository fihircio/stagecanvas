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
- [x] `make sanity`
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
- [x] `make render-compile`
- [x] `make sanity`
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
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-053 Media Ingest Storage Wiring

Ticket: SC-053
Scope: wire media registry persistence to local filesystem storage stub.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/app/models.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_media_storage_stub.py`
- docs tied to these files
Out of scope:
- real object storage integration
- UI ingestion workflow
Acceptance:
- [x] registry persists media entries to a local storage stub
- [x] entries survive process restart in tests
- [x] API returns consistent metadata after reload
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-054 Asset Transfer Worker Stub

Ticket: SC-054
Scope: add async transfer queue worker with retry/backoff (no real file copy yet).
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_asset_transfer_worker.py`
- docs tied to these files
Out of scope:
- actual file transfer implementation
- UI changes
Acceptance:
- [x] transfer requests are queued and processed asynchronously
- [x] retries apply with bounded backoff on simulated failures
- [x] worker status is observable via snapshots or logs
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-055 Render Node Media Cache Index

Ticket: SC-055
Scope: add cache index and eviction policy stub on render-node.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/state.py`
- `render-node/tests/test_cache_index.py`
- `render-node/README.md`
Out of scope:
- real media decoding
- filesystem storage implementation
Acceptance:
- [x] cache index tracks assets with size/last-access metadata
- [x] eviction policy removes least-recently-used entries when over limit
- [x] tests cover eviction order and capacity enforcement
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-056 Mapping Config End-to-End Application

Ticket: SC-056
Scope: propagate mapping config from orchestration to render-node bridge and validate application path.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_mapping_config_flow.py`
- `render-node/app/state.py`
- `render-node/app/bridge.py`
- `render-node/tests/test_mapping_config_flow.py`
- docs tied to these files
Out of scope:
- real shader/mesh processing
- UI mapping editor
Acceptance:
- [x] mapping config flows from show update to node load to bridge `set_mapping`
- [x] invalid mapping config rejected with reason code
- [x] tests cover success and failure propagation
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-057 Preview Pipeline Stub

Ticket: SC-057
Scope: add preview pipeline stub (UI trigger -> orchestration -> node snapshot response).
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_preview_pipeline_stub.py`
- docs tied to these files
Out of scope:
- actual image/video preview rendering
- UI design overhaul
Acceptance:
- [x] UI can request a preview snapshot
- [x] orchestration returns stub response with node id + timestamp
- [x] tests cover request/response contract
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-058 Timeline Editor Drag/Reorder + Snapping Basics

Ticket: SC-058
Scope: add basic drag/reorder and snapping controls to timeline editor.
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/app/globals.css`
- `control-ui/lib/types.ts`
Out of scope:
- advanced multi-track selection
- audio/effects lanes
Acceptance:
- [x] track and clip order can be rearranged via simple drag controls
- [x] snapping toggle exists and affects UI ordering actions
- [x] UI updates without requiring full page refresh
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-059 Mapping UI Stub

Ticket: SC-059
Scope: add minimal mapping config load/save UI stub.
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- `control-ui/app/globals.css`
Out of scope:
- visual mesh editor
- image preview overlays
Acceptance:
- [x] operator can load/save mapping config JSON via modal or panel
- [x] validation errors surface from orchestration responses
- [x] config is sent with show update endpoints
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-060 Render-Node Video Playback Stub

Ticket: SC-060
Scope: add mock decoder playback loop tied to `PLAY_AT` timing.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/state.py`
- `render-node/app/agent.py`
- `render-node/tests/test_playback_stub.py`
- `render-node/README.md`
Out of scope:
- real codec integration
- GPU pipeline implementation
Acceptance:
- [x] playback stub starts at `PLAY_AT` target time and emits frame ticks
- [x] pause/stop affect stub state deterministically
- [x] tests cover timing offset and stop behavior
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-061 Control UI Dark Mode

Ticket: SC-061
Scope: add a dark mode theme with a user-visible toggle.
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/app/globals.css`
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/app/layout.tsx`
Out of scope:
- full redesign of layout
- new typography or branding system
Acceptance:
- [ ] dark mode can be toggled in the UI and persists for the session
- [ ] key panels (timeline, node cards, preview, actions) are legible in dark mode
- [ ] colors maintain sufficient contrast
Checks:
- [ ] `cd control-ui && npm run lint && npm run build`
- [ ] `make sanity`
Deliverable:
- [ ] branch + handoff note

## SC-062 Media Upload API + Local Storage

Ticket: SC-062
Scope: add media upload endpoint and store files locally for development.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_media_upload.py`
- docs tied to these files
Out of scope:
- production object storage integration
- UI upload flow
Acceptance:
 [x] `POST /api/v1/media/upload` accepts multipart file uploads
 [x] uploads stored under local `orchestration-server/data/media/`
 [x] registry entry created with filename, size, and checksum
Checks:
 [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
 [x] `make sanity`
Deliverable:
 [x] branch + handoff note

## SC-063 Media Transfer Worker v1

Ticket: SC-063
Scope: implement real file copy from orchestration storage to render-node cache for local dev.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/registry.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_media_transfer_worker.py`
- `render-node/app/state.py`
- `render-node/tests/test_state.py`
- docs tied to these files
Out of scope:
- distributed storage or CDN
- UI workflow changes
Acceptance:
 [x] transfer worker copies files from `orchestration-server/data/media/` to a render-node cache dir
 [x] cache state reflects transferred bytes and completion
 [x] tests validate file presence and cache metadata update
Checks:
 [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
 [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
 [x] `make sanity`
Deliverable:
 [x] branch + handoff note

## SC-064 Render-Node Local Cache Persistence

Ticket: SC-064
Scope: persist render-node cache index and restore on restart.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/state.py`
- `render-node/tests/test_cache_persistence.py`
- `render-node/README.md`
Out of scope:
- cross-node cache sync
- cloud storage
Acceptance:
- [x] cache index persists to local JSON file
- [x] restart restores cache metadata
- [x] tests validate persistence and restore accuracy
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-065 Playback Stub Reads Cached Media

Ticket: SC-065
Scope: extend playback stub to verify cached media presence before playing.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/state.py`
- `render-node/app/agent.py`
- `render-node/tests/test_playback_cache_gate.py`
- `render-node/README.md`
Out of scope:
- real decoding pipeline
- GPU playback
Acceptance:
- [x] `PLAY_AT` fails with reason code if required asset missing from cache
- [x] success path verifies cache metadata before playback start
- [x] tests cover missing asset and success cases
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-066 Media Profile Metadata + Validation

Ticket: SC-066
Scope: attach codec/format profile metadata and validate against supported profiles.
Owner: feature-agent (other chat)
Files allowed:
- `shared-protocol/messages.v1.json`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_media_profile_validation.py`
- docs tied to these files
Out of scope:
- transcoding implementation
- UI profile editor
Acceptance:
 [x] media registry stores codec profile (`HAP`, `HAP-Q`, `ProRes4444`, `H264`)
 [x] unsupported profiles rejected with reason code
 [x] tests cover acceptance + rejection paths
Checks:
 [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
 [x] `make sanity`
Deliverable:
 [x] branch + handoff note

## SC-067 Decoder Integration Stub

Ticket: SC-067
Scope: add a decoder interface stub and integrate it into the render-node playback path.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/app/state.py`
- `render-node/app/bridge.py`
- `render-node/tests/test_decoder_stub.py`
- `render-node/README.md`
Out of scope:
- GPU decoding
- real codec integration
Acceptance:
- [x] playback path calls decoder stub on `LOAD_SHOW` and `PLAY_AT`
- [x] decoder errors propagate to node state (`ERROR`)
- [x] tests cover success and failure paths
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-068 Transcoding Queue Stub

Ticket: SC-068
Scope: add a transcoding job queue stub and status tracking in orchestration.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_transcoding_queue_stub.py`
- docs tied to these files
Out of scope:
- real transcoding pipeline
- UI workflow
Acceptance:
- [x] media registry can enqueue a transcode job for an asset/profile
- [x] job status transitions are persisted in memory (queued/running/done/failed)
- [x] tests validate enqueue + status update + query
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-069 Mapping UI Editor v1

Ticket: SC-069
Scope: add a basic mapping editor panel (forms for outputs, mesh/blend params).
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- `control-ui/app/globals.css`
Out of scope:
- drag mesh editor
- live preview overlays
Acceptance:
- [x] operator can edit per-output mapping params in a form
- [x] save sends mapping config to orchestration show update
- [x] validation errors display inline
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-070 Preview Image Pipeline Stub

Ticket: SC-070
Scope: add preview image request/response stub through orchestration.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_preview_image_stub.py`
- `control-ui/components/nodes-dashboard.tsx`
- `control-ui/lib/types.ts`
- docs tied to these files
Out of scope:
- real image rendering
- binary transfer optimization
Acceptance:
- [x] UI can request a preview image and receives a stub payload
- [x] orchestration records last preview request time per node
- [x] tests validate request/response contract
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `cd control-ui && npm run lint && npm run build`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-071 Time Sync Abstraction

Ticket: SC-071
Scope: add a time-sync abstraction to support NTP/PTP later.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `render-node/app/agent.py`
- `render-node/tests/test_time_sync_stub.py`
- docs tied to these files
Out of scope:
- actual PTP integration
- kernel time discipline
Acceptance:
 [x] time sync source can be selected (system/ntp/ptp stub)
 [x] drift computation uses the abstraction
 [x] tests validate selection and default behavior
Checks:
 [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
 [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
 [x] `make sanity`
Deliverable:
 [x] branch + handoff note

## SC-072 OSC/HTTP Trigger Stub

Ticket: SC-072
Scope: add basic OSC/HTTP trigger stubs to orchestration for external cues.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/models.py`
- `orchestration-server/tests/test_trigger_stub.py`
- docs tied to these files
Out of scope:
- full trigger routing system
- security hardening
Acceptance:
 [x] add endpoints to register trigger rules and simulate trigger events
 [x] events are recorded in an in-memory log
 [x] tests validate register + fire + list behavior
Checks:
 [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
 [x] `make sanity`
Deliverable:
 [x] branch + handoff note

## SC-073 Real Timeline Model Migration

Ticket: SC-073
Scope: transition from simple show/clip stubs to a granular, hierarchical timeline model.
Owner: lead-agent (this chat)
Files allowed:
- `shared-protocol/messages.v1.json`
- `orchestration-server/app/models.py`
- `orchestration-server/app/registry.py`
- `orchestration-server/tests/test_timeline_model_v2.py`
Out of scope:
- rendering engine changes
- UI layout overhaul
Acceptance:
- [x] timeline supports multiple tracks and overlapping clips
- [x] clip metadata includes asset reference and timing offsets
- [x] orchestration persists and serves v2 timeline schema
- [x] migration path or clean-state validation for existing shows
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-074 Frame-Accurate Playback Scheduler

Ticket: SC-074
Scope: replace fixed 0.2s tick loop with a high-precision scheduler for sync playback.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/agent.py`
- `render-node/app/state.py`
- `render-node/tests/test_precision_scheduler.py`
Out of scope:
- real GPU rendering
- protocol version changes
Acceptance:
- [x] playback tick interval scales dynamically with system clock
- [x] drift correction logic maintains < 2ms error for OK status
- [x] scheduler handles transport state transitions (PAUSE/SEEK) with high precision
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-075 WebGPU Renderer Core

Ticket: SC-075
Scope: initialize a real GPU compositing engine for node rendering.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/bridge.py`
- `render-node/app/renderer_gpu.py`
- `render-node/tests/test_gpu_renderer.py`
Out of scope:
- real video decoding
- UI mapping editor
Acceptance:
- [x] RendererBridge implementation successfully initializes WebGPU context (or equivalent)
- [x] layers are composited as GPU textures with basic blend modes
- [x] renderer emits frame results to a local memory buffer for verification
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
Deliverable:
- [x] branch + handoff note

## SC-076 WebCodecs Video Decoding Engine

Ticket: SC-076
Scope: implement low-latency video decoding replacing existing NullDecoder.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/bridge.py`
- `render-node/app/decoder_webcodecs.py`
- `render-node/tests/test_video_decoder.py`
Out of scope:
- complex transcoding
- multi-output mapping
Acceptance:
- [x] Decoder implementation successfully decodes H.264/HAP sequences
- [x] decoded frames are available as GPU-ready textures
- [x] decoder handles seek and loop states correctly
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-077 AI Interaction Engine (YOLO/Pose)

Ticket: SC-077
Scope: integrate AI-powered vision triggers as the project USP.
Owner: feature-agent (other chat)
Files allowed:
- `interaction-engine/app.py`
- `interaction-engine/detectors/yolo.py`
- `interaction-engine/detectors/pose.py`
- `orchestration-server/app/main.py`
Out of scope:
- real-time video low-latency streaming to UI
- complex gesture training
Acceptance:
- [x] detection service correctly identifies YOLO objects or Pose positions
- [x] detection events trigger registered cues in orchestration-server
- [x] latency from detection to trigger emission is within acceptable bounds (<100ms)
Checks:
- [x] `python -m compileall interaction-engine`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-078 WebGPU Mesh Warping (Mapping Engine)

Ticket: SC-078
Scope: Implement grid and bezier warping inside the WebGPU pipeline to distort outputs.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/renderer_gpu.py`
- `render-node/app/mapping/warp_mesh.py`
- `render-node/tests/test_warp_mesh.py`
Out of scope:
- UI Mapping Editor integration
Acceptance:
- [x] Render pipeline accepts mesh geometry data (UV maps / vertices).
- [x] Textures are successfully mapped across the distorted grid.
- [x] Performance remains stable (<2ms latency addition).
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
Deliverable:
- [x] branch + handoff note

## SC-079 WebGPU Edge Blending & Masks (Mapping Engine)

Ticket: SC-079
Scope: Support alpha masks and gradient edge blending for multi-projector setups.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/renderer_gpu.py`
- `render-node/app/mapping/edge_blend.py`
- `render-node/tests/test_edge_blend.py`
Out of scope:
- Multi-GPU communication
Acceptance:
- [x] Renderer pipeline applies soft-edge blend masks to the final composited texture.
- [x] Alpha masking for custom stage shapes works via projected shapes.
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
Deliverable:
- [x] branch + handoff note

## SC-080 OSC Server Integration (IO Engine)

Ticket: SC-080
Scope: Allow external lighting desks and triggers via Open Sound Control (OSC).
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/io/osc_server.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_osc_server.py`
Out of scope:
- MIDI
Acceptance:
- [x] OSC Server runs alongside the API server.
- [x] Maps incoming OSC UDP packets to the internal trigger/cue REST API.
- [x] Secure/bound to configurable port (default 8000).
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-081 MIDI Control Engine (IO Engine)

Ticket: SC-081
Scope: Support MIDI hardware mapping for tactile control and triggers.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/io/midi_handler.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_midi_handler.py`
Out of scope:
- WebMIDI in UI
Acceptance:
- [x] Application connects to active MIDI devices.
- [x] MIDI CC messages route to layer opacity or transformations.
- [x] MIDI Note messages trigger cues.
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-082 Precision Time Protocol (PTP) Sync Stub

Ticket: SC-082
Scope: Migrate local time sync to an abstract PTP sync provider for multi-node lock.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/sync_manager.py`
- `render-node/app/agent.py`
- `render-node/tests/test_ptp_sync.py`
Out of scope:
- Kernel driver integration
Acceptance:
- [x] PTP Clock abstraction implemented.
- [x] Calculates true drift across the network, accounting for latency jitter.
- [x] Plugs directly into the Frame-Accurate Playback Scheduler (SC-074).
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-083 Node-Graph Designer Frontend (React)

Ticket: SC-083
Scope: Evolve the editor to a visual node-based programming model bridging UI to AI triggers.
Owner: feature-agent (other chat)
Files allowed:
- `control-ui/components/node-graph.tsx`
- `control-ui/app/designer/page.tsx`
- `control-ui/package.json`
Out of scope:
- Advanced timeline lanes UI
Acceptance:
- [x] Implementation of `reactflow` (or similar) canvas.
- [x] Visual blocks for "Camera Input", "YOLO Trigger", "Play Clip".
- [x] Edges drawn between blocks compile to a Show Rule JSON sent to the orchestrator.
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-084 ArtNet / DMX Control Engine (IO Engine)

Ticket: SC-084
Scope: Allow lighting consoles to control the media server natively over DMX.
Owner: feature-agent (other chat)
Files allowed:
- `orchestration-server/app/io/artnet_server.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_artnet_server.py`
Out of scope:
- Full Fixture Profile generation
Acceptance:
- [x] ArtNet listener daemon runs in the background on port 6454.
- [x] DMX Universe/Channel combinations map dynamically to Layer properties (Opacity, Speed, Play/Pause).
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-085 NDI / Spout Output Integration

Ticket: SC-085
Scope: Enterprise video routing capabilities without physical capture cards.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/output/ndi_sender.py`
- `render-node/app/renderer_gpu.py`
- `render-node/tests/test_ndi_sender.py`
Out of scope:
- NDI Ingest (Inputs)
Acceptance:
- [x] Extends the WebGPU pipeline to push the final composited frame to an NDI sender stream.
- [x] NDI stream is discoverable on the local network.
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
Deliverable:
- [x] branch + handoff note

## SC-086 Hardware Genlock Sync Stub

Ticket: SC-086
Scope: Sub-frame synchronization across multiple physical LED walls via hardware sync pulses.
Owner: lead-agent (this chat)
Files allowed:
- `render-node/app/sync_genlock.py`
- `render-node/app/renderer_gpu.py`
- `render-node/tests/test_sync_genlock.py`
Out of scope:
- Direct Quadro/Decklink driver API integration (mock only)
Acceptance:
- [x] Renderer tick loop holds frame flip until Genlock pulse is received.
- [x] Drift metrics correctly account for Genlock holding time.
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-087 Redundancy & Auto-Failover

Ticket: SC-087
Scope: Implement Primary/Backup heartbeating for orchestration reliability.
Owner: lead-agent (this chat)
Files allowed:
- `orchestration-server/app/cluster_manager.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_failover.py`
Out of scope:
- Multi-master active-active writing
Acceptance:
- [x] Backup node monitors Primary via dedicated heartbeat endpoint.
- [x] Backup promotes to Primary within 3 seconds of Primary failure.
- [x] Render-nodes gracefully reconnect to the promoted Backup.
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-088 WebRTC Browser Monitoring

Ticket: SC-088
Scope: Allow operators to view the live rendering output inside the Next.js control UI.
Owner: feature-agent (other chat)
Files allowed:
- `render-node/app/output/webrtc_stream.py`
- `control-ui/components/live-monitor.tsx`
- `control-ui/package.json`
Out of scope:
- Public internet relay (STUN/TURN handling)
Acceptance:
- [x] Render node encodes its output map to a lightweight WebRTC stream.
- [x] Control UI dashboard can connect to the local stream and display moving video at >15 fps.
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-089 Node-Graph Compiler & Dispatch

Ticket: SC-089
Scope: Compile visual ReactFlow connections into Show Rules and dispatch them to the Orchestrator API.
Owner: feature-agent
Files allowed:
- `control-ui/components/node-graph.tsx`
- `control-ui/lib/compiler.ts`
- `orchestration-server/app/main.py`
Acceptance:
- [x] Connecting a "YOLO Trigger" to a "Play Clip" node correctly updates the Orchestrator's rules DB.
- [x] UI reflects deployment success/failure status.
Deliverable:
- [x] branch + handoff note

## SC-090 Production NDI & WebRTC SDK Integration

Ticket: SC-090
Scope: Replace stubs with real NDI 5 and aiortc encoding.
Owner: feature-agent
Files allowed:
- `render-node/app/output/ndi_sender.py`
- `render-node/app/output/webrtc_stream.py`
- `render-node/requirements.txt`
Acceptance:
- [x] Real NDI stream visible in NDI Studio Monitor.
- [x] WebRTC stream supports H.264 hardware encoding where available.
Deliverable:
- [x] branch + handoff note

## SC-091 DMX/ArtNet Fixture Profile Engine

Ticket: SC-091
Scope: Define a formal JSON schema for DMX-to-Parameter mapping.
Owner: lead-agent
Files allowed:
- `shared-protocol/fixtures.json`
- `orchestration-server/app/io/artnet_server.py`
Acceptance:
- [x] Users can define custom ArtNet profiles (e.g. Channel 1=Opacity, 2=Speed).
- [x] Orchestrator handles multiple universes simultaneously.
Deliverable:
- [x] branch + handoff note

## SC-092 Multi-Node Canvas Splitting

Ticket: SC-092
Scope: Split a giant canvas into sub-segments for distributed rendering.
Owner: lead-agent
Files allowed:
- `orchestration-server/app/models.py`
- `render-node/app/renderer_gpu.py`
- `shared-protocol/messages.v1.json`
Acceptance:
- [x] Orchestrator can command Node A to render Top-Left 4K and Node B to render Bottom-Right 4K.
- [x] Sync maintained across the split via PTP.
Deliverable:
- [x] branch + handoff note

## SC-093 GPU Texture Sharing (NDI/Spout) Performance Optimization

Ticket: SC-093
Scope: Optimize texture readout from WebGPU for zero-copy streaming.
Owner: feature-agent
Files allowed:
- `render-node/app/renderer_gpu.py`
- `render-node/app/output/ndi_sender.py`
Acceptance:
- [x] Reduction in CPU usage compared to standard `read_texture` calls.
- [x] Maintain 60fps at 4K resolution.
Deliverable:
- [x] branch + handoff note

## SC-094 Automated Asset Transcoding Service (HAP/DXV)

Ticket: SC-094
Scope: Background service to optimize raw video uploads for GPU efficiency.
Owner: feature-agent
Files allowed:
- `orchestration-server/app/services/transcoder.py`
- `orchestration-server/requirements.txt`
- `shared-protocol/assets.json`
Acceptance:
- [x] Uploaded MP4/MOV files are automatically converted to HAP (MOV) or DXV (MOV) using FFmpeg.
- [x] Transcoded assets are linked in the show metadata instead of original files.
- [x] Status updates (Progress %) are emitted via WebSockets to the UI.
Deliverable:
- [x] branch + handoff note

## SC-095 Dynamic Node Discovery & Health Dashboard

Ticket: SC-095
Scope: mDNS discovery of render nodes and a pro-grade health dashboard.
Owner: lead-agent
Files allowed:
- `render-node/app/discovery.py`
- `orchestration-server/app/registry.py`
- `control-ui/app/nodes/page.tsx`
Acceptance:
- [x] Render nodes broadcast presence via mDNS (Zeroconf).
- [x] Orchestration server automatically registers new nodes.
- [x] Dashboard displays GPU Temp, VRAM usage, and Frame-Sync status in real-time.
Deliverable:
- [x] branch + handoff note

## SC-096 Generative AI Visual Layer (SD-Lite)

Ticket: SC-096
Scope: Real-time generative layer type for the GPU engine.
Owner: feature-agent
Files allowed:
- `render-node/app/layers/generative_ai.py`
- `render-node/app/renderer_gpu.py`
Acceptance:
- [x] New layer type "Generative AI" that accepts text prompts.
- [x] Use a lightweight SD stub or API call to render frames directly into the GPU compositor.
Deliverable:
- [x] branch + handoff note

## SC-097 Spatial Show Control (PSN/Stage Automation)

Ticket: SC-097
Scope: Integration of PosiStageNet (PSN) or similar stage automation protocols.
Owner: lead-agent
Files allowed:
- `orchestration-server/app/io/psn_listener.py`
- `shared-protocol/automation.json`
Acceptance:
- [x] Listen for incoming 3D coordinates of stage moving heads/scenery.
- [x] Map 3D positions to layer coordinates or mask origins in real-time.
Deliverable:
- [x] branch + handoff note

## SC-098 Multi-User Collaboration & Operational Locks

Ticket: SC-098
Scope: Concurrent editing safeguards for the control UI.
Owner: feature-agent
Files allowed:
- `orchestration-server/app/collaboration.py`
- `control-ui/hooks/use-locks.ts`
Acceptance:
- [x] Visual indicators when another user is editing a specific clip or rule.
- [x] Simple mutex "Lock" for show-day safety (Take Control / Release Control).
Deliverable:
- [x] branch + handoff note

## SC-099 Pro Shader Effects (LUT, Color, Blur)

Ticket: SC-099
Scope: Implement a post-processing effects pipeline inside the WebGPU renderer.
Owner: feature-agent (Agent D)
Files allowed:
- `render-node/app/renderer_gpu.py`
- `render-node/app/effects/shader_library.py`
- `render-node/tests/test_shader_effects.py`
Out of scope:
- UI for effect parameter tuning (Next.js side)
Acceptance:
- [x] Implement a reusable Effect shader structure in the WebGPU pipeline.
- [x] Add at least 3 core effects: 3D LUT (Color Grading), Gaussian Blur, and Brightness/Contrast/Saturation.
- [x] Effects can be enabled/disabled per layer via the `snapshot` update.
Checks:
- [x] `python -m unittest discover -s render-node/tests -p 'test_*.py'`
- [x] `make render-compile`
Deliverable:
- [x] branch + handoff note

## SC-100 SMPTE Linear Timecode (LTC) Integration

Ticket: SC-100
Scope: Lock StageCanvas playback to incoming SMPTE LTC timecode.
Owner: lead-agent
Files allowed:
- `orchestration-server/app/io/ltc_reader.py`
- `orchestration-server/app/main.py`
- `orchestration-server/tests/test_ltc_reader.py`
Acceptance:
- [x] LTC decoder parses incoming 24/25/29.97/30fps SMPTE audio signal.
- [x] Timeline playhead snaps to the incoming timecode with <1 frame error.
- [x] Show correctly chases, jams-syncs, and free-wheels when LTC signal is lost.
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
- [x] `make sanity`
Deliverable:
- [x] branch + handoff note

## SC-101 Effects Parameter UI (Next.js)

Ticket: SC-101
Scope: Build the visual panel in the control UI to tune the Pro Shader Effects.
Owner: feature-agent
Files allowed:
- `control-ui/components/effects-panel.tsx`
- `control-ui/app/designer/page.tsx`
- `control-ui/package.json`
Acceptance:
- [x] Sliders and toggles for Color Correction (B/C/S), Blur radius, and LUT selection.
- [x] Parameter changes apply in real-time to the affected render layer via the WebSocket API.
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-102 Performance Benchmark Suite

Ticket: SC-102
Scope: Automated performance regression tests for the render pipeline.
Owner: feature-agent
Files allowed:
- `render-node/benchmarks/bench_gpu_pipeline.py`
- `Makefile`
Acceptance:
- [x] Benchmarks measure: frames composited/second, shader effect cost (ms per pass), PTP drift standard deviation.
- [x] Output formatted as a JSON report for CI comparison.
- [x] `make bench` runs cleanly.
Checks:
- [x] `make bench`
Deliverable:
- [x] branch + handoff note

## SC-103 Public REST SDK & API Docs

Ticket: SC-103
Scope: Formalize the Orchestration Server REST API with auto-generated OpenAPI docs.
Owner: lead-agent
Files allowed:
- `orchestration-server/app/main.py`
- `orchestration-server/app/api/routes_v1.py`
- `docs/API.md`
Acceptance:
- [x] `/docs` endpoint serves interactive Swagger UI.
- [x] All public endpoints have schemas, example payloads, and error codes documented.
- [x] `docs/API.md` provides a quick-start guide for third-party integration.
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-104 Mobile Operator UI (PWA)

Ticket: SC-104
Scope: Progressive Web App version of the control dashboard for handheld operation.
Owner: feature-agent
Files allowed:
- `control-ui/manifest.json`
- `control-ui/app/layout.tsx`
- `control-ui/components/mobile-cue-panel.tsx`
Acceptance:
- [x] Dashboard installable as a PWA on iOS/Android.
- [x] Mobile Cue Panel shows the top 8 cue buttons for one-touch triggering.
- [x] Offline service worker caches the app shell.
Checks:
- [x] `cd control-ui && npm run lint && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-105 Pixel Mapping & DMX Output (IO Engine)

Ticket: SC-105
Scope: Output video pixels to DMX lighting fixtures (LED strips/panels).
Owner: feature-agent
Files allowed:
- `orchestration-server/app/io/artnet_sender.py`
- `render-node/app/mapping/pixel_mapper.py`
Acceptance:
- [x] Render Node samples specific UV coordinates from the compositor buffer.
- [x] Orchestrator sends sampled colors over ArtNet to external fixtures.
- [x] Supports minimum 10 universes at >30fps.
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-106 Multi-Channel Audio Playback Engine

Ticket: SC-106
Scope: Precision audio routing and playback synced with timeline.
Owner: lead-agent
Files allowed:
- `render-node/app/audio_engine.py`
- `shared-protocol/messages.v1.json`
Acceptance:
- [x] Support up to 16 channels of ASIO / CoreAudio output.
- [x] Sub-frame lock between audio playhead and WebGPU flip via the Precision Scheduler.
Checks:
- [x] `make render-test`
Deliverable:
- [x] branch + handoff note

## SC-107 AI Generative Stems (Audio-Reactive)

Ticket: SC-107
Scope: AI visual layers react dynamically to incoming audio FFT.
Owner: feature-agent
Files allowed:
- `render-node/app/layers/generative_ai.py`
- `render-node/app/audio_analysis.py`
Acceptance:
- [x] Extract real-time frequency bands (Kick, Snare, Highs) from system audio.
- [x] Pass FFT data as uniform buffers to the Generative AI layer and standard Effects.
- [x] Visuals pulse/react to the beat reliably.
Checks:
- [x] `make render-compile`
Deliverable:
- [x] branch + handoff note

## SC-108 3D Pre-Viz Stage Simulator (Next.js)

Ticket: SC-108
Scope: Live 3D viewing of the stage logic without physical hardware.
Owner: lead-agent
Files allowed:
- `control-ui/components/stage-previz.tsx`
- `control-ui/package.json`
Acceptance:
- [x] Integrate `react-three-fiber`.
- [x] Represent projector outputs and bounding boxes in a basic 3D room.
- [x] Stream WebRTC low-res textures onto the 3D screens for live pre-vis.
Checks:
- [x] `cd control-ui && npm run build`
Deliverable:
- [x] branch + handoff note

## SC-109 System Archiving & Show Packaging

Ticket: SC-109
Scope: Export and import total show configurations including gigabytes of assets.
Owner: feature-agent
Files allowed:
- `orchestration-server/app/services/archiver.py`
- `orchestration-server/app/main.py`
Acceptance:
- [x] One-click export to a `.stage` compressed tarball containing SQLite DB + all assets.
- [x] Show import overwrites current registry cleanly.
Checks:
- [x] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [x] branch + handoff note

## SC-110 AI Scene-Segmentation (Background Removal)

Ticket: SC-110
Scope: Real-time background removal for live camera feeds via AI.
Owner: feature-agent
Files allowed:
- `render-node/app/layers/ai_segmentation.py`
- `render-node/app/renderer_gpu.py`
- `render-node/requirements.txt`
Acceptance:
- [ ] Implement a live segmentation layer using a lightweight model (e.g., Mediapipe or SelfieSegmentation).
- [ ] Extract alpha mask from live camera input and apply it to the video stream on the GPU.
- [ ] Run at >30fps on standard hardware.
Checks:
- [ ] `make render-compile`
Deliverable:
- [ ] branch + handoff note

## SC-111 Global Asset Sync (Cloud S3 Integration)

Ticket: SC-111
Scope: Cloud-based asset synchronization for multi-node/multi-site shows.
Owner: lead-agent
Files allowed:
- `orchestration-server/app/services/cloud_sync.py`
- `orchestration-server/requirements.txt`
Acceptance:
- [ ] Support S3-compatible storage for asset backups and distributed sync.
- [ ] Orchestration server automatically pulls assets from cloud when a show is loaded on a new site.
- [ ] Progress reporting for background downloads based on WebSocket API.
Checks:
- [ ] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [ ] branch + handoff note

## SC-112 Visual Scripting Engine (Logic Blocks)

Ticket: SC-112
Scope: Add logic nodes (If/Then, Timers, Math) to the Node Graph designer.
Owner: feature-agent
Files allowed:
- `control-ui/components/node-graph.tsx`
- `control-ui/lib/compiler.ts`
- `orchestration-server/app/collaboration.py`
Acceptance:
- [ ] New node types: "Timer", "Counter", "Compare", "Boolean Logic".
- [ ] Logic compiles to a backend persistent state machine in the Orchestration Server.
- [ ] Ability to trigger Layer properties based on logic outcomes (e.g., "If AI_DETECTED count > 5, Play Clip X").
Checks:
- [ ] `cd control-ui && npm run build`
Deliverable:
- [ ] branch + handoff note

## SC-113 Enterprise RBAC & User Management

Ticket: SC-113
Scope: Role-Based Access Control for large broadcast teams.
Owner: lead-agent
Files allowed:
- `orchestration-server/app/auth.py`
- `orchestration-server/app/models.py`
- `control-ui/hooks/use-auth.ts`
Acceptance:
- [ ] Define roles: Viewer, Operator, Designer, Admin.
- [ ] Operational locks (SC-098) restricted based on role permissions.
- [ ] Basic JWT authentication and session management.
Checks:
- [ ] `python -m unittest discover -s orchestration-server/tests -p 'test_*.py'`
Deliverable:
- [ ] branch + handoff note

## SC-114 VR Operator Console (OpenXR)

Ticket: SC-114
Scope: Experimental support for operating the media server in a VR environment.
Owner: feature-agent
Files allowed:
- `control-ui/components/vr-console.tsx`
- `control-ui/package.json`
Acceptance:
- [ ] basic WebXR/OpenXR support in the 3D Pre-Viz renderer (SC-108).
- [ ] Virtual trigger buttons controllable via VR controllers.
- [ ] Stereoscopic view for 3D stage simulation.
Checks:
- [ ] `cd control-ui && npm run build`
Deliverable:
- [ ] branch + handoff note
