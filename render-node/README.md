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
```

## Notes

- This agent is the control/runtime layer for the future Unity renderer integration.
- Unity output/mapping can now plug into `app/bridge.py` without changing orchestration protocol flow.
- Agent retries node registration with backoff and keeps connection/error diagnostics internally.
- Agent ignores malformed WS JSON frames and unsupported/invalid commands without crashing loops.
- Diagnostics output includes heartbeat counters, reconnect attempts, and command history stats.
- Log stream policy: info logs go to stdout; warn/error logs go to stderr.
