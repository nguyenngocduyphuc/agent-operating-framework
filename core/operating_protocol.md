# OPERATING PROTOCOL — GENERIC
> Mandatory for ALL agents (IDE + CLI) in this workspace.
> Scope: `${WORKSPACE_ROOT}`. Owner = `${OWNER_ROLE}`.

## FRAMEWORK STACK (optional tools — adapt per workspace)

1. **Task tracker** — every task tracked. Choose one: Asana, GitHub Issues, Linear, Jira, Trello.
2. **Token-efficient code nav (optional)** — e.g. Serena, symbols-based navigation instead of whole-file reads.
3. **Karpathy principles** — think-first, simplicity, surgical changes.
4. **Execution contract** — scope-lock per task (see `execution_contract.md`).
5. **Ponytail (optional)** — minimalism ladder: YAGNI -> stdlib -> native -> existing dep -> one line -> minimal code. Stop at the first rung that holds.
6. **Document ingestion (optional)** — e.g. markitdown for PDF/DOCX/HTML -> markdown.
7. **Human-agent harness (optional)** — collaboration model for review/approval gates.

## Three pillars

### 1. TASK TRACKER — every task is tracked (no silent work)
- Before non-trivial work: create/find the task; set **In Progress**; the brief/DoD lives in the task notes.
- After: post an evidence comment (what changed, links, gate result) and set **Done** / **Blocked**.
- Token for tracker API stored only in environment or private `.env`.

### 2. TOKEN DISCIPLINE (optional) — default for code/file work
- Navigate with symbols/search instead of reading whole files. Never paste large file bodies unnecessarily.

### 3. ORCHESTRATOR + WORKER — orchestrator plans, workers execute
- Main/orchestrator agent: **plan -> delegate -> verify -> ship**.
- Execution-heavy work (drafting, refactors, analysis) goes to a worker.
- **Orchestrator-only (workers FORBIDDEN):** publish, deploy, SSH, git commit/push, tracker writes, credential access.

## Execution contract (scope-lock)
Every task is a contract with: Task / Owner / Scope / DoD / Do not / Stop if / Return.
- One task . one owner . one scope . one DoD . one stop condition.
- Stop-if fires OR DoD met OR fix needs something outside Scope -> STOP and return a Blocker.
- Out-of-scope need = blocker, not a side-quest. Return: evidence + blocker + next owner.

## SOP — exact steps per task

```
0. PREFLIGHT   python3 -m core.preflight --task <id>    # repo+branch correct? exit 2 = fix first
1. CONTRACT    read the task's Task/Owner/Scope/DoD/Do-not/Stop-if/Return
2. BRANCH      git checkout -b fix/<id>-<slug>           # in the repo owning your CWD only
3. PLAN        orchestrator writes brief -> task In Progress
4. DELEGATE    dispatch worker with brief (per worker dispatch mechanism)
5. VERIFY      run the repo's gates/tests
6. STOP-CHECK  DoD met? out-of-scope need? -> STOP, return blocker+next owner
7. SHIP        orchestrator-only: publish/deploy/git commit+push/tracker write
8. EVIDENCE    tracker comment (what+links+gate) + handoff report -> Done|Blocked
```

## The continuous loop

```
plan -> task -> delegate -> verify -> stop-check -> ship -> evidence
```

All tasks tracked. All work produces evidence. No silent work.
