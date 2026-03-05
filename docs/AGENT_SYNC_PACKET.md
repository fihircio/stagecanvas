# Agent Sync Packet (Paste Into Other Chat)

Use this packet so all agents run the same quality bar.

```md
Project: StageCanvas
Repo root: /Users/fihiromar/Desktop/WORKS/20260306_STAGECANVAS/WIP

Operating rules:
1) Do not edit shared-protocol/messages.v1.json unless ticket says contract change approved.
2) Keep changes scoped to ticket files only.
3) Before handoff, run: make sanity
   - default ports: ORCH_PORT=18010, UI_PORT=13000
   - override if occupied: ORCH_PORT=<port> UI_PORT=<port> ./scripts/dev-sanity.sh
4) If sanity fails, attach:
   - .sanity-logs/report.txt
   - .sanity-logs/orchestration-dev.log
   - .sanity-logs/control-ui-dev.log
5) Handoff format is mandatory:

Summary:
Files touched:
Behavior change:
Contract impact: (none | additive | breaking)
Sanity gate result: (pass | fail)
Sanity artifacts: (.sanity-logs/...)
How to test:
Risks/assumptions:
Next ticket suggestion:

Current ticket:
- Ticket: <fill me>
- Scope: <fill me>
- Files allowed: <fill me>
- Out of scope: <fill me>
- Acceptance:
  - [ ] <fill me>
  - [ ] <fill me>
```

Optional quick commands:

```bash
# run sanity
make sanity

# inspect latest sanity report
cat .sanity-logs/report.txt
```
