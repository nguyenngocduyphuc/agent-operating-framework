# Contributing to Agent Operating Framework

## Canonical repo

This directory (`vendors/agent-operating-framework` in a workspace, or the
standalone clone) is the **only** product tree. Do not edit shadow copies of
`core/` elsewhere on a machine.

## Required reading (in order)

1. `docs/HISTORY_GOVERNANCE.md` — History Gate
2. `docs/ARCHITECTURE.md` — layers and boundaries
3. `docs/ENGINEERING_WORKFLOW.md` — how to change code safely
4. `docs/DOCUMENT_GOVERNANCE.md` — how to change docs without drift

## Dev setup

```bash
cd /path/to/agent-operating-framework
python3 -m pip install -e ".[dev]"   # or: pip install pytest ruff && PYTHONPATH=.
ruff check core/ tests/
python3 -m pytest -q
```

Register MCP with an **absolute** path to this tree’s server entry (see
`aof doctor` output), not `python -m core.mcp_server` from a parent monorepo.

## Pull requests

- Feature branch off the active development branch
- Tests + ruff green
- User-visible changes noted in `CHANGELOG.md`
- No hardcoded MCP tool counts; doctor compares to `TOOLS` dynamically

## What we will reject

- Nudging fail-closed gates so a test turns green
- Putting tracker/cmux logic into `core/`
- Auto-applying self-improve proposals without human approval
- Docs claims that cannot be reproduced with a command in the PR
