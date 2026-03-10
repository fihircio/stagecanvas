# Render Node

Current implementation:

- Persistent connection to orchestration server
- Local state machine for show lifecycle
- Playback simulation loop
- Metrics and heartbeat emission
- Renderer bridge contract for Unity integration

Implemented commands:

- `LOAD_SHOW`
- `PLAY_AT`
- `PAUSE`
- `SEEK`
- `STOP`
- `PING`
Note: `LOAD_SHOW` payload may include `mapping_config` for warp/blend wiring.

## Run One Node

```bash
cd render-node
python -m pip install -e .
stagecanvas-render-node --node-id render-node-1 --label "Render Node 1"
```

Mock Unity bridge logs:

```bash
stagecanvas-render-node --node-id render-node-1 --label "Render Node 1" --bridge mock-unity
```

Periodic diagnostics logs (useful while debugging reconnection/command handling):

```bash
stagecanvas-render-node --node-id render-node-1 --label "Render Node 1" --log-state-every-sec 2
```

Bridge integration path:

- The renderer bridge interface lives in `app/bridge.py` and supports `load_show`, `play_at`, `pause`, `seek`, `stop`, and `ping`.
- Bridge exceptions propagate back into the node state (status flips to `ERROR` and the command history records the failure).

Bounded smoke run (auto-stop):

```bash
stagecanvas-render-node --node-id render-node-1 --max-runtime-sec 20 --log-state-every-sec 2
```

Runtime tuning flags:

- `--heartbeat-interval-sec` (default `1.0`)
- `--tick-interval-sec` (default `0.2`)
- `--ws-reconnect-initial-sec` (default `1.0`)
- `--ws-reconnect-max-sec` (default `8.0`)
- `--max-runtime-sec` (default `0`, disabled)
- `--diagnostics-file` (optional path; appends JSONL diagnostics snapshots)
- `--diagnostics-sample-every` (default `1`; emit one diagnostics sample per N intervals)
- `--warn-rate-window-sec` (default `30`; warning rate-limit window per event key)
- `--warn-rate-burst` (default `3`; max warnings per event key per window before suppression)

## Run Two Nodes (sync test)

Terminal A:

```bash
stagecanvas-render-node --node-id render-node-1 --label "Render Node 1"
```

Terminal B:

```bash
stagecanvas-render-node --node-id render-node-2 --label "Render Node 2"
```

Then use the control UI `PLAY_AT (+3s)` action to verify both nodes enter `PLAYING` together.

## Run Tests

```bash
python -m unittest discover -s render-node/tests -p 'test_*.py'
```

From repo root:

```bash
make render-test
make render-compile
make render-smoke
```

## Notes

- This agent is the control/runtime layer for the future Unity renderer integration.
- Unity output/mapping can now plug into `app/bridge.py` without changing orchestration protocol flow.
- Agent retries node registration with backoff and keeps connection/error diagnostics internally.
- Agent ignores malformed WS JSON frames and unsupported/invalid commands without crashing loops.
- Diagnostics output includes heartbeat counters, reconnect attempts, and command history stats.
- Log stream policy: info logs go to stdout; warn/error logs go to stderr.
- Repeated warning events are rate-limited with summary lines to reduce log flooding.
- `LOAD_SHOW` with `preload_only=true` updates node cache contract fields in heartbeat/diagnostics for orchestration monitoring.
- Playback stub emits frame counts during `PLAYING` and resets on `STOP`.
- `make render-smoke` runs a bounded end-to-end node session against local orchestration and validates diagnostics output.
- Cache index stub tracks assets with LRU eviction (`app/state.py`).
- Cache index is persisted to local JSON and restored on restart (`app/state.py`).
- Playback stub validates required assets are present in cache before `PLAY_AT`.
- Decoder stub is invoked on `LOAD_SHOW` and `PLAY_AT` to validate integration hooks (`app/bridge.py`).
