# Engineering workflow — develop AOF without breaking trust

*For humans and agents working in this repo. 2026-07-21.*

## Before any product change

1. Read `HISTORY_GOVERNANCE.md` (History Gate).
2. Read `ARCHITECTURE.md` (boundaries + identity rules).
3. Cite sources in the plan/PR: history index, decision records, ExecPlan if any.
4. No cite → no semantic change to gates.

## Default loop (every task)

```text
preflight (feature branch, bound cwd)
  → contract C (7 fields + DoD-cmd runnable)
  → implement smallest change
  → verify_gate (ruff | pytest) owned by orchestrator
  → audit_scope vs contract Scope
  → post_evidence OR session_log blocked
  → session_handoff (writes bundle + index)
```

CLI mirror: `aof doctor` → work → `aof log` → `aof handoff` → next session `aof resume`.

## Branch + commit

- Work on a **feature branch**, never long-lived direct `main` for product work
  (preflight warns on main/master by design).
- One concern per commit; message explains *why*.
- Do not force-delete `.git/index.lock` without checking holders (IDE/VM mounts).
- Never commit `.serena/`, `.DS_Store`, secrets, or host-only paths.

## Quality bar (local = CI intent)

```bash
ruff check core/ tests/
python -m pytest -q
# MCP catalog live (from repo root, PYTHONPATH=.)
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | PYTHONPATH=. python -m core.mcp_server
```

Regression rule: **do not lower test count to pass**. Every real bug becomes a permanent test.

## Self-improve loop (weekly, not every event)

1. Inputs: `op_log` (168h) + errors ledger (when F3 lands) + lease collisions.
2. Output: **exactly one** proposal (policy threshold, new test, doc gate).
3. Path: print proposal → `session_log needs_approval` → human/PR merge.
4. Stop-if: proposal requires Asana/cmux inside core → belongs in adapter.

## Multi-repo / worktree rules

- Register MCP with **absolute path** into this vendor repo, never bare
  `python -m core.mcp_server` from a parent workspace that still has a shadow `core/`.
- Handoff files live in the **bound repo** working tree; the global index lives under
  `$AOF_AUDIT_DIR` or `~/.aof/handoffs/`.

## What “done” means

| Kind of work | Done when |
|---|---|
| Bugfix | failing test first (or same PR), then green |
| Feature | ExecPlan acceptance + tests + ruff + doctor still honest |
| Docs | linked from `docs/INDEX.md`, no claim without measurable source |
| Release | CI green on 3.10–3.12, changelog, tag only with owner approval |

## Stop rules (agent)

- Any unexplained red test → stop, report.
- Second writer to append-only ledgers → stop, report.
- Urge to nourish a gate so CI passes → stop, report.
