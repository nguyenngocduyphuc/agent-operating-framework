# Adapters — Workspace-Specific Configuration

The AOF core is workspace-agnostic. Adapters bridge it to a specific
workspace by supplying environment variables, paths, and policies.

## How it works

1. **`core/`** loads default config from its own defaults.
2. **Adapter files** in this directory override those defaults.
3. The activation order is: core defaults → adapter files → env vars.

## Adapter files

| File | Purpose |
|------|---------|
| `.env` | Workspace tokens, secrets, and path overrides. Not committed. |
| `.env.example` | Template showing which env vars are expected. Committed. |
| `workspace_config.json` | Workspace config (paths, policy flags, credential groups, gate commands). Not committed. |
| `workspace_config.example.json` | Template for the config. Committed. |
| `asana_adapter.py` | Generic Asana tracker adapter (stdlib only). Committed. |

## Asana tracker adapter (`asana_adapter.py`)

A generic, zero-dependency (stdlib `urllib`) bridge that lets AOF post real
tracker evidence. No hardcoded paths, project IDs, or section GIDs.

**Public API**

- `load_token(dotenv_path=None) -> str` — resolves a token from env
  (`ASANA_TOKEN` / `asana_token` / `ASANA_API_KEY` / `TRACKER_TOKEN`) or a
  `.env` file; returns `""` if none.
- `post_comment(task_gid, text, token=None) -> dict` — post a story (comment).
- `complete_task(task_gid, token=None) -> dict` — mark a task completed.

**CLI**

```bash
python3 adapters/asana_adapter.py comment --task <gid> --text "hello"
python3 adapters/asana_adapter.py done    --task <gid> --evidence "closeout summary"
# `done` posts the evidence comment then completes the task (use --no-complete to skip completion).
```

**How `post_evidence` picks it up**

`core/mcp_server.py`'s `post_evidence` tool always logs to the local audit
trail (source of truth). It *additionally* posts to Asana when BOTH env vars
are set:

- `TRACKER_TYPE=asana`
- `TRACKER_TOKEN=<asana personal access token>`

The network call is fail-soft: if it fails (bad token / offline), the tool
still returns success with the local audit confirmation plus the tracker error
under `result["tracker"]`. When `exit_code == 0` (resolution `Done`),
`post_evidence` also calls `complete_task`.

## Customizing for your workspace

- Copy `.env.example` to `.env` and fill in your tokens.
- Copy `workspace_config.example.json` to `workspace_config.json` and
  adjust paths, gates, and credential groups.
- The `require_*` flags in workspace_config control which AOF checks
  are enforced (e.g., `require_asana_task: true` blocks taskless work).
- Gate commands in `gates` map names to CLI invocations used by
  `aof gate run <name>`.

## Workspace marker

AOF discovers the workspace root by looking for `.agentframework`
(your choice — could be `.git`, a marker file, or any path).
Set `AOF_WORKSPACE` in `.env` to override auto-detection.
