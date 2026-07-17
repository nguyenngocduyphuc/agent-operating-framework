# AOF repository identity governance — Genspark review packet

**Date:** 2026-07-17  
**Owner:** Pham Duc Phuong Nam  
**Asana (packet task):** `1216654453009522`  
**Asana (implementation):** `1216654071128493`  
**Audience:** Genspark external design/safety review  
**Decision needed:** Human merge/reject of PR #7 — **this packet does not authorize merge or deploy**

---

## 1. Executive verdict

| Kind | Statement |
|------|-----------|
| **Fact** | Two GitHub repositories exist with distinct remotes: product AOF at `nguyenngocduyphuc/agent-operating-framework`, and consumer workspace `nguyenngocduyphuc/AntiGravity-IDE-Upgrade` (local tree `NP_AI_macos`). |
| **Verdict** | **Two-repo topology is the correct architecture** (upstream reusable product vs consumer/integration workspace). It is not an accidental dual-home of the same product. |
| **Prior drift (fact)** | Preflight did not bind GitHub origin identity. Product-oriented fixes could pass preflight and be authored/pushed from the consumer remote. Governance goal notes a P0 fix landed on the consumer for that reason. |
| **Shipped control (fact)** | PR #7 adds an **opt-in local** policy key `expected_repository` and fails closed when origin does not match. |
| **Safety to merge** | **Not a packet decision.** Local design is small, tested, and CI-green; server-side branch rules are intentionally unshipped (see §5). **Human reviewer must decide merge.** |

**Label guide used below:** **Fact** = observed in source, tests, or live GitHub API in this review window. **Inference** = reasoned from facts. **Recommendation** = optional next step; not applied here.

---

## 2. Topology and canonical PR

```text
                    ┌─────────────────────────────────────────┐
                    │  UPSTREAM / CANONICAL (product)         │
                    │  nguyenngocduyphuc/                     │
                    │    agent-operating-framework            │
                    │  Role: reusable AOF kernel + policy     │
                    │  PR #7 binds origin identity            │
                    └──────────────────┬──────────────────────┘
                                       │
                    one-way product updates / copy / pin
                                       │
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │  CONSUMER / INTEGRATION                 │
                    │  nguyenngocduyphuc/AntiGravity-IDE-Upgrade│
                    │  Local: NP_AI_macos (+ worktrees)       │
                    │  Role: monorepo, benches, ops sites     │
                    │  Must NOT become silent product origin  │
                    └─────────────────────────────────────────┘
```

| Item | Value |
|------|--------|
| Canonical repository | https://github.com/nguyenngocduyphuc/agent-operating-framework |
| Canonical `owner/repo` | `nguyenngocduyphuc/agent-operating-framework` |
| Consumer repository | https://github.com/nguyenngocduyphuc/AntiGravity-IDE-Upgrade |
| Review PR | **https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7** |
| PR state (observed) | OPEN · base `main` · head `fix/ASANA-1216654071128493-repo-identity` |
| Head SHA (observed) | `c0aa8e8718e85372f555cc9b6e911efddeeddd93` |
| PR title | `fix(preflight): bind canonical repository` |

**Inference:** Keeping product identity on the canonical remote and treating AntiGravity as consumer reduces fork-drift and wrong-remote ship risk. Research synthesis on “upstream-first” / fork drift supports that separation as a governance pattern (see §4 for audit limits).

---

## 3. Shipped control (local only)

### 3.1 Policy

**Fact — canonical checkout policy** (`.aof_policy.json`):

```json
{
  "expected_repository": "nguyenngocduyphuc/agent-operating-framework"
}
```

**Fact — adopter template** (`.aof_policy.example.json`): key is present as empty string `""`, so identity check is **opt-out by default** for new workspaces.

### 3.2 Behavior (`core/preflight.py`)

| Behavior | Detail |
|----------|--------|
| Loader | `load_policy(ws)` merges `.aof_policy.json` (or `$AOF_POLICY_FILE`) into defaults. |
| Gate | `check_expected_repository(repo, expected)` after branch checks. |
| Opt-out | Missing, non-string, or blank `expected_repository` → no identity blocker. |
| Parse | `normalize_github_owner_repo` accepts: `git@github.com:o/r(.git)`, `https://[user@][www.]github.com/o/r(.git)`, `ssh://git@github.com/o/r(.git)`. |
| Fail-closed | Blocks when: no git repo; missing/empty origin; unparseable origin; `actual != expected`. Exit **2**. |
| Match | String equality on normalized `owner/repo`. |

**Not shipped (out of this PR):** path-glob “protected upstream paths,” automatic consumer-role inference, GitHub rulesets, required PR approvals, CODEOWNERS enforcement.

### 3.3 Tests (local evidence)

Command (re-run in this worktree):

```bash
python3 -m pytest tests/test_preflight.py -q
# ..........  10 passed
```

| Case | Expected |
|------|----------|
| SSH origin matches | clear (no identity blocker) |
| HTTPS origin matches | clear |
| Mismatch origin | status `blocked`, exit 2 |
| Missing origin | blocked |
| Unparseable origin (e.g. GitLab SSH URL) | blocked |
| Key absent / empty string | opt-out (no identity blocker) |
| Normalize helper | SSH / HTTPS / invalid |
| Linked worktree + human preflight smoke | still green |

PR body also reports full suite: `pytest tests/test_preflight.py tests/test_adversarial.py tests/test_mcp_server.py -q` → **29 passed**, plus ruff on changed files.

### 3.4 CI (live, observed 2026-07-17)

Workflow: `.github/workflows/aof.yml` — jobs `preflight`, `quality` (ruff), `demo`, `tests` on Python 3.10 / 3.11 / 3.12.

**Fact:** All PR #7 checks observed via `gh pr checks 7` concluded **pass** (duplicate rollups from push + pull_request events). Representative run:

- https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/runs/29553019321

**Coverage note (fact):** CI runs preflight and pytest inside the **canonical checkout**. It proves the gate does not false-block on the correct remote; it does **not** by itself prove agents cannot still edit a consumer clone without setting `expected_repository` there.

---

## 4. Research findings (source-backed only) + audit limitations

**Research artifacts (local):**

| Artifact | Path |
|----------|------|
| NotebookLM synthesis | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/04_notebooklm_report.md` |
| DeepSeek factual audit | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/07_deepseek_audit.md` |
| Stack summary | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/SUMMARY.md` |

**Topic:** GitHub upstream / consumer repository governance (best practices).

### 4.1 Findings that are directionally useful (treat as synthesis, not statute)

These themes appear in the NotebookLM catalog and are **conceptually relevant** to AOF’s split:

1. **Upstream-first / fork-drift risk** — long-lived divergent forks make security backports hard (synthesis cites OSPO-style contribution norms).  
2. **Centralized repository rulesets** — preferred over ad-hoc branch protection for consistent merge gates.  
3. **Least-privilege Actions tokens / SHA-pinning Actions** — supply-chain hardening for CI, orthogonal to origin binding but part of broader repo hygiene.  
4. **CODEOWNERS for sensitive paths** — review ownership for manifests/workflows.

### 4.2 Audit limitations (must not over-cite)

DeepSeek audit confidence: **75/100**. Assessment: many claims lack matching citation support; several **HIGH** overreaches (e.g. “impossible” upgrades, empty source `[14]`, unbacked ruleset-network extension, unbacked throughput figures).

**Packet rule:** Do **not** treat NotebookLM figures (e.g. litellm 9%/88%, ~137k ops/s) or dramatic attack narratives as verified. Use research for **pattern vocabulary** only; AOF merge safety rests on **local code + tests + live GitHub state**.

### 4.3 Mapping research → this PR (recommendation, not shipped)

| Research pattern | AOF today | Status |
|------------------|-----------|--------|
| Prevent wrong-repo product work | `expected_repository` local preflight | **Shipped in PR #7** |
| Server-side non-bypassable merge rules | Rulesets / branch protection | **Not applied** (see §5) |
| Upstream-first consumer sync discipline | Process/docs only | **Not automated here** |
| Action SHA pin / token least privilege | Workflow still uses `@v4` tags | **Out of PR #7 scope** |

---

## 5. Residual risks

| Risk | Kind | Evidence / note |
|------|------|-----------------|
| **No repository rulesets** | Fact | `GET .../rulesets` → `[]` for `agent-operating-framework`. |
| **No classic branch protection on `main`** | Fact | `GET .../branches/main/protection` → HTTP 404 “Branch not protected”. |
| **Single collaborator** | Fact | Collaborators API returned only `nguyenngocduyphuc` (admin). |
| **Mandatory review not applied** | Fact + intentional decision | Requiring 1+ approving reviewers with only one collaborator can **self-lock merges**. Plan/stop-rule: report rather than apply. |
| **Local-only control** | Inference | Agents or humans who skip preflight, or consumers without `expected_repository`, are not blocked by GitHub. |
| **Parser surface** | Fact | Non-GitHub hosts, unusual URL forms, and multi-remote setups beyond `origin` are unparseable/out of scope → block only when policy is set. |
| **Policy file location** | Fact | Policy is loaded from workspace root (or `AOF_POLICY_FILE`), not from package install path alone — wrong workspace root can load wrong policy. |
| **Research overclaim risk** | Fact (audit) | External memo is not a compliance certificate. |

**Recommendation (not applied):** After a second human reviewer or bot-account is available, consider a **minimal ruleset** (require PR to `main`, optional required status checks for the AOF workflow) **without** “require approving review” until multi-collaborator exists—or use owner bypass carefully documented.

---

## 6. Genspark review questions

Please challenge these explicitly:

1. **Parsing correctness / coverage**  
   Is `normalize_github_owner_repo` sufficient for real agent remotes (SSH aliases, `insteadOf`, enterprise hosts, `.git` suffixes, trailing paths)? Which additional forms should fail closed vs ignore?

2. **Policy placement**  
   Is workspace-root `.aof_policy.json` the right binding point vs package-local / env-only / signed config? Can a consumer monorepo accidentally inherit the product `expected_repository` value?

3. **Consumer update path**  
   What is the safe, repeatable path for AntiGravity (and future consumers) to take product updates from canonical AOF **without** reopening wrong-remote ship? Should consumers set a *different* `expected_repository` or leave the key empty?

4. **Safe ruleset proposal**  
   Given one admin collaborator today, what is the **smallest** GitHub ruleset that reduces force-push / direct-main risk without lockout? When (if ever) should required approvals be turned on?

5. **CI gap**  
   Should CI add a negative job (synthetic wrong origin) so mismatch-blocking is proven in Actions, not only local pytest?

6. **Research hygiene**  
   Any governance claim beyond this packet’s local evidence should be re-sourced; do not rubber-stamp the unaudited NotebookLM overreaches.

---

## 7. Stop-if / human decision gate

| Action | Status |
|--------|--------|
| Merge PR #7 | **STOP — human decision only** |
| Deploy / alter consumer production remotes | **STOP — out of scope** |
| Apply mandatory approving-review ruleset | **STOP — would risk single-collaborator lockout** |
| Expand to protected path globs / consumer enforcement | **STOP — separate task** |

**Exact decision for owner/reviewer:**

> Approve or reject merge of https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7 after Genspark review of design safety.  
> Do not treat CI green alone as authorization for server-side branch locks.

---

## 8. Evidence table

| Evidence | Absolute path or URL | What it shows |
|----------|----------------------|---------------|
| This packet | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/docs/reviews/AOF_REPOSITORY_GOVERNANCE_GENSPARK_REVIEW_2026-07-17.md` | Review-complete single file |
| Plan | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/docs/plans/ASANA-1216654453009522-genspark-governance-review.md` | Scope / stop rules |
| Preflight implementation | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/core/preflight.py` | Parse + gate |
| Canonical policy | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/.aof_policy.json` | `expected_repository` binding |
| Example policy | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/.aof_policy.example.json` | Opt-out default for adopters |
| Tests | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/tests/test_preflight.py` | Match / mismatch / opt-out matrix |
| CI workflow | `/Users/phuongnam/02.AI/.worktrees/aof-canonical-governance/.github/workflows/aof.yml` | Preflight + pytest jobs |
| Implementation report | `/tmp/aof-canonical-identity-minimal-report.md` | DoD for code change |
| Governance context | `/tmp/aof-repo-identity-governance-2026-07-17.md` | Drift motivation; two-repo intent |
| NotebookLM report | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/04_notebooklm_report.md` | Upstream/consumer best-practice synthesis |
| DeepSeek audit | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/07_deepseek_audit.md` | Citation/overreach flags; conf. 75 |
| Research SUMMARY | `/Users/phuongnam/02.AI/NP_AI_macos/artifacts/dispatch/research_1784259210108687000/SUMMARY.md` | Artifact index |
| PR #7 | https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7 | Open PR, head `c0aa8e8…` |
| Canonical repo | https://github.com/nguyenngocduyphuc/agent-operating-framework | Upstream product |
| Consumer repo | https://github.com/nguyenngocduyphuc/AntiGravity-IDE-Upgrade | Integration monorepo |
| Actions run (green) | https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/runs/29553019321 | CI SUCCESS for PR branch |

---

## 9. Packet integrity notes

- **No merge, deploy, consumer edit, ruleset change, or Asana write** was performed to produce this packet.  
- Live GitHub facts (PR state, checks, rulesets, branch protection, collaborator list) were read-only verified on **2026-07-17**. Re-check before merge if time has elapsed.  
- Claims about historical “P0 landed on consumer” come from local governance goal text (`/tmp/aof-repo-identity-governance-2026-07-17.md`), not re-proven commit archaeology in this packet.  
- Research is cited only as context; **audit limitations are binding** for external claim strength.

---

**End of packet. Next owner: human reviewer (Genspark + Pham Duc Phuong Nam) for merge decision on PR #7.**
