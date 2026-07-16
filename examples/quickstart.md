# AOF Quickstart

> 💡 **No-code pilot?** See the [beta onboarding prompts](../README.md#no-code-pilot-beta) for Claude Code or Codex.

Start an agent operating framework in your workspace.

## 1. Install

```bash
# Copy the runtime and policy template into your project
cp -R path/to/aof/core path/to/aof/.aof_policy.example.json your-project/
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

Copy the optional adapter template, then fill in your values:

```bash
cp -R path/to/aof/adapters your-project/
cp your-project/adapters/.env.example your-project/adapters/.env
# edit your-project/adapters/.env with your tokens
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
