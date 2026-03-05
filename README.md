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

Multi-agent collaboration:

- `docs/MULTI_AGENT_WORKFLOW.md` for branch ownership, handoff, and merge process.
- `docs/AGENT_SYNC_PACKET.md` for a paste-ready packet to align parallel chats.
- `scripts/dev-sanity.sh` for shared startup sanity checks and error logs in `.sanity-logs/`.
- `make sanity` as the standard pre-handoff check command for all agents.
