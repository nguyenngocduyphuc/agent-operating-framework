# AOF Architecture — trust layer, not orchestrator

*Canonical mental model for contributors and agents. Updated 2026-07-21.*

## One sentence

AOF is a **portable operational trust layer** that fails closed before agent work
does damage: wrong repo, wrong branch, unscoped changes, self-graded DoD, silent
policy fail-open, session trampling. It is **not** a fleet orchestrator, not a
task tracker, and not a chat UI.

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Host / skill face  (/aof, Claude Code, Cowork, CLI `aof`)  │  language + UX
├─────────────────────────────────────────────────────────────┤
│  MCP server + CLI   (core/mcp_server.py, core/cli.py)       │  one catalog
├─────────────────────────────────────────────────────────────┤
│  Enforcement chain  preflight → contract → verify → scope   │  always on
│                     → evidence (+ lease, lanes, approval)   │
├─────────────────────────────────────────────────────────────┤
│  Host-side ledgers  ~/.aof (or $AOF_AUDIT_DIR):              │  append-only
│    audit.jsonl · decisions.jsonl · leases/ · handoffs/      │
├─────────────────────────────────────────────────────────────┤
│  Repo-side artifacts  <bound-repo>/docs/sessions/           │  next to code
│    HANDOFF_*.md + RECAP_*.html (same stamp)                 │
├─────────────────────────────────────────────────────────────┤
│  Adapters (out of core)  Asana, cmux, ceo_inbox, improve    │  NP_AI only
│    ledger tied to trackers — see REWIRE_MAP_AOF_SKILL.md    │
└─────────────────────────────────────────────────────────────┘
```

## Hard boundaries

| In core (portable) | Out of core (adapter) |
|---|---|
| preflight, contract, gates, lease, lanes | Asana write, cmux open |
| session_log, status_report, op_log | skill health, fleet |
| handoff/recap/index/resume | plan-gate inbox UI |
| propose_policy_change (read-only propose) | auto-merge improve_ledger |
| worker_watch by output mtime | worker process managers |

**Self-improve rule:** core may *propose* one policy change with evidence; it
must never write `.aof_policy.json` or open tracker tickets. Humans approve via
`session_log needs_approval` / PR.

## Identity: two paths, two jobs

| Function | Returns | Use for |
|---|---|---|
| `nearest_repo(cwd)` (`preflight`) | working-tree root (handles worktree `.git` file) | **Writing** `docs/sessions/` |
| `repo_identity(cwd)` (`lease`) | git common-dir realpath + short hash | **Leases + index keys** shared across worktrees |

Never use `repo_identity()[0]` as a file-write base — it is a `.git` directory.

## MCP tool surface

Catalog is the list `TOOLS` in `core/mcp_server.py`. Count is dynamic (`aof
doctor` compares live `tools/list` to `len(TOOLS)`). Do not hardcode tool counts
in docs or tests.

## Data flow — handoff (v0.4)

1. Session bounds via `preflight` → `bound_cwd` / `bound_task`.
2. `session_handoff` resolves write root with `nearest_repo(bound_cwd)`.
3. `write_session_bundle` writes pair `HANDOFF_<stamp>.md` + `RECAP_<stamp>.html`.
4. `append_handoff_index` appends one JSON line under `audit_dir()/handoffs/index.jsonl`.
5. Next session: `aof resume` / tool `aof_resume` reads index → RESUME BRIEF.

## Failure modes this architecture exists to prevent

- Shadow import of a stale `core/` on `sys.path` (History Gate law 2).
- Fail-open when policy key names change (legacy aliases).
- Two live sessions on one task (lease).
- Worker self-grading DoD (orchestrator owns verify_gate).
- Handoff written into parent workspace instead of the repo being worked.

## Related docs

- Product intent: `PRODUCT_DIRECTION_V03.md`
- History Gate: `HISTORY_GOVERNANCE.md`
- Skill cutover: `REWIRE_MAP_AOF_SKILL.md`
- Engineering loop: `ENGINEERING_WORKFLOW.md`
- Doc ownership: `DOCUMENT_GOVERNANCE.md`
