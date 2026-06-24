# agent-operating-framework

> MCP server that wires AI agents into a structured, evidence-backed execution loop.

Agents are powerful but drift. They skip contract validation, forget to post evidence, and silently expand scope. This MCP makes the right behavior the easy path — one tool call per step, structured JSON responses, tamper-evident audit trail.

## The execution loop

```
preflight → check_contract → work → audit_scope → verify_gate → post_evidence → Done|Blocked
```

Every step is a tool call. Every call is logged. Scope violations surface before they cost hours.

## Why it works

A real incident from the author's workspace:

> Agent received a task to fix a bug in `scripts/npflight.py`. Without scope enforcement, it "improved" adjacent code in 4 other files, broke two tests, and spent 40 minutes on work that wasn't asked for.

With `check_contract` + `audit_scope`, the scope would have been locked to one file before work began. `audit_scope` would have flagged the 4 extra files immediately.

## Tools (8)

| Tool | When to call | Returns |
|------|-------------|---------|
| `preflight(cwd, task)` | First, every session | `{status, checks[], blockers[]}` |
| `check_contract(brief)` | Before dispatching work | `{ok, missing[], decision_id}` |
| `operating_protocol()` | When you need the rules | Protocol text |
| `post_evidence(task_gid, summary, exit_code, artifacts, duration_s)` | When Done or Blocked | `{ok, story_gid}` |
| `verify_gate(gate_type, cwd, extra_args)` | Before marking Done | `{status, exit_code, output}` |
| `audit_scope(scope, changed_files)` | After editing files | `{ok, out_of_scope[]}` |
| `session_log(event, data)` | Key decision points | `{ok, logged}` |
| `query_audit(limit, tool, session_id)` | Debugging / analysis | `{entries[], summary}` |

## Install

```bash
git clone https://github.com/nguyenngocduyphuc/agent-operating-framework
cd agent-operating-framework
bash install.sh
```

To auto-register in an existing `.mcp.json`:
```bash
bash install.sh --mcp-json /path/to/.mcp.json
```

## Configuration

All optional. Works with zero config out of the box.

`~/.npflight/config.json`:

```json
{
  "workspace": "/path/to/your/project",
  "operating_protocol_path": "/path/to/OPERATING_PROTOCOL.md",
  "contract_fields": ["Task", "Owner", "Scope", "DoD", "Do not", "Stop if", "Return"],
  "env_checks": ["ASANA_TOKEN", "OPENAI_API_KEY"],
  "gates": {
    "ruff": ["ruff", "check", "."],
    "pytest": ["python", "-m", "pytest", "tests/", "-x", "-q"],
    "custom": ["make", "test"]
  }
}
```

See `examples/config.json` for the full reference.

## Manual MCP registration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "operating-framework": {
      "command": "python3",
      "args": ["/path/to/agent-operating-framework/src/npflight_mcp.py"],
      "env": {}
    }
  }
}
```

## Preflight checks (R1–R4+)

`preflight` runs these checks and returns machine-parseable JSON:

| Check | What it detects |
|-------|----------------|
| R1 git_repo | Agent is inside a git repository |
| R2 feature_branch | Not on `main` or `master` |
| R3 task_in_branch | Task id appears in branch name |
| R4 clean_shared_branch | No uncommitted changes on shared branches |
| R5+ configurable | Any env var in `config.env_checks` |

`status` is `clear`, `warn`, or `blocked`. Agents can act on individual check IDs.

## Audit trail

Every tool call is logged to `~/.npflight/audit.jsonl`:

```json
{
  "ts": "2026-06-24T10:30:45Z",
  "session_id": "a3f2c1b0",
  "tool": "check_contract",
  "args": {"brief_len": "412"},
  "result": "CONTRACT OK — all scope-lock fields present.",
  "duration_ms": 3
}
```

`session_id` correlates all calls in a session. Use `query_audit` to analyze patterns.

`check_contract` also writes to `~/.npflight/decisions.jsonl` — a tamper-evident record written **before** the tool returns, so the decision exists even if execution fails.

## `post_evidence` (Asana integration)

Set `ASANA_TOKEN` env var. Call with the Asana task GID:

```
post_evidence(
  task_gid="1234567890",
  summary="Fixed the scope drift bug. All 29 tests pass, ruff clean.",
  exit_code=0,
  artifacts=["tests/test_npflight_mcp.py"],
  duration_s=42
)
```

Posts a formatted comment to the Asana task. No external dependencies — uses Python `urllib`.

## Debug mode

Set `MCP_DEBUG=true` in env to include full Python tracebacks in error responses.

## Requirements

- Python 3.9+ (stdlib only — no `pip install` needed)
- Claude Code, Cursor, or any MCP-compatible client

## Tests

```bash
python -m pytest tests/ -v
```

29 tests, 0 external dependencies.

## License

MIT
