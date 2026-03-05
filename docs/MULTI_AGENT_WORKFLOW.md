# Multi-Agent Workflow (StageCanvas)

## 1) Roles

- Lead Agent: owns integration, protocol contracts, merge order, and final acceptance.
- Feature Agent(s): own scoped implementation tickets only.
- Sanity Agent: runs the shared dev sanity gate and reports failures with logs.

In a two-chat setup, one chat can run both Lead + Sanity, while the other chat focuses on feature delivery.

## 2) Ownership Map

Lead-owned files (no edit without explicit approval):

- `shared-protocol/messages.v1.json`
- `docs/ARCHITECTURE.md`
- `docs/DETERMINISM.md`

Feature-owned areas (default):

- `control-ui/`
- `orchestration-server/`
- `render-node/`

## 3) Branch + Worktree Convention

- Main integration branch: `main`
- Ticket branches: `codex/<area>-<ticket>`

Example:

- `codex/ui-heartbeat-badge`
- `codex/server-playat-validation`

Use worktrees to isolate parallel work:

```bash
git worktree add ../WIP-agent-ui -b codex/ui-heartbeat-badge
git worktree add ../WIP-agent-server -b codex/server-playat-validation
```

## 4) Required Ticket Format

```md
Ticket: SC-0XX
Scope: <single outcome>
Owner: <lead | feature-agent>
Files allowed: <explicit paths>
Out of scope: <explicit paths>
Acceptance:
- [ ] behavior 1
- [ ] behavior 2
Checks:
- [ ] run shared sanity gate
Deliverable:
- [ ] branch + handoff note
```

## 5) Shared Sanity Gate (Subagent)

Run this before handoff or merge:

```bash
make sanity
```

What it does:

- installs/validates dependencies for `orchestration-server` and `control-ui`
- starts orchestration server in dev mode
- starts control UI in dev mode against local orchestration
- fails fast on startup errors and writes logs to `.sanity-logs/`

Default sanity ports:

- orchestration: `18010`
- control UI: `13000`

Override if needed:

```bash
ORCH_PORT=28010 UI_PORT=23000 ./scripts/dev-sanity.sh
```

Artifacts:

- `.sanity-logs/report.txt`
- `.sanity-logs/orchestration-dev.log`
- `.sanity-logs/control-ui-dev.log`

## 6) Merge Order

1. Protocol/contract changes (`shared-protocol`)
2. Orchestration changes
3. Render node and control-ui consumers

Do not merge cross-layer mega PRs.

## 7) Handoff Note (Required)

```md
Summary:
Files touched:
Behavior change:
Contract impact: (none | additive | breaking)
Sanity gate result: (pass | fail)
Sanity artifacts: (.sanity-logs/...)
How to test:
Risks/assumptions:
Next ticket suggestion:
```

## 8) Cadence

- Feature agent posts one handoff every 45-60 minutes or ticket completion.
- Lead agent rebases/merges and issues next scoped ticket.
- If both agents need the same file, stop and re-scope before coding.
