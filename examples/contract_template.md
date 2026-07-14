# Execution Contract Template

Every task is a contract. Fill in the fields below before starting work.

```markdown
Task:    <one sentence describing the single task>
Owner:   <the agent, role, or lane that owns this task>
Scope:   <exact paths, directories, or systems. Be specific — "lib/parse.py"
         not "the parser module". State what IS in scope, not what is not.>
DoD:     <verifiable completion criteria. Examples: "all tests pass with
         python -m pytest tests/ -x -q", "ruff check exits 0", "1 new
         endpoint at POST /api/reports". Each criterion is a command or
         a concrete observable.>
Do not:  <3-5 forbidden actions. Examples: "do not touch files outside
         lib/", "do not deploy to production", "do not commit or push",
         "do not read credentials from env", "do not install new deps">
Stop if: <conditions that force immediate stop. Examples: "scope includes
         a file outside this repo", "the fix needs a decision from the
         project lead", "a pre-existing bug unrelated to this task is
         found". When this fires, return a blocker — do not self-expand.>
Return:  <what the owner produces: diff summary + gate results + evidence
         URL or blocker reason + next owner.>
References: <links to relevant docs, KB entries, research reports. Write
         "none (trivial)" if not applicable.>
```

## Field explanation

- **Task**: One task, one sentence. If you need "and", split into two tasks.
- **Owner**: Exactly one. If work spans multiple lanes, the orchestrator
  owns the decomposition.
- **Scope**: Boundaries that define where work happens. Explicit is better
  than implicit.
- **DoD**: Must be verifiable without subjective judgment. Prefer commands
  over prose.
- **Do not**: Prevents common overreach. Updated from past mistakes.
- **Stop if**: The escape hatch. Without it, agents self-expand scope.
- **Return**: What the consumer of this contract receives.
