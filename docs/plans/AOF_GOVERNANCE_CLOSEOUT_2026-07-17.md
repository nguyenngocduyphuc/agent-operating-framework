---
title: "[GOV] AOF reviewer model, safe ruleset, and Genspark closeout"
owner: "Pham Duc Phuong Nam"
due_on: "2026-07-19"
project: "P15"
route_key: "p15_app_factory"
---

# AOF governance closeout

## GOAL

Make PR #7 ready for external Genspark review, apply a non-locking server-side protection baseline, and leave one complete handoff for the resulting human verdict.

## CONTEXT

The canonical AOF repository has one admin collaborator and no GitHub ruleset. PR #7 has green CI and must not be merged by the orchestrator.

## ACCEPTANCE CRITERIA

- PR #7 is ready for review but remains unmerged.
- A level-1 ruleset requires pull requests and blocks deletion/force-push without mandatory approval lockout. PR #7 must have green AOF CI before human review; making CI a repository-required check is deferred until the workflow also covers docs-only PRs.
- One Genspark handoff includes context, evidence, review questions, and a verdict response template.

## EXECUTION ORDER

1. Verify current PR, CI, collaborator, and ruleset state.
2. Create the Genspark handoff through a worker.
3. Mark PR ready for review; never self-approve or merge.
4. Apply and read-back verify the level-1 ruleset.
5. Commit/push only the handoff document and close evidence.

## VERIFICATION COMMANDS

```bash
gh pr view 7 --repo nguyenngocduyphuc/agent-operating-framework
gh api repos/nguyenngocduyphuc/agent-operating-framework/rulesets
gh pr checks 7 --repo nguyenngocduyphuc/agent-operating-framework
```

## STOP RULES

- Do not self-approve, merge, deploy, invite collaborators, or apply mandatory approving-review rules while only one collaborator exists.
- If GitHub rejects the non-locking ruleset schema, return the API evidence; do not weaken the intended PR/anti-force controls.

## EVIDENCE REQUIRED AT CLOSE

- Handoff path and PR URL.
- Ruleset ID and read-back configuration.
- CI state and explicit note that Genspark verdict is pending external review.
