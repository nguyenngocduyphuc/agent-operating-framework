# EXECUTION CONTRACT — scope-lock per task

> Read this FIRST, before any implementation work. Overrides "feel productive."

## Contract fields (header required in task notes + handoff)

| Field | Description |
|-------|-------------|
| **Task** | Unique task identifier |
| **Owner** | Role or person responsible (e.g. "Orchestrator", "Worker", "${OWNER_ROLE}") |
| **Scope** | Exact boundaries — what IS included |
| **DoD** | Definition of Done — measurable completion criteria |
| **Do not** | Actions explicitly forbidden during this task |
| **Stop if** | Condition that triggers immediate STOP and blocker return |
| **Return** | What to return: evidence + blocker + next owner |

## Hard rules

1. **One task . one owner . one scope . one DoD . one stop condition.**
2. **Stop-if fires OR DoD met OR fix needs something outside Scope -> STOP and return a Blocker with next owner. NEVER self-expand scope to find side-work.**
3. **Out-of-scope need (theme/SSH, other repo, external owner, a decision) = blocker, not a side-quest.**
4. **Return: evidence + blocker + next owner. Done OR Blocked -- never silent expansion.**
5. **Worker self-check before each action: "Is this in Scope? Will this violate any Do-not?" If uncertain -> STOP.**

## Default Do-not for workers

Workers MUST NOT: publish, deploy, git commit/push, write to task tracker, modify credentials/secrets, or modify files outside their assigned scope. These are orchestrator-only actions.

## Continuous loop

```
plan -> task -> delegate -> verify -> stop-check -> ship -> evidence -> (repeat)
```

Every cycle produces evidence. No silent work.
