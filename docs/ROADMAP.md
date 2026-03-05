# StageCanvas Roadmap

## Phase 0: Foundation (1-2 weeks)

- Define protocol messages and versioning rules
- Create monorepo structure and CI checks
- Implement local dev bootstrap for UI + orchestration

Deliverable:

- Running UI + server with mocked nodes and live heartbeat panel

## Phase 1: MVP Playback (3-6 weeks)

- Build render-node command receiver
- Implement show state machine
- Add `PLAY_AT`, `PAUSE`, `SEEK`, `STOP`
- Add basic media preload + local cache
- Implement 2-node software sync validation

Deliverable:

- Two render nodes playing synchronized timeline content from one operator UI

## Phase 2: Mapping + Reliability (4-8 weeks)

- Warp mesh + edge blend pipeline
- Node reconnect/recovery behavior
- Redundant command retries and idempotency
- Monitoring panel with drift/frame-drop alerts

Deliverable:

- Stable small-venue multi-projector deployment profile

## Phase 3: Production Features (ongoing)

- Advanced timeline editor
- Sensor triggers (OSC/HTTP/vision events)
- AI-assisted cue logic
- PTP and genlock integration path

Deliverable:

- Production-ready hybrid platform for installations/tours

## Cross-Cutting Technical Milestones

1. Protocol stability:
`shared-protocol` reaches `v1` with backward compatibility guarantees.

2. Determinism budget:
Define and enforce drift/error SLOs for playback synchronization.

3. Observability:
Every node emits metrics and structured logs with trace IDs.

4. Installability:
One-command local bootstrap for staging environments.

