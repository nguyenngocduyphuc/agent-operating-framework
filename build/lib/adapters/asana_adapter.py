#!/usr/bin/env python3
"""Generic Asana tracker adapter for AOF.

Zero third-party dependencies — stdlib only (urllib, json, os, pathlib).
No hardcoded workspace paths, project IDs, or section GIDs: everything the
adapter needs is passed in or read from the environment / a `.env` file.

Public API:
    load_token(dotenv_path=None) -> str
        Resolve an Asana token from env (ASANA_TOKEN / asana_token /
        ASANA_API_KEY / TRACKER_TOKEN) or a .env file. Returns "" if none.
    post_comment(task_gid, text, token=None) -> dict
        POST a plain story (comment) to an Asana task.
    complete_task(task_gid, token=None) -> dict
        PUT completed=True on an Asana task.

CLI:
    python3 adapters/asana_adapter.py comment --task <gid> --text "..."
    python3 adapters/asana_adapter.py done    --task <gid> --evidence "..."
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ASANA_BASE_URL = "https://app.asana.com/api/1.0"
_TOKEN_KEYS = ("ASANA_TOKEN", "asana_token", "ASANA_API_KEY", "TRACKER_TOKEN")


def _ssl_context():
    """Certifi-based SSL context with a lazy fallback (matches core/mcp_server)."""
    import ssl as _ssl
    try:
        import certifi
        return _ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return _ssl.create_default_context()


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Generic dotenv parser — no assumptions about which file/where."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def load_token(dotenv_path: str | os.PathLike | None = None) -> str:
    """Resolve an Asana token.

    Order: process env (any of _TOKEN_KEYS) -> explicit dotenv_path ->
    ./.env in the current working directory. Returns "" when nothing is found.
    """
    for key in _TOKEN_KEYS:
        if os.environ.get(key):
            return os.environ[key]
    candidates: list[Path] = []
    if dotenv_path:
        candidates.append(Path(dotenv_path).expanduser())
    candidates.append(Path.cwd() / ".env")
    for path in candidates:
        parsed = _parse_dotenv(path)
        for key in _TOKEN_KEYS:
            if parsed.get(key):
                return parsed[key]
    return ""


def _request(method: str, endpoint: str, token: str, data: dict | None = None) -> dict:
    """Minimal Asana REST call. Raises urllib errors on failure (caller handles)."""
    payload = json.dumps({"data": data}).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url=f"{ASANA_BASE_URL}{endpoint}",
        method=method,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AOF-Asana-Adapter/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _redact(text: str, token: str | None) -> str:
    if token and token in text:
        return text.replace(token, "***REDACTED***")
    return text


def post_comment(task_gid: str, text: str, token: str | None = None) -> dict:
    """POST a plain comment (story) to an Asana task.

    Returns {"ok": True, "story_gid": ...} or {"ok": False, "error": ...}.
    """
    token = token or load_token()
    if not token:
        return {"ok": False, "error": "no Asana token (set ASANA_TOKEN or TRACKER_TOKEN)"}
    if not task_gid:
        return {"ok": False, "error": "task_gid is required"}
    try:
        body = _request("POST", f"/tasks/{task_gid}/stories", token, {"text": text})
        return {"ok": True, "story_gid": body.get("data", {}).get("gid", ""), "task_gid": task_gid}
    except urllib.error.HTTPError as exc:
        raw = _redact(exc.read().decode("utf-8", errors="replace")[:500], token)
        return {"ok": False, "error": f"HTTP {exc.code}: {raw}"}
    except Exception as exc:  # noqa: BLE001 - fail soft, caller keeps local audit
        return {"ok": False, "error": _redact(str(exc), token)}


def complete_task(task_gid: str, token: str | None = None) -> dict:
    """Mark an Asana task completed.

    Returns {"ok": True, "completed": True} or {"ok": False, "error": ...}.
    """
    token = token or load_token()
    if not token:
        return {"ok": False, "error": "no Asana token (set ASANA_TOKEN or TRACKER_TOKEN)"}
    if not task_gid:
        return {"ok": False, "error": "task_gid is required"}
    try:
        body = _request("PUT", f"/tasks/{task_gid}", token, {"completed": True})
        return {"ok": True, "completed": body.get("data", {}).get("completed", True), "task_gid": task_gid}
    except urllib.error.HTTPError as exc:
        raw = _redact(exc.read().decode("utf-8", errors="replace")[:500], token)
        return {"ok": False, "error": f"HTTP {exc.code}: {raw}"}
    except Exception as exc:  # noqa: BLE001 - fail soft
        return {"ok": False, "error": _redact(str(exc), token)}


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generic Asana tracker adapter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_comment = sub.add_parser("comment", help="Post a comment (story) to a task")
    p_comment.add_argument("--task", required=True, help="Asana task GID")
    p_comment.add_argument("--text", required=True, help="Comment text")

    p_done = sub.add_parser("done", help="Post evidence comment then complete the task")
    p_done.add_argument("--task", required=True, help="Asana task GID")
    p_done.add_argument("--evidence", required=True, help="Evidence / closeout comment text")
    p_done.add_argument("--no-complete", action="store_true", help="Post the comment but do not complete the task")

    args = parser.parse_args(argv)
    token = load_token()
    if not token:
        print(json.dumps({"ok": False, "error": "no Asana token found in env or .env"}))
        return 1

    if args.cmd == "comment":
        result = post_comment(args.task, args.text, token)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    # done
    comment_result = post_comment(args.task, args.evidence, token)
    output: dict = {"comment": comment_result}
    if not args.no_complete:
        output["complete"] = complete_task(args.task, token)
    ok = comment_result.get("ok") and (args.no_complete or output.get("complete", {}).get("ok"))
    print(json.dumps(output, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_cli())
