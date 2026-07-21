# Agent Operating Framework (AOF)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)](#)
[![CI](https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/workflows/aof.yml/badge.svg)](https://github.com/nguyenngocduyphuc/agent-operating-framework/actions/workflows/aof.yml)

> A lightweight operational gate for AI-agent workspaces -- prevents wrong-repo, wrong-branch, and ungrounded execution.

## Setup (3 steps)

```bash
# 1. Install the tool (from a clone; PyPI not published yet)
git clone https://github.com/nguyenngocduyphuc/agent-operating-framework
cd agent-operating-framework
pip install .
# dev (tests/lint): pip install -e ".[dev]"

# 2. Configure your workspace (pure Python, Windows-safe)
aof init your-project/         # creates .aof_policy.json + .agentframework marker
aof doctor your-project/       # real-probe health check, plain vi/en output, exit 0/2

# 3. Register the MCP server with your agent host
claude mcp add aof -- aof start-mcp-server
```

Idempotent -- safe to re-run. The tool stays in your PATH; the project keeps only config.

**No-code daily use (no CLI):** with MCP connected, ask for status (`status_report`) — it includes a 24h effectiveness pulse. Auto file: `~/.aof/estate/HIEU_QUA_HOM_NAY.md` (refreshed on every MCP session end).

## Measured results (3-arm causal benchmark, n=105 runs, preregistered rule)

- **Scope containment: 100% of out-of-scope requests blocked vs 43% bare** (p<0.05, Fisher one-sided, replicated across two independent measurements).
- Task pass rate +11.6pp and fabrication −11.6pp vs bare — consistent direction across both measurements, not individually significant at this n.
- **Cost: ~+35% wall time on gated tasks.** That tax is why lanes exist: the full chain is mandatory only on the risk lane (deploy / publish / multi-file / data-write); routine work can run the lite lane (preflight + evidence) with automatic escalation.
- Measured on one backend; cross-worker generalization not yet measured.

## Features

- **Preflight gate** -- detects workspace, repo, branch, and credential gaps before work starts. Exit 0 = ready, exit 2 = fix first.
- **Execution contract** -- scope-lock every task with Task/Owner/Scope/DoD/Stop-if/Return. No silent expansion, no scope creep.
- **MCP server** -- stdio JSON-RPC (**14 tools**): `preflight`, `check_contract`, `operating_protocol`, `verify_gate`, `audit_scope`, `session_log`, `post_evidence`, `status_report`, `op_log`, `session_recap`, `session_handoff`, `worker_watch`, `aof_resume`, `estate_report`.
- **Effectiveness (no-code)** -- `status_report` embeds a 24h pulse; `estate_report` tool + auto file `~/.aof/estate/HIEU_QUA_HOM_NAY.md` (per-workspace / cmux identity when env present).
- **Task lease** -- one task, one live session. Keyed by the git common dir, so all linked worktrees of a repo share one lock. A second live session on the same task is refused before any gate opens; stale leases (dead holder) are taken over with provenance.
- **Plain-language status** -- `status_report` renders session state in Vietnamese or English for non-technical operators: Blocked / Preparing / Ready / Done-with-proof, always with a concrete next step.
- **Scope audit** -- compares changed files against the active contract scope before claiming done. Catches side-quests automatically.
- **Verify gate** -- runs quality checks (ruff, pytest, custom gates) with optional multi-trial statistical pass for flaky tests.
- **Evidence log** -- structured audit trail to `~/.aof/audit.jsonl`. Every action is logged: decisions, gates, blockers, outcomes.

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
4. On completion, writes structured evidence to `~/.aof/audit.jsonl`.

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
# 1. Install
uv tool install .               # or: pip install .

# 2. Configure workspace (config only -- no code copy)
bash setup.sh your-project/

# 3. Register MCP server
claude mcp add aof -- aof start-mcp-server
```

Agent host `.mcp.json` (manual):

```json
{
  "mcpServers": {
    "aof": {
      "command": "aof",
      "args": ["start-mcp-server"],
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

AOF is not a platform. There are no servers to operate, no databases to maintain, no dashboards to check. It is a thin CLI tool with a companion MCP server, written in Python stdlib only. Install once, configure per project in five minutes. The contract is a markdown header, the evidence log is a JSONL file, and the policy is a flat JSON dict.

The philosophy is contract-first, gate-on-path, evidence-before-done. Every task starts with a written contract that defines scope and stopping conditions. Every gate is checked along the execution path, not at the end. No task is closed without structured evidence. This is operational discipline, not middleware.

---

## Installation

```bash
uv tool install .                            # from a local clone
uv tool install agent-operating-framework   # from PyPI (once published)
pip install .                               # pip fallback
```

The `aof` command is installed globally. Your project keeps only `.aof_policy.json`
(configuration) and `.agentframework` (workspace marker). No framework code is copied
into your project.

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

### MCP response format

Every `tools/call` reply uses the MCP result envelope, so hosts render it instead
of showing an empty tool call:

```json
{"content": [{"type": "text", "text": "<JSON payload>"}], "isError": false}
```

Refusals from the gate (preflight not run, contract not checked, scope audit
stale, ...) come back as `isError: true` with the same envelope — the text
carries `error_code`, `error`, and a `fix` telling the agent what to call next.
JSON-RPC `error` responses are reserved for protocol faults (unknown method,
unparseable JSON).

---

## Configuration

| File | Purpose |
|------|---------|
| `.agentframework` | Workspace marker file. AOF scans parent directories for this file to find the workspace root. |
| `.aof_policy.json` | Workspace policy. Controls enforcement flags (`require_task`, `require_contract`, `require_evidence`, etc.). Start from `.aof_policy.example.json`. |
| `adapters/.env` | Credentials and path overrides. Not committed. Template at `adapters/.env.example`. |

### `require_karpathy` (default: `false`)

Off by default: it raises the bar for what counts as a valid brief, and that is a
workspace's call, not the framework's. Turn it on in `.aof_policy.json` when you
want thinking-before-code to be a gate instead of a slogan:

```json
{ "require_karpathy": true }
```

With the flag on, `check_contract` adds three structural checks on top of the
seven required fields. Each binds to machinery that runs later, so passing the
check costs something:

| Principle | Check | Teeth |
|---|---|---|
| 1. Think before coding | brief has `Assumptions:` or `Tradeoffs:` with substance | the claim is named and lands in the audit trail |
| 4. Goal-driven execution | brief has a non-trivial `DoD-cmd:` | the server **runs** it via `verify_gate` `gate_type="dod"` |
| 2 + 3. Simplicity / surgical | `Scope:` is bounded (no `*`, `**/*`, `.`) | `audit_scope` can actually catch drift |

A brief that satisfies it:

```
Task: Add a health endpoint
Owner: worker
Scope: src/api/health.py, tests/test_health.py
Assumptions: the router already mounts /api; if it does not, this needs a router change first.
DoD: GET /health returns 200
DoD-cmd: python -m pytest tests/test_health.py
Do not: touch deploy config
Stop if: the fix needs a router change
Return: diff + test output
```

When a brief fails, `check_contract` returns `ok: false` plus a `hint` naming
each failed principle, the problem, and the fix.

**Limits, stated plainly.** These checks test the *structure* of a brief, not the
truth of it. `Assumptions: none that matter for this change` passes. `DoD-cmd:`
rejects a literal no-op list (`true`, `:`, `echo ok`) but not a crafted one like
`python -c pass`. This is detection, not prevention: it makes an unthought brief
an explicit, auditable lie rather than a silent omission. A reviewer still judges
quality.

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
