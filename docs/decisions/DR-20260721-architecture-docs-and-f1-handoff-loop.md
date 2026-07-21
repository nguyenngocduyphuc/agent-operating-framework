# DR-20260721 — Architecture/docs governance + F1 handoff loop

## Context

CEO approved full authority to harden AOF toward a 90-day public release.
Audit found: strong enforcement core, weak production docs (no architecture
map, wrong CONTRIBUTING template, stale plan COPY PROMPTs that could reintroduce
bugs), and incomplete v0.4 handoff loop (bundle + correct write root done;
index + resume missing).

## Decisions

1. **Canon docs** live in-repo: `ARCHITECTURE.md`, `ENGINEERING_WORKFLOW.md`,
   `DOCUMENT_GOVERNANCE.md`; `CONTRIBUTING.md` is AOF-specific.
2. **Write base** for sessions = `nearest_repo(cwd)`; **index/lease keys** =
   `repo_identity(cwd)`. Never swap the two.
3. **Host index** = `$AOF_AUDIT_DIR/handoffs/index.jsonl` (default `~/.aof/...`),
   one writer (`append_handoff_index`), append-only.
4. **Resume** = CLI `aof resume` + MCP tool `aof_resume` (13th tool), never gated.
5. **Self-improve** (later F3-4) proposes only; no auto-merge policy; no Asana in core.

## Consequences

- Agents must fix landmine docs in the same session they discover them.
- Doctor tool counts remain dynamic against `TOOLS`.
- Next: F3 error ledger + improve-check; shadow `NP_AI_macos/core` retirement
  remains a host ops task outside this vendor commit.
