---
title: "[P0] Canonical grounding gates: quality and scope"
owner: "Pham Duc Phuong Nam"
due_on: "2026-07-19"
project: "P15"
route_key: "p15_app_factory"
---

# AOF P0 canonical grounding remediation

## GOAL

Close the two P0 fabrication paths in the **canonical** AOF repository: an empty/weak quality gate and caller-controlled scope evidence.

## CONTEXT

The earlier hardening commit `83fc87c` exists only in the AntiGravity consumer repository. PR #7 is repository identity only and must not be treated as P0 grounding remediation.

## ACCEPTANCE CRITERIA

- `core/mcp_server.py` permits only allowlisted verification gates and cannot treat byte-compilation alone as a quality proof.
- Scope audit derives changed files from trusted Git state, including untracked files; caller claims cannot widen/narrow the evidence.
- `post_evidence` fails unless the trusted scope audit has passed for the bound task/workspace.
- Focused adversarial tests prove the prior bypasses fail closed in canonical AOF.
- Canonical PR is separate from PR #7; no merge/deploy.

## EXECUTION ORDER

1. Diff canonical `main` against consumer commit `83fc87c`; identify portable behavior, not blind-copy files.
2. Worker implements minimal canonical patch and tests under this worktree only.
3. Orchestrator independently runs focused tests, Ruff, and MCP smoke.
4. Push a distinct P0 branch and draft PR; request Claude/Genspark review.

## VERIFICATION COMMANDS

```bash
python -m pytest tests/test_adversarial.py tests/test_mcp_server.py -q
python -m ruff check core/mcp_server.py core/check_contract.py tests/test_adversarial.py
```

## STOP RULES

- Do not merge/deploy or modify PR #7.
- Do not copy consumer-only tracker/adapter behavior into portable AOF.
- If canonical and consumer protocol semantics differ such that a safe port needs public API design, stop and report the delta.

## EVIDENCE REQUIRED AT CLOSE

- Commit/PR URL plus changed-file list.
- Adversarial test matrix and full CI state.
- Explicit statement that PR #7 remains repository identity only.
