# StageCanvas Determinism Spec v0.1

## Scope

Defines minimum timing guarantees for multi-node playback in MVP.

## Protocol Guardrails

- Protocol version is pinned to `v1` for command and heartbeat payloads.
- Unknown protocol versions must be rejected at API boundaries.
- Commands are sequence-based and expected to be monotonic per node.

## PLAY_AT Scheduling Rules

- `PLAY_AT` uses absolute epoch milliseconds (`target_time_ms`).
- Minimum lead time is required to avoid late starts.
- MVP rule: `target_time_ms` must be at least `1500 ms` in the future at dispatch time.

## Drift SLO

Drift is measured as absolute timing difference in milliseconds:

- `OK`: `abs(drift_ms) < 2.0`
- `WARN`: `2.0 <= abs(drift_ms) < 8.0`
- `CRITICAL`: `abs(drift_ms) >= 8.0`

MVP intent:

- Keep all active nodes in `OK` during normal operation.
- `WARN` is actionable and should surface in operator UI.
- `CRITICAL` indicates visible desync risk and requires immediate operator action.

## Operator Stream Contract

Operator snapshots should include:

- Per-node `drift_level` classification
- SLO thresholds (`warn_ms`, `critical_ms`)
- Aggregated counts (`ok`, `warn`, `critical`)

## Future Upgrades

- Persist drift history for trend-based alerting.
- Add jitter and packet-delay metrics.
- Add PTP discipline and compare against NTP baseline.

