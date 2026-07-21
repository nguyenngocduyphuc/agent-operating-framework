# Bypass map & Karpathy default

## Product rule

**Karpathy is ON by default.** The agent pays (Assumptions + DoD-cmd + bounded
Scope), not the no-code operator. Sources of truth:

- `aof init` / `doctor._DEFAULT_POLICY` → `require_karpathy: true`
- `load_policy()` defaults → `require_karpathy: true` (fixed 2026-07-21)
- `setup.sh` template → `require_karpathy: true` (fixed 2026-07-21)
- Legacy: `require_ponytail` aliases to `require_karpathy`

MCP: `check_contract` calls `validate(..., require_karpathy=bool(policy…))`.

## Bypass classes

| Class | Example | Mitigation |
|---|---|---|
| **A. Policy fail-open** | Missing key → False | Defaults True; init/setup write True |
| **B. Outside MCP** | Agent only uses bash/edit | Host skill + registration; not core |
| **C. Report-only path** | handoff without preflight | By design; evidence still gated |
| **D. Bootstrap forever** | `allow_bootstrap_without_task` | Re-preflight with task before work |
| **E. Unused loop** | handoff/resume/errors = 0 | Dogfood protocol (DOGFOOD_7DAY_VI) |

## What “hard mode” means in core

`verify_gate` / `audit_scope` / `post_evidence` require `preflight_ok` and
`contract_ok` in-session. There is **no** `enforcement_mode=advisory` switch in
core MCP (that lived in older NP_AI notes). If gates are not called, nothing
blocks the agent’s keyboard.

## Verify Karpathy is live

```bash
# 1) Policy default without file
python -c "from core.preflight import load_policy; print(load_policy('/tmp/no-policy-ws').get('require_karpathy'))"
# expect: True

# 2) Contract without Assumptions fails when Karpathy on
# (see tests/test_karpathy.py)
```
