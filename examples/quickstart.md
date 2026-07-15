# AOF Quickstart

> 💡 **No-code?** See the [No-code quickstart](../README.md#no-code-quickstart) for copy-paste prompts you can use with Claude Code or Codex right away.

Get an agent operating framework running in your workspace in 5 minutes.

## 1. Install

```bash
# Copy the core directory into your project
cp -r path/to/aof/core/ your-project/core/
```

## 2. Create workspace marker

```bash
touch your-project/.agentframework
```

AOF uses this file to find the workspace root. You can place it at the
monorepo root, or export `AOF_WORKSPACE` in your shell.

## 3. Run preflight

```bash
python -m core.preflight
```

This checks: repo/branch state, contract requirements, credential
groups, and policy flags. Exit code 0 = ready; exit code 2 = fix first.

Pass `--json` for machine-readable output.

## 4. Configure policy (optional)

Copy the policy template and tailor it:

```bash
cp .aof_policy.example.json .aof_policy.json
# edit .aof_policy.json for your workspace
```

## 5. Configure env vars

Copy the adapter template and fill in your values:

```bash
cp adapters/.env.example adapters/.env
# edit adapters/.env with your tokens
```

## 6. Create your first contract

Create a task brief with an Execution Contract header. See
`examples/contract_template.md`.

## 7. Run the demo

```bash
python examples/full_flow_demo.py
```

This runs preflight and a sample contract validation.

## 7. Integrate with your agent

Add the AOF MCP server to your agent's config. The server exposes
`preflight`, `check_contract`, `verify_gate`, `audit_scope`, `session_log`,
and `post_evidence` tools.

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
