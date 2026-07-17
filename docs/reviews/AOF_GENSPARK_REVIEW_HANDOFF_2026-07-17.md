# AOF Genspark closeout handoff — PR #7

**Date:** 2026-07-17  
**Owner:** Pham Duc Phuong Nam  
**Asana:** `1216654489388810`  
**Audience:** Genspark (external design/safety reviewer)  
**Status:** **External verdict PENDING** — do not invent APPROVE / REQUEST_CHANGES / BLOCKED

This file does **not** authorize merge, deploy, or Asana updates.

---

## 1. Context (one paragraph)

Two GitHub remotes exist and are **not** duplicate homes of the same product: **upstream/canonical** product AOF is `nguyenngocduyphuc/agent-operating-framework`; **consumer/integration** workspace is `nguyenngocduyphuc/AntiGravity-IDE-Upgrade` (local tree `NP_AI_macos` and worktrees). Product work must bind to the canonical origin; the consumer must not become a silent product remote. PR #7 ships a **local, opt-in** preflight gate (`expected_repository`) on the canonical repo only.

---

## 2. Chronology

| Stage | What happened |
|-------|----------------|
| **Discovery** | Preflight did not bind GitHub origin identity, so product-oriented fixes could pass preflight and be authored/pushed from the consumer remote (governance drift motivation). |
| **Canonical correction** | Implementation on branch `fix/ASANA-1216654071128493-repo-identity`: optional policy key + fail-closed origin match when set. |
| **PR #7** | Open on canonical repo: code commit `c0aa8e8`, later docs packet commit `145e9a0`. CI observed green. |
| **Review packet** | Single evidence-backed Genspark packet written (no merge, no consumer edit). |
| **Current state** | **Genspark external verdict is pending.** Level-1 GitHub ruleset `19085276` is active on the default branch; no merge, no deploy. |

---

## 3. Exact references (URLs + commits)

| Item | Value |
|------|--------|
| **PR #7** | https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7 |
| **PR state (observed)** | OPEN · base `main` · head `fix/ASANA-1216654071128493-repo-identity` |
| **Code commit** | `c0aa8e8718e85372f555cc9b6e911efddeeddd93` — `fix(preflight): bind canonical repository` |
| **Packet commit** | `145e9a0294e7dfef89cb641a8fa2e1af89bed0d2` — `docs(governance): add Genspark review packet` |
| **Canonical repo** | https://github.com/nguyenngocduyphuc/agent-operating-framework |
| **Consumer repo** | https://github.com/nguyenngocduyphuc/AntiGravity-IDE-Upgrade |
| **Review packet (this worktree)** | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/docs/reviews/AOF_REPOSITORY_GOVERNANCE_GENSPARK_REVIEW_2026-07-17.md` |
| **Closeout plan** | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/docs/plans/AOF_GOVERNANCE_CLOSEOUT_2026-07-17.md` |
| **Representative green CI run** | https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/runs/29553019321 |
| **DeepSeek research audit (limits only)** | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/07_deepseek_audit.md` |

Short SHAs for humans: **`c0aa8e8`**, **`145e9a0`**.

---

## 4. What was fixed · proof · intentionally not fixed

### Fixed (in PR #7)

- Policy key `expected_repository` in canonical `.aof_policy.json` → `nguyenngocduyphuc/agent-operating-framework`.
- Preflight gate in `core/preflight.py`: when set, fail closed (exit **2**) on missing/empty/unparseable origin or `actual != expected`.
- Opt-out: missing / non-string / blank key → no identity blocker (adopter template uses `""`).
- Focused tests for SSH/HTTPS match, mismatch, missing origin, unparseable URL, opt-out, normalize helper.

### Test / CI proof

| Proof | Evidence |
|-------|----------|
| Local preflight tests | Packet reports `python3 -m pytest tests/test_preflight.py -q` → **10 passed** |
| Broader local suite (PR body) | `pytest tests/test_preflight.py tests/test_adversarial.py tests/test_mcp_server.py -q` → **29 passed** + ruff on changed files |
| Live CI | PR #7 checks observed **pass**; run https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/runs/29553019321 |
| CI coverage note | CI proves the gate does **not** false-block on the correct remote; it does **not** alone prove consumer clones without the key are blocked |

Local evidence paths:

- `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/core/preflight.py`
- `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/.aof_policy.json`
- `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/.aof_policy.example.json`
- `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/tests/test_preflight.py`
- `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/.github/workflows/aof.yml`

### Intentionally not fixed / not shipped in this PR

| Item | Why |
|------|-----|
| GitHub rulesets / classic branch protection on `main` | Level-1 active ruleset `19085276`: pull-request-only, blocks deletion and non-fast-forward updates; zero required approvals to avoid single-maintainer lockout. |
| Mandatory approving reviewers | Single collaborator today → risk of self-lockout |
| Path-glob “protected upstream paths,” auto consumer-role inference | Out of PR #7 scope |
| Consumer remote / production deploy changes | Stop rule |
| Action SHA-pinning / token least-privilege CI hardening | Orthogonal hygiene; not this PR |
| Negative CI job with synthetic wrong origin | Recommended review question only |

---

## 5. Level-1 reviewer model

| Role | Responsibility |
|------|----------------|
| **Genspark (external)** | Design/safety **verdict only** using the packet + this handoff. Returns `APPROVE` \| `REQUEST_CHANGES` \| `BLOCKED` with evidence. **No merge authorization.** |
| **Owner (Pham Duc Phuong Nam)** | Sole human merge/reject decision on PR #7 after external verdict. |
| **GitHub required approval** | **Not required today** and must not be forced as a ruleset while only one collaborator exists (`nguyenngocduyphuc` admin per packet live read). A future second collaborator (or bot) is the unlock for mandatory reviews. |
| **Orchestrator** | PR is ready for review; active Level-1 non-locking ruleset has been read-back verified. Evidence is closed; it does not merge. |

**Level-1 protection applied:** require pull requests to `main`, block deletion, and block non-fast-forward updates; **do not** enable “require approving review” until multi-collaborator exists. AOF CI is green for PR #7, but is not yet a server-required check because the current workflow excludes docs-only PRs.

---

## 6. Genspark prompt + copyable verdict template

### Prompt (paste into Genspark)

```text
You are the external design/safety reviewer for AOF PR #7 (repository identity governance).

Read in order:
1) This handoff: docs/reviews/AOF_GENSPARK_REVIEW_HANDOFF_2026-07-17.md
2) Full packet: docs/reviews/AOF_REPOSITORY_GOVERNANCE_GENSPARK_REVIEW_2026-07-17.md
3) Implementation: core/preflight.py, .aof_policy.json, tests/test_preflight.py
4) Research hygiene only: DeepSeek audit path in the packet (confidence 75/100 — do not rubber-stamp unaudited NotebookLM figures)

Topology fact: agent-operating-framework = upstream product; AntiGravity-IDE-Upgrade / NP_AI_macos = consumer. Not dual product homes.

PR: https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7
Commits: c0aa8e8 (code), 145e9a0 (packet).

Challenge explicitly:
- normalize_github_owner_repo coverage (SSH aliases, insteadOf, enterprise hosts)
- .aof_policy.json placement vs consumer accidental inheritance
- safe consumer update path without wrong-remote ship
- smallest non-locking ruleset given one collaborator
- whether CI needs a synthetic wrong-origin negative job
- any claim beyond local code + tests + live GitHub must be re-sourced

Rules:
- Verdict is PENDING until YOU fill the template. Never invent a prior verdict.
- Your output is advisory only. You do NOT authorize merge, deploy, or Asana writes.
- Use only APPROVE | REQUEST_CHANGES | BLOCKED in the template below.
- Cite concrete evidence paths/URLs for every finding. No hallucinated CI, rulesets, or citations.
```

### Verdict response template (copy, fill, return)

```markdown
# Genspark verdict — AOF PR #7

**Reviewer:** Genspark  
**Date:** YYYY-MM-DD  
**PR:** https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7  
**Head commits reviewed:** c0aa8e8 (code), 145e9a0 (packet)  
**Verdict:** APPROVE | REQUEST_CHANGES | BLOCKED

## Summary (3–5 sentences)
<!-- What the change does, residual risk, why this verdict -->

## Evidence reviewed
- [ ] PR URL and commits c0aa8e8 / 145e9a0
- [ ] core/preflight.py + .aof_policy.json + tests/test_preflight.py
- [ ] Packet: docs/reviews/AOF_REPOSITORY_GOVERNANCE_GENSPARK_REVIEW_2026-07-17.md
- [ ] CI run(s): <URL>
- [ ] Research audit limits acknowledged (no unaudited figures as fact)

## Findings
| ID | Severity (blocker / major / minor / note) | Finding | Evidence (path or URL) | Required action if not APPROVE |
|----|-------------------------------------------|---------|------------------------|--------------------------------|
| F1 | | | | |

## Answers to packet questions (§6)
1. Parsing correctness / coverage:
2. Policy placement:
3. Consumer update path:
4. Safe ruleset proposal (no single-collaborator lockout):
5. CI gap (negative wrong-origin job?):
6. Research hygiene:

## Explicit non-authorizations
- This verdict does **not** merge PR #7.
- This verdict does **not** deploy or change consumer remotes.
- This verdict does **not** apply or modify GitHub rulesets.
- Final merge/reject remains with owner: Pham Duc Phuong Nam.

## If REQUEST_CHANGES or BLOCKED
**Minimum changes before re-review:**
1.
2.
```

---

## 7. Explicit current state

| Item | State |
|------|--------|
| **Genspark / external verdict** | **PENDING** — not invented, not implied by CI green |
| **PR #7 merge** | **Not authorized** by this handoff |
| **Deploy / consumer remotes** | **Not in scope** |
| **Level-1 ruleset applied?** | **Yes** — GitHub ruleset `19085276`, read-back verified active on the default branch |
| **Mandatory GitHub approving reviews** | **Not appropriate yet** (single collaborator lockout risk) |
| **Next owner** | Genspark fills verdict template → Pham Duc Phuong Nam decides merge |

**Stop line:** Until Genspark returns a filled template, treat review outcome as **unknown**. CI green is necessary evidence, not merge permission.

---

**End of handoff.**  
Next: Genspark verdict → owner merge decision. No orchestrator merge action is authorized.
