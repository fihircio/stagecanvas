# StageCanvas

Hybrid media-server platform architecture inspired by WATCHOUT/WATCHPAX/WATCHNET:

- `control-ui/`: operator interface (Control Layer)
- `orchestration-server/`: coordination + scheduling (Orchestration Layer)
- `render-node/`: local playback/render output (Render Layer)
- `shared-protocol/`: cross-service message contracts
- `docs/`: architecture and roadmap

Start with the architecture docs in:

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/DETERMINISM.md`

Current executable milestone:

- Orchestration server + Control UI + Render node agent are wired end-to-end for:
  - node registration
  - heartbeats
  - `PLAY_AT`, `PAUSE`, `STOP` control flow
