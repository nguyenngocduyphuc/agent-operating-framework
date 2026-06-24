# OPERATING PROTOCOL — template for your workspace
> Copy to your project root and customize. Point config.json → operating_protocol_path here.

## Execution loop (every task)
```
preflight → check_contract → branch → plan → work → audit_scope → verify_gate → post_evidence → Done|Blocked
```

## EXECUTION CONTRACT (every task brief must include)
```
Task:    <one sentence — what specifically must be done>
Owner:   <single agent — exactly one>
Scope:   <exact files/dirs/systems allowed — nothing outside this>
DoD:     <verifiable done criteria — tests pass, gate clean, evidence posted>
Do not:  <3 forbidden actions — e.g. push to main, edit outside Scope, deploy>
Stop if: <conditions that force immediate stop>
Return:  <exact output shape — evidence + blocker + next owner>
```

## Hard rules
1. One task · one owner · one scope · one DoD · one stop condition. No bundling.
2. `Stop if` fires → STOP immediately. Return a blocker with `next owner`.
3. Out of scope = blocker, not a side-quest. Never self-expand.
4. `post_evidence` is mandatory before marking Done or Blocked.

## Orchestrator-only actions (workers cannot do these)
- git commit / push
- deploy / publish
- external API writes (Asana, Slack, etc.)
- infrastructure changes

## Quality gates (run before Done)
- `verify_gate(ruff)` — linting clean
- `verify_gate(pytest)` — all tests pass
- `audit_scope` — no files touched outside contract Scope
