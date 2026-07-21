# Effectiveness smoke — WITH AOF vs WITHOUT AOF (2026-07-21)

## Honesty bound

This is a **mechanism smoke** on three failure modes AOF is designed to
prevent. It is **not** a multi-agent ROI bench and must not be cited as an
n≥30 causal result (see CAUSAL-VERDICT / AOF-Bench plans for that class).

Re-run anytime:

```bash
cd vendors/agent-operating-framework
PYTHONPATH=. python3 scripts/effectiveness_ab_smoke.py
```

## Result (this session)

| Failure mode | WITHOUT AOF | WITH AOF |
|---|---|---|
| Handoff written to parent workspace, not the repo being worked | **Fails safety** (writes wrong place) | **Passes** (nearest_repo + docs/sessions) |
| “Close” error without permanent test_ref | **Fails safety** (silent close allowed) | **Passes** (refused until test_ref) |
| Two live sessions on same task | **Fails safety** (both proceed) | **Passes** (lease conflict) |

**Verdict:** `effectiveness_smoke_pass: true` (script exit 0).

## What this does / does not prove

| Proves | Does not prove |
|---|---|
| Gates fire on the failure modes above | Better product quality for arbitrary coding tasks |
| Naive path exhibits the bugs AOF blocks | Statistical ROI / wall-time tradeoff |
| Regression suite (153 tests) + this smoke still green | Public “n≥30” marketing claims |

## Broader verification already in-repo

- `python -m pytest -q` — unit + adversarial + E2E user journey
- CI matrix 3.10–3.12 (ruff full `core/ tests/` + pytest + tools/list)
- History: ASSESSMENT_20260721.md, ALIGNMENT_WITH_HISTORY, lease/policy incident tests
