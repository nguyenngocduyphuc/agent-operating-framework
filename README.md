# Agent Operating Framework (AOF)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](core/LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)](#)

> A lightweight operational gate for AI-agent workspaces -- prevents wrong-repo, wrong-branch, and ungrounded execution.

## One-command setup

```bash
bash setup.sh your-project/
```

Or from a remote URL (no clone needed):

```bash
curl -fsSL https://raw.githubusercontent.com/nguyenngocduyphuc/agent-operating-framework/main/setup.sh | bash -s -- your-project/
```

Runs preflight, configures the workspace marker, creates initial commit, and shows MCP
registration. Idempotent -- safe to re-run on an existing AOF workspace.

## Features

- **Preflight gate** -- detects workspace, repo, branch, and credential gaps before work starts. Exit 0 = ready, exit 2 = fix first.
- **Execution contract** -- scope-lock every task with Task/Owner/Scope/DoD/Stop-if/Return. No silent expansion, no scope creep.
- **MCP server** -- stdio JSON-RPC server for agent-host integration (Claude Code, Cline, Cursor, etc.). Exposes `preflight`, `check_contract`, `verify_gate`, `audit_scope`, `session_log`, and `post_evidence` tools.
- **Scope audit** -- compares changed files against the active contract scope before claiming done. Catches side-quests automatically.
- **Verify gate** -- runs quality checks (ruff, pytest, custom gates) with optional multi-trial statistical pass for flaky tests.
- **Evidence log** -- structured audit trail to `~/.npflight/audit.jsonl`. Every action is logged: decisions, gates, blockers, outcomes.

## No-code pilot (beta)

Paste one of these prompts into Claude Code or Codex (pilot hosts). This is a
beta onboarding path; release claims wait for the pilot thresholds in the QA plan.

### Install

```text
Install Agent Operating Framework from
https://github.com/nguyenngocduyphuc/agent-operating-framework
for this workspace. Keep credentials private, configure the AOF MCP server,
run the smoke test, and tell me only: Ready, Needs approval, or Blocked.
```

### Daily use

```text
Use AOF for this goal: <plain-language goal>.
Plan it, keep scope safe, ask before risky actions, verify the result,
and give me a plain-language evidence summary.
```

### Expected pilot states

The host agent should respond with one of four states:

| State | Meaning |
|-------|---------|
| **Planning** | Analysing the goal, creating a contract, checking prerequisites. |
| **Needs approval** | Ready to act but needs your OK — scope, risk, or cost check. |
| **Blocked** | Can't proceed — wrong workspace, missing credentials, or unsafe request. |
| **Done** | Goal met. Summary is plain language, not JSON or exit codes. |

<details>
<summary>How it works — technical overview</summary>

When you paste either prompt, your agent:

1. Calls `preflight` to verify workspace, repo, and credentials.
2. Creates an **execution contract** from your goal — a scope-lock with Task, Owner, DoD, and Stop-if.
3. Reports back its internal state: **Planning**, **Needs approval**, **Blocked**, or **Done**.
4. On completion, writes structured evidence to `~/.npflight/audit.jsonl`.

Exit codes (0 = success, 2 = blocker) and MCP calls are handled internally.
You only see the state label and a plain-language summary.

</details>

> **Pilot hosts:** Claude Code and Codex first. Other hosts (Cursor, Gemini, etc.) added after the pilot.

---

## Results (measured, honest)

> **Status: Beta.** These measurements come from controlled experiments. Release claims
> wait for the pilot thresholds in the QA plan.

| Metric | Bare (no AOF) | With AOF | Note |
|--------|--------------|----------|------|
| Scope adherence (stayed within task boundaries) | 43 % | **100 %** | n = 105 runs, 3 arms, p = 0.049 one‑sided Fisher — causal, significant |
| Pass rate | 53.1 % | 64.7 % | Consistent trend across two independent runs; not individually significant at n ≈ 33 / arm |
| Fabrication rate (claimed done, wasn't) | 46.9 % | 35.3 % | Separate scorer flag; tracks failed runs closely in this dataset — directional improvement |
| Median wall‑time on gated tasks | baseline | + 35–36 % | Mitigated by risk‑lane activation (full chain only for risky task types) |

**Method:** 5 deterministic tasks × 3 arms × 7 trials, isolated git worktree per run,
same backend model in both arms. Benchmark code in the maintainers' workspace; results
JSON available on request.

---

## Troubleshooting — common install errors

Symptom first, then a prompt you can paste for your agent to self-diagnose.

| Symptom | Prompt for the agent |
|---------|----------------------|
| `python: command not found` | `Check which Python versions are installed, show the path, and suggest how to add it to PATH.` |
| `Not an AOF workspace` / `.agentframework not found` | `Create a .agentframework marker at the workspace root and run preflight again. Tell me if preflight passes.` |
| `JSON decode error` in `.aof_policy.json` | `Read .aof_policy.json, fix syntax errors, validate it, and confirm the file is valid JSON.` |
| Agent says "MCP server not found" | `Run python -m core.mcp_server from the workspace root. If it errors, show the message. If it works, tell me to configure the MCP host.` |
| `exit code 2` with unclear output | `Run python -m core.preflight --json and explain each field in plain language — what's missing and how to fix it.` |

---

## Quickstart

```bash
# 1. Copy the runtime and policy template into your project
cp -R core .aof_policy.example.json your-project/
# Optional: copy credential templates when you need integrations
cp -R adapters your-project/
cd your-project
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
adapters/              workspace-specific config (env, credentials)
  .env.example

core/                  generic framework (preflight, MCP, contracts, protocol)
  preflight.py
  check_contract.py
  mcp_server.py
  execution_contract.md
  operating_protocol.md

examples/              runnable demo and templates
  full_flow_demo.py
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
# Required: runtime and policy template (lightweight, no deps)
cp -R core .aof_policy.example.json your-project/
# Optional: credential templates for integrations
cp -R adapters your-project/
```

> **Note**: AOF is designed to be copied directly into projects rather than installed as a package. This avoids dependency management complexity and ensures full control over the framework.

Keep host runtime state such as `.claude/`, `.codex/`, session logs, and credentials
out of the distribution repository. Configure Claude Code or Codex to call the
tracked `core.mcp_server` entry point; do not publish a user's local agent folder.

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

All commands exit 0 on success, 2 on blocker.

---

## Configuration

| File | Purpose |
|------|---------|
| `.agentframework` | Workspace marker file. AOF scans parent directories for this file to find the workspace root. |
| `.aof_policy.json` | Workspace policy. Controls enforcement flags (`require_task`, `require_contract`, `require_evidence`, etc.). Start from `.aof_policy.example.json`. |
| `adapters/.env` | Credentials and path overrides. Not committed. Template at `adapters/.env.example`. |

---

## Adapters

The `adapters/` directory holds workspace-specific configuration (credentials, env vars). The directory ships empty (with templates). This keeps the core framework pure and reusable across any codebase.

Policy configuration belongs at the workspace root in `.aof_policy.json` (see `.aof_policy.example.json`).

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
