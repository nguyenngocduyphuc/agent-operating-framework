# Agent Operating Framework (AOF)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](core/LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)](#)

> A lightweight operational gate for AI-agent workspaces -- prevents wrong-repo, wrong-branch, and ungrounded execution.

## Features

- **Preflight gate** -- detects workspace, repo, branch, and credential gaps before work starts. Exit 0 = ready, exit 2 = fix first.
- **Execution contract** -- scope-lock every task with Task/Owner/Scope/DoD/Stop-if/Return. No silent expansion, no scope creep.
- **MCP server** -- stdio JSON-RPC server for agent-host integration (Claude Code, Cline, Cursor, etc.). Exposes `preflight`, `check_contract`, `verify_gate`, `audit_scope`, `session_log`, and `post_evidence` tools.
- **Scope audit** -- compares changed files against the active contract scope before claiming done. Catches side-quests automatically.
- **Verify gate** -- runs quality checks (ruff, pytest, custom gates) with optional multi-trial statistical pass for flaky tests.
- **Evidence log** -- structured audit trail to `~/.npflight/audit.jsonl`. Every action is logged: decisions, gates, blockers, outcomes.

## Quickstart

```bash
# 1. Clone or copy core/ into your project
# 2. Create a workspace marker
touch .agentframework
# 3. Run preflight
python -m core.preflight
# 4. Integrate MCP server with your agent host
python -m core.mcp_server
```

Configure your agent host's `.mcp.json`:

```json
{
  "mcpServers": {
    "aof": {
      "command": "python",
      "args": ["-m", "core.mcp_server"],
      "env": {}
    }
  }
}
```

---

## Architecture

```
adapters/              workspace-specific config (env, policy, credentials)
  .env.example
  workspace_config.example.json

  core/                  generic framework (preflight, MCP, contracts, protocol)
  preflight.py
  check_contract.py
  mcp_server.py
  execution_contract.md
  operating_protocol.md

examples/              runnable demo and templates
  demo.py
  quickstart.md
  contract_template.md
```

Core is workspace-agnostic. Adapters bridge it to a specific project by supplying environment variables, paths, and policy flags. Activation order: core defaults -> adapter files -> env vars.

---

## Why AOF?

AI agents drift. The same problems show up session after session: an agent commits to the wrong repository, works on the wrong branch, silently expands scope beyond what was asked, or makes ungrounded claims that slip past human review. These are not bad-agent problems -- they are no-gate problems.

AOF puts a lightweight gate at the session boundary. It runs at the start of every agent session and catches the same class of errors that a pre-flight checklist catches for a pilot: "Am I in the right place? Do I have what I need? What am I not allowed to do?" The gate is opt-in per workspace, takes under a second to run, and fails closed.

AOF is not a platform. There are no servers to operate, no databases to maintain, no dashboards to check. It is a thin CLI tool with a companion MCP server, written in Python stdlib only. You can copy `core/` into any project and be running in five minutes. The contract is a markdown header, the evidence log is a JSONL file, and the policy is a flat JSON dict.

The philosophy is contract-first, gate-on-path, evidence-before-done. Every task starts with a written contract that defines scope and stopping conditions. Every gate is checked along the execution path, not at the end. No task is closed without structured evidence. This is operational discipline, not middleware.

---

## Installation

```bash
# Copy into your project (lightweight, no deps)
cp -r core/ your-project/
```

> **Note**: AOF is designed to be copied directly into projects rather than installed as a package. This avoids dependency management complexity and ensures full control over the framework.

---

## Usage

```bash
# Run preflight (check workspace, repo, branch, credentials)
python -m core.preflight

# Machine-readable output (for tooling)
python -m core.preflight --json

# Start MCP server (stdio JSON-RPC)
python -m core.mcp_server

# Run quality checks via MCP server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"verify_gate","arguments":{"gate_type":"ruff"}}}' | python -m core.mcp_server
```

All commands exit 0 on success, 1 on soft failure, 2 on blocker.

---

## Configuration

| File | Purpose |
|------|---------|
| `.agentframework` | Workspace marker file. AOF scans parent directories for this file to find the workspace root. |
| `.aof_policy.json` | Workspace policy. Controls enforcement flags (`require_contract`, `require_evidence`, `enforcement_mode`, etc.). |
| `adapters/.env` | Credentials and path overrides. Not committed. Template at `adapters/.env.example`. |
| `adapters/workspace_config.json` | Gate commands, credential groups, and workspace-specific paths. Not committed. Template at `adapters/workspace_config.example.json`. |

---

## Adapters

The `adapters/` directory holds workspace-specific configuration. The directory ships empty (with templates) until you customize it for your project. This keeps the core framework pure and reusable across any codebase.

Common adapter customizations:
- Setting `require_asana_task: true` to block taskless implementation
- Defining custom gate commands under `gates` (e.g., `"typecheck": "mypy src/"`)
- Configuring credential groups for workspace-specific API tokens

---

## Contributing

Contributions are welcome. This project is in active development. Open an issue or pull request on the repository.

## License

MIT License. See [core/LICENSE](core/LICENSE).

---

## Links

- [Execution Contract](core/execution_contract.md)
- [Operating Protocol](core/operating_protocol.md)
- [Quickstart Guide](examples/quickstart.md)
