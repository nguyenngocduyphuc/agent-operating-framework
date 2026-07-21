# Clean-machine audit — 2026-07-21

**Method:** clone public GitHub into `/tmp`, new venv, no monorepo, no local dirty tree.  
**HEAD:** `9f5aed1` (merge PR #17)

## Commands (repro)

```bash
git clone --depth 1 https://github.com/nguyenngocduyphuc/agent-operating-framework.git
cd agent-operating-framework
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
aof --version
aof init /tmp/myproj && aof doctor /tmp/myproj
pip install pytest ruff   # required until [project.optional-dependencies] dev ships
python -m pytest -q
ruff check core/ tests/
```

## Results

| Check | Result |
|---|---|
| `pip install -e .` | **OK** → `agent-operating-framework-0.3.0b1` |
| `aof --version` | **0.3.0b1** |
| `aof init` + `aof doctor` (empty project) | **✅ SẴN SÀNG** — all 6 probes ok, MCP handshake ok |
| MCP `tools/list` | **14 tools** including `estate_report` |
| `require_karpathy` default (no policy file) | **True** |
| `pytest` after `pip install pytest` | **163 passed** |
| `ruff check core/ tests/` | **clean** |
| `pip install -e ".[dev]"` | **WARN** — extra `dev` **missing** (fixed in follow-up PR) |
| PyPI install without clone | **N/A** — not published |
| Git tag matches version | **No** — only historic `v0.2-beta` |

## Publish-ready re-score (after clean audit)

| Lens | Before (monorepo bias) | After clean audit |
|---|---:|---:|
| Stranger can install from clone | ~5 | **7.0** |
| Doctor/MCP work out of box | ~6 | **8.0** |
| Dev test path without monorepo | ~4 | **5.5** (needs pytest install) |
| PyPI one-liner | 2 | **2** (unchanged) |
| **Overall publish-ready** | **4.5** | **5.3** |

Clean install is **better than feared**: doctor green + 14 tools + tests pass.  
Still **not** “pip install from PyPI and go”.

## Gaps ranked (impact × effort)

1. **`[project.optional-dependencies] dev`** — one-liner tests  
2. **README tools list stale** (says subset, not 14)  
3. **Tag `v0.3.0b1`** + CI badge  
4. **Dogfood** handoff/resume (operational, not packaging)  
5. **TestPyPI**  

See `docs/plans/AOF_BEST_PATH_90D.md`.
