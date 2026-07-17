# Genspark / Claude technical review packet — AOF P0 grounding (PR #8)

**Audience:** Claude or Genspark technical reviewer  
**Asana task:** `1216654621860246`  
**Date:** 2026-07-17  
**Reviewer action requested:** produce a written verdict only (see template at end).  
**This packet does not claim a verdict and does not authorize merge.**

---

## 1. Identity — what this is and is not

| Item | Value |
|------|--------|
| **This change** | **PR #8** — **P0 grounding** of verification evidence in the **canonical** AOF repository |
| **PR title** | `fix(mcp): ground verification evidence` |
| **PR state (at packet time)** | DRAFT |
| **Branch** | `fix/ASANA-1216654621860246-aof-p0-grounding` |
| **Head commit** | `a5a332472580f5942c1a1b75ae1ebfc4012da1f6` (short: `a5a3324`) |
| **Commit subject** | `fix(mcp): ground verification evidence` |
| **Base (main tip at branch point)** | `d3d4ce9` — `feat: one-command setup + measured Results (#6)` |

**Unambiguous distinction from PR #7:**

- **PR #8** is the P0 work that grounds *quality-gate* and *scope-audit* evidence so agents cannot fabricate completion.
- **PR #7** is a **separate** change about **repository identity** (canonical-origin binding in preflight). Title: `fix(preflight): bind canonical repository`. Asana: `#1216654071128493`.
- **PR #7 is not evidence that P0 grounding is complete.** Do not treat CI green on PR #7, or any repo-identity tests, as proof that the two P0 fabrication holes below are closed.
- Do not restate or re-review the P1/repo-identity ruleset here except for this separation.

---

## 2. Prior P0 holes (why this PR exists)

Before commit `a5a3324` on canonical `main` (parent `d3d4ce9`), two fabrication paths existed in `core/mcp_server.py`:

### Hole A — Arbitrary / compileall-only “quality” proof

- Gate names were restricted in a set, but the **`quality` builtin was only**  
  `python -m compileall -q core`  
  (byte-compilation of `core/`). That is a weak / non-substantive quality signal: syntax-level compile success, not project lint or tests.
- Unknown gate names returned an error, but the historical path still allowed treating a trivial gate as “verification passed,” which agents could chain into `post_evidence`.
- **Risk:** an agent claims “quality gate passed” after a meaningless compileall (or similarly weak) run and posts completion evidence.

### Hole B — Caller-claimed scope

- `audit_scope` **required** caller-supplied `changed_files` and audited **only those paths** against contract scope globs.
- An adversarial or sloppy caller could pass an in-scope subset and **omit** out-of-scope or untracked work, so `scope_audit_ok` became true without reflecting Git truth.
- `post_evidence` required `scope_audit_ok` but did **not** bind that audit to the current task + workspace binding.
- **Risk:** fabricated “in scope” closeout while real dirty tree includes out-of-scope files.

These holes are exactly what the plan document calls the two P0 fabrication paths (empty/weak quality gate + caller-controlled scope evidence).

---

## 3. Exact PR #8 controls (what `a5a3324` does)

### 3.1 Files changed (commit `a5a3324`)

| Path | Role |
|------|------|
| `core/mcp_server.py` | Production controls (gates + git inventory + evidence binding) |
| `tests/test_adversarial.py` | Focused fail-closed / adversarial coverage |
| `docs/plans/AOF_P0_GROUNDING_CANONICAL_2026-07-17.md` | Canonical remediation plan (context only; not runtime) |

Stat: **+367 / −31** across 3 files.

### 3.2 Quality / verify_gate grounding

- Module-level **`ALLOWED_GATES = frozenset({"ruff", "pytest", "quality"})`**.
- Unknown gate names: **never execute** any command (`subprocess` not called); return `passed: false` with “not allowed”.
- Commands resolved only via **`_gate_commands`** → fixed argv lists; **`shell=False`**; gate type is never used as a shell command name.
- **`quality` is no longer compileall:**
  - Always: `python -m ruff check .` (+ optional `extra_args`)
  - Additionally: `python -m pytest -x tests` when `tests/` exists **and** not already under `PYTEST_CURRENT_TEST` (avoids re-entrant suite under pytest).
  - Explicit comment and tests: **never treat byte-compilation alone as quality evidence.**
- Workspace/cwd still must match preflight binding when bound.

### 3.3 Scope audit grounding

- `audit_scope` tool schema: **`changed_files` no longer required**; description states git-derived paths.
- Implementation **ignores caller `changed_files` as evidence** (`caller_changed_files_ignored: true`).
- Trusted inventory from **`_git_inventory(bound_cwd)`**:
  1. Confirm git work tree.
  2. Resolve **base ref** in order: `origin/HEAD`, `origin/main`, `origin/master`, `main`, `master`.
  3. If base found: `merge-base HEAD <base>` then committed diff `mb...HEAD` (fallback two-dot).
  4. Staged: `git diff --name-only --cached`
  5. Unstaged: `git diff --name-only`
  6. **Untracked (tracked inventory gap closed):** `git ls-files --others --exclude-standard`
  7. Paths normalized; return sorted unique set.
- Fail-closed on inventory failure: error `-32007`, clear `scope_audit_*`.
- Scope globs must match **contract-parsed** scope; mismatch → `-32006`.
- On pass: sets `scope_audit_ok`, **`scope_audit_task`**, **`scope_audit_cwd`** (realpath).

### 3.4 post_evidence binding

Before closeout, requires:

1. Preflight + contract OK  
2. `last_verify_status == "passed"`  
3. `scope_audit_ok`  
4. **`scope_audit_task` matches current `bound_task`** (when task bound)  
5. **`scope_audit_cwd` matches realpath of current `bound_cwd`**  
6. Existing cross-task `task_gid` check (`-32004`)

Stale or cross-workspace scope audit fails closed (`-32003`).

### 3.5 Threat-model boundary (read carefully)

**This PR is fail-closed *evidence grounding* for MCP session completion claims.**

It is **not**:

- general adversarial host security (kernel, container escape, compromised git binary),
- full multi-tenant isolation,
- proof against a malicious local user rewriting `.git` after audit,
- a substitute for CI policy or branch protection merge rules.

In scope: agents/tools cannot claim quality or scope using weak builtins or self-reported file lists; missing git truth fails closed. Out of scope: broader OS-level attack surface.

---

## 4. Tests and CI evidence

### 4.1 Local suite (this worktree / head `a5a3324`)

```text
25 tests collected
25 passed
```

Command:

```bash
python3 -m pytest tests/ -q
```

**Test inventory (25):**

| File | Tests |
|------|--------|
| `tests/test_adversarial.py` (19) | `test_invalid_policy_fails_closed`, `test_prose_contract_fails`, `test_valid_contract_passes`, `test_wrong_branch_blocks`, `test_matching_branch_passes`, `test_disallowed_gate_blocked`, `test_allowed_gate_checks_runtime`, **`test_quality_gate_not_compileall_only`**, `test_gate_cwd_outside_workspace_blocked`, `test_gate_cwd_mismatch_blocked`, `test_scope_mismatch_blocked`, **`test_caller_changed_files_cannot_hide_out_of_scope_git`**, **`test_git_inventory_includes_untracked`**, `test_new_preflight_resets_prior_gate_state`, `test_cross_task_evidence_blocked`, **`test_post_evidence_requires_bound_scope_audit`**, `test_evidence_needs_verify`, `test_evidence_needs_scope_audit`, `test_full_mcp_sequence_passes` |
| `tests/test_mcp_server.py` (4) | initialize / tools_list / one tools_call / full oneshot |
| `tests/test_preflight.py` (2) | linked worktree `.git` file; human preflight no crash |

P0-focused new/strengthened adversarial cases (names bolded above) directly target Hole A and Hole B.

### 4.2 GitHub CI matrix (workflow)

Absolute path:

`/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/.github/workflows/aof.yml`

Matrix: **Python 3.10, 3.11, 3.12** on jobs:

- Preflight gate  
- Code quality (ruff)  
- Demo smoke-test  
- Regression tests (pytest) → `python -m pytest tests/ -q`

At packet time, `gh pr checks 8` reported **pass** for matrix jobs (duplicate check rows may appear from multiple workflow runs). Example Actions run URLs:

- https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/runs/29556153126  
- https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/runs/29556128525  

---

## 5. Absolute evidence paths and URLs

### Local (absolute)

| Artifact | Absolute path |
|----------|----------------|
| Worktree root | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding` |
| MCP implementation | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/core/mcp_server.py` |
| Adversarial tests | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/tests/test_adversarial.py` |
| MCP tests | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/tests/test_mcp_server.py` |
| Preflight tests | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/tests/test_preflight.py` |
| CI workflow | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/.github/workflows/aof.yml` |
| Canonical plan | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/docs/plans/AOF_P0_GROUNDING_CANONICAL_2026-07-17.md` |
| **This review packet** | `/Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding/docs/reviews/AOF_P0_GROUNDING_GENSPARK_REVIEW_2026-07-17.md` |

### Remote

| Artifact | URL |
|----------|-----|
| **PR #8 (this P0)** | https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/8 |
| Commit `a5a3324` | https://github.com/nguyenngocduyphuc/agent-operating-framework/commit/a5a332472580f5942c1a1b75ae1ebfc4012da1f6 |
| Compare branch | https://github.com/nguyenngocduyphuc/agent-operating-framework/compare/main...fix/ASANA-1216654621860246-aof-p0-grounding |
| **PR #7 (repo identity only — not P0 completion)** | https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/7 |
| Canonical repo | https://github.com/nguyenngocduyphuc/agent-operating-framework |
| Asana task (P0) | GID `1216654621860246` |

Inspect commit:

```bash
cd /Users/phuongnam/02.AI/.worktrees/aof-p0-canonical-grounding
git show a5a332472580f5942c1a1b75ae1ebfc4012da1f6 --stat
git show a5a332472580f5942c1a1b75ae1ebfc4012da1f6 -- core/mcp_server.py tests/test_adversarial.py
```

---

## 6. Concrete reviewer questions

Answer each with **evidence** (file + behavior + test name). Prefer fail-closed over convenience.

### Git inventory semantics

1. Does `_git_inventory` cover all change classes that matter for scope evidence (committed-since-base, staged, unstaged, untracked), and is the set semantics correct (union, not last-writer-wins)?
2. Path normalization: are `./`, backslashes, and empty lines handled so glob matching cannot be bypassed by path spelling?
3. When git commands fail mid-inventory, is the failure always fail-closed (no partial success used as `scope_audit_ok`)?

### Base-ref edge cases

4. Base ref order is `origin/HEAD` → `origin/main` → `origin/master` → `main` → `master`. Is that correct for linked worktrees, shallow clones, and default-branch renames?
5. If **no** base ref verifies, inventory still includes staged/unstaged/untracked — is omitting committed-vs-base intentionally safe for this threat model?
6. Three-dot vs two-dot fallback after merge-base: any cases where wrong parent set understates or overstates scope?

### Untracked paths

7. Confirm untracked files from `ls-files --others --exclude-standard` **cannot** be hidden by caller `changed_files` (see `test_caller_changed_files_cannot_hide_out_of_scope_git`, `test_git_inventory_includes_untracked`).
8. Are ignored paths (`.gitignore`) correctly out of inventory? Is that desired for evidence grounding?

### Quality portability

9. Replacing compileall with `ruff` (+ optional pytest) is stronger but **requires ruff installed**. Is that acceptable for portable AOF consumers that only had stdlib before?
10. Under `PYTEST_CURRENT_TEST`, quality skips nested pytest — does that weaken evidence when the only gate run is `quality` from inside a test harness vs production MCP?
11. Confirm unknown gates never reach `subprocess` (see `test_disallowed_gate_blocked`, `test_quality_gate_not_compileall_only`).

### Scope binding

12. Can `post_evidence` succeed if `scope_audit_ok` is true but `scope_audit_task` / `scope_audit_cwd` are stale or from another workspace? (`test_post_evidence_requires_bound_scope_audit`)
13. Does preflight / check_contract correctly clear scope audit bindings so a prior pass cannot leak across sessions?

### Compatibility

14. Callers that still send `changed_files` (old required field): ignored safely, not rejected in a way that breaks honest clients?
15. Tool schema change (`changed_files` optional): any MCP client codegen breakage?
16. Does this PR stay free of consumer-only AntiGravity tracker/adapter behavior (plan stop rule)?

---

## 7. Reviewer verdict template (copy/paste)

Fill this block. **Do not merge.** This packet authorizes **review opinion only**.

```markdown
## Verdict — PR #8 P0 grounding (`a5a3324`)

**Decision:** APPROVE | REQUEST_CHANGES | BLOCKED

**Reviewed commit:** a5a332472580f5942c1a1b75ae1ebfc4012da1f6  
**PR:** https://github.com/nguyenngocduyphuc/agent-operating-framework/pull/8  
**Asana:** 1216654621860246  
**Date / reviewer:** YYYY-MM-DD / <name or agent>

### Distinction check
- [ ] I treated this as **P0 grounding only**.
- [ ] I did **not** count PR #7 (repo identity) as evidence of P0 completion.

### Hole closure (evidence)
| Prior hole | Closed? (Y/N/Partial) | Evidence (test / code path) |
|------------|------------------------|-----------------------------|
| A: arbitrary / compileall-only quality | | |
| B: caller-claimed scope | | |

### Answers to critical questions (brief)
- Git inventory: …
- Base-ref edge cases: …
- Untracked: …
- Quality portability: …
- Scope binding: …
- Compatibility: …

### Findings (if REQUEST_CHANGES or BLOCKED)
1. **[severity]** … — path/line — suggested fix …

### Explicit non-authorization
- [ ] I am **not** authorizing merge, deploy, or Asana closeout.
- [ ] Threat model understood: fail-closed evidence grounding, **not** general adversarial host security.

### Evidence consulted
- Local paths / commit / CI run URLs:
```

**Decision meanings:**

| Decision | Meaning |
|----------|---------|
| **APPROVE** | Holes A/B closed for stated threat model; residual risks acceptable; still **no merge authority** from this review alone. |
| **REQUEST_CHANGES** | Specific grounding defects; list required fixes with evidence. |
| **BLOCKED** | Unsafe to proceed until a named blocker is resolved (e.g. base-ref semantics wrong, tests miss hole, compatibility break). |

---

## 8. Out of scope for this review packet

- Implementing code fixes  
- Editing the plan file  
- Merging PR #8 or PR #7  
- Deploy, Asana status writes, git push, or CI configuration changes  
- Restating full P1 repository-identity policy beyond the PR #7 distinction  

**Next owner after this packet:** Genspark/Claude reviewer fills the verdict template; human maintainer decides merge under normal process.
