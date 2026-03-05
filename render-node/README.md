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

## Notes

- This agent is the control/runtime layer for the future Unity renderer integration.
- Unity output/mapping can now plug into `app/bridge.py` without changing orchestration protocol flow.
