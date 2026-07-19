"""Agent Operating Framework — portable preflight, contract, and execution protocol for AI agents.

AOF is a lightweight framework that enforces operational discipline in AI-agent
workspaces. It is not a library you import everywhere — it is a thin gate you run
at session start to prevent wrong-repo, wrong-branch, and ungrounded execution.

Public API:

    python -m core.preflight [--task <id>] [--json]
        Run the preflight gate. Exit 0 = clear, 2 = blocker.

    python -m core.mcp_server
        Start the stdio MCP server for integration with agent hosts.

Typical usage:
    python -m core.preflight --task 1234567890
    → prints operating card, exits 0 or 2
"""

__version__ = "0.2.0b1"
