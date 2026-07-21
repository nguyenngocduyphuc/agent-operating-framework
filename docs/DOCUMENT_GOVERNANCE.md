# Document governance — production-grade docs for AOF

*Why this exists: architecture, workflow, and history were partial and easy to
drift (stale roadmaps, wrong COPY PROMPTs, tool counts hardcoding). Publish-ready
repos treat docs as product surfaces with owners and update rules.*

## Principles

1. **Single map** — `docs/INDEX.md` is the only entry directory. New durable doc → link it there the same PR.
2. **Truth over narrative** — numbers (test counts, tool counts, feature %) come from commands run in that PR, not memory.
3. **Decisions are files** — product pivots go to `docs/decisions/DR-YYYYMMDD-*.md`, not chat.
4. **Plans expire** — `docs/plans/*` is working memory. Mark STALE in the title when superseded; never leave a COPY PROMPT that contradicts `ARCHITECTURE.md`.
5. **VI for operators, EN for public API** — operator loops may be Vietnamese-first; architecture and README public claims need English parity before publish.
6. **No second home** — product truth lives in this repo. NP_AI private ops stay outside; distill pointers only (`history/INDEX.md`).

## Doc classes

| Class | Location | Lifecycle |
|---|---|---|
| Canon (law) | `HISTORY_GOVERNANCE.md`, `ARCHITECTURE.md`, `DOCUMENT_GOVERNANCE.md`, `ENGINEERING_WORKFLOW.md` | Change only with History Gate cite |
| Product | `PRODUCT_DIRECTION_*.md`, `REWIRE_MAP_*.md`, `ASSESSMENT_*.md` | Versioned by date or version tag |
| Operator | `QUICKSTART_VI.md`, `OPERATOR_WORKFLOW_VI.md`, `VONG_LAP_NO_CODE_VI.md` | Update when CLI/MCP UX changes |
| Working plans | `docs/plans/` | ExecPlan → implement → archive/stale |
| Sessions | `<repo>/docs/sessions/` (generated) | Machine-written; do not hand-edit as source of truth |
| Decisions | `docs/decisions/` | Append-only records |

## Update rules (checklist for authors/agents)

When you change behavior in `core/`:

- [ ] Operator docs still match command names and outcomes
- [ ] `ARCHITECTURE.md` boundaries still true (or updated in same PR)
- [ ] `docs/INDEX.md` structure blurb not lying (tool counts: say “see TOOLS catalog”, not a stale integer)
- [ ] Any `docs/plans/*` COPY PROMPT that taught the old behavior is fixed or marked STALE
- [ ] CHANGELOG entry if user-visible

When you write a plan for agents:

- [ ] Prefer linking `ARCHITECTURE.md` over pasting long architecture prose
- [ ] COPY PROMPT must match code that already shipped if the task is marked DONE
- [ ] Acceptance criteria are commands, not vibes

## Stale and wrong docs — duty to fix

If you discover a doc that would cause an agent to reintroduce a fixed bug
(example: teaching `repo_identity()` as a write base for sessions), you **must**
fix or STALE-mark it in the same session as the discovery. Leaving landmines is
a governance failure equal to shipping the bug.

## Ownership

| Surface | Owner default |
|---|---|
| Canon + architecture | repo maintainer (CEO / release captain) |
| Plans during a wave | executing agent, reviewed at phase gate |
| Session handoffs | machine (`session_handoff` / `aof handoff`) |
| Publish README claims | maintainer only at release |

## Related

- History Gate laws: `HISTORY_GOVERNANCE.md`
- Plan review format: `PLAN_REVIEW_STANDARD.md` (when using roadmap architect skill)
