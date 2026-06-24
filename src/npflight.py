#!/usr/bin/env python3
"""npflight — portable preflight gate for any AI agent workspace.

Resolves which git repo/branch you are in, runs drift-safety checks, and
prints a structured binding card. Reads optional config from ~/.npflight/config.json.

Usage:  python3 src/npflight.py [--task <id>] [--json]
Exit:   0 = clear · 1 = warnings · 2 = blocked
"""
import argparse
import json
import os
import subprocess
import sys

CONFIG_FILE = os.path.expanduser("~/.npflight/config.json")


def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            return json.loads(open(CONFIG_FILE, encoding="utf-8").read())
        except Exception:
            pass
    return {}


def sh(args, cwd=None) -> str:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def find_repo(start: str):
    d = os.path.abspath(start)
    while d != "/":
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return None


def main():
    cfg = _load_config()
    workspace = cfg.get("workspace")  # optional, for display only
    env_checks = cfg.get("env_checks", [])  # list of env var names to check

    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default=None, help="task id this session is bound to")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cwd = os.getcwd()
    repo = find_repo(cwd)
    blockers, warns, checks = [], [], []

    # R1: inside git repo
    if not repo:
        blockers.append("Not inside any git repo — cd into a project first.")
        checks.append({"id": "R1", "name": "git_repo", "status": "fail",
                       "detail": "Not inside any git repo", "blocker": True})
        repo_name = branch = "-"
    else:
        repo_name = os.path.relpath(repo, workspace) if workspace and repo.startswith(workspace) else repo
        branch = sh(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"])
        dirty = sh(["git", "-C", repo, "status", "--porcelain"])
        checks.append({"id": "R1", "name": "git_repo", "status": "pass",
                       "detail": f"repo={repo_name}", "blocker": False})

        # R2: not on main/master
        if branch in ("main", "master"):
            blockers.append(f"On {branch}: create a feature branch before editing.")
            checks.append({"id": "R2", "name": "feature_branch", "status": "fail",
                           "detail": f"On {branch} — create a task-scoped feature branch", "blocker": True})
        else:
            checks.append({"id": "R2", "name": "feature_branch", "status": "pass",
                           "detail": f"branch={branch}", "blocker": False})

        # R3: task id in branch name
        if args.task:
            if args.task in branch:
                checks.append({"id": "R3", "name": "task_in_branch", "status": "pass",
                               "detail": f"task {args.task} found in branch name", "blocker": False})
            else:
                warns.append(f"Branch '{branch}' does not contain task id '{args.task}'.")
                checks.append({"id": "R3", "name": "task_in_branch", "status": "warn",
                               "detail": f"branch '{branch}' does not contain '{args.task}'", "blocker": False})

        # R4: uncommitted changes on shared branch
        if dirty and branch in ("main", "master"):
            warns.append("Uncommitted changes on a shared branch.")
            checks.append({"id": "R4", "name": "clean_shared_branch", "status": "warn",
                           "detail": "uncommitted changes on shared branch", "blocker": False})
        else:
            checks.append({"id": "R4", "name": "clean_shared_branch", "status": "pass",
                           "detail": "ok", "blocker": False})

    # R5+: configurable env var checks
    for i, var in enumerate(env_checks, start=5):
        present = bool(os.environ.get(var, ""))
        checks.append({"id": f"R{i}", "name": f"env_{var.lower()}", "blocker": False,
                       "status": "pass" if present else "warn",
                       "detail": f"{var} set" if present else f"{var} not set in environment"})

    status_str = "blocked" if blockers else ("warn" if warns else "clear")
    card = {
        "status": status_str,
        "repo": repo_name,
        "branch": branch,
        "cwd": cwd,
        "task": args.task,
        "checks": checks,
        "blockers": blockers,
        "warnings": warns,
    }

    if args.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print("─" * 60)
        print(f"  PREFLIGHT · repo={repo_name} · branch={branch} · status={status_str.upper()}")
        if args.task:
            print(f"  task={args.task}")
        print("─" * 60)
        for c in checks:
            icon = "✅" if c["status"] == "pass" else ("⚠️" if c["status"] == "warn" else "🛑")
            print(f"  {icon} {c['id']} {c['name']}: {c['detail']}")
        if blockers:
            print("  🛑 BLOCKERS:")
            for b in blockers:
                print(f"    - {b}")
        print("─" * 60)

    sys.exit(2 if blockers else (1 if warns else 0))


if __name__ == "__main__":
    main()
