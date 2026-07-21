#!/usr/bin/env python3
"""preflight — portable preflight gate for AI agents in any multi-repo workspace.

Run FIRST from your working dir. Resolves which repo/branch you are in, runs
drift-safety checks, prints the binding operating card. Stdlib only (zero deps).

Workspace root resolution (in order):
  $AOF_WORKSPACE env var
  -> nearest ancestor with `.agentframework` marker file
  -> outermost git repo above cwd
  -> cwd

Usage:  python3 -m core.preflight [--task <id>] [--bootstrap] [--json]
Exit:   0 = clear . 2 = blocker
"""
import argparse
import json
import os
import re
import subprocess
import sys


def sh(args, cwd=None):
    try:
        return (
            subprocess.run(args, cwd=cwd, capture_output=True, text=True)
            .stdout.strip()
        )
    except Exception:
        return ""


def nearest_repo(start):
    d = os.path.abspath(start)
    while d != "/":
        git_path = os.path.join(d, ".git")
        if os.path.isdir(git_path) or os.path.isfile(git_path):
            return d
        d = os.path.dirname(d)
    return None


def workspace_root(cwd):
    if os.environ.get("AOF_WORKSPACE"):
        return os.environ["AOF_WORKSPACE"]
    d = os.path.abspath(cwd)
    marker = None
    outer_repo = None
    while d != "/":
        if os.path.exists(os.path.join(d, ".agentframework")):
            marker = d
        if os.path.isdir(os.path.join(d, ".git")):
            outer_repo = d
        d = os.path.dirname(d)
    return marker or outer_repo or os.path.abspath(cwd)


# v1 policy schemas used tracker/style-specific key names. If a legacy key is
# present and its modern twin is NOT explicitly set, the legacy value is honoured
# and the migration is reported. Silently ignoring legacy keys turned a hard-mode
# workspace into fail-open (found in the 2026-07-20 audit: old policy said
# require_asana_task=true, new loader read require_task=false, gate said "clear").
LEGACY_POLICY_ALIASES = {
    "require_asana_task": "require_task",
    "require_ponytail": "require_karpathy",
}


def load_policy(ws):
    policy_path = os.environ.get("AOF_POLICY_FILE") or os.path.join(ws, ".aof_policy.json")
    default = {
        "require_task": False,
        "require_contract": True,
        "require_evidence": True,
        "require_handoff": True,
        "allow_bootstrap_without_task": True,
        # F4-1: worker_watch / aof watch stale threshold (seconds).
        "worker_stale_after_s": 300,
    }
    if not os.path.exists(policy_path):
        default["policy_file"] = policy_path
        default["policy_loaded"] = False
        return default
    try:
        with open(policy_path, encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            migrated = []
            for legacy, modern in LEGACY_POLICY_ALIASES.items():
                if legacy in loaded and modern not in loaded:
                    loaded[modern] = loaded[legacy]
                    migrated.append(f"{legacy} -> {modern}")
            default.update(loaded)
            if migrated:
                default["policy_migrated_keys"] = migrated
        default["policy_loaded"] = True
    except Exception as exc:
        default["policy_error"] = str(exc)
        default["policy_loaded"] = False
    default["policy_file"] = policy_path
    return default


def normalize_github_owner_repo(url):
    """Return owner/repo from a GitHub remote URL, or None if unparseable."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    # SSH: git@github.com:owner/repo(.git)
    m = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # HTTPS (optional auth/www): https://[user@]github.com/owner/repo(.git)
    m = re.match(
        r"^https?://(?:[^/@]+@)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        url,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # ssh://git@github.com/owner/repo(.git)
    m = re.match(r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def check_expected_repository(repo, expected):
    """If expected is set, verify origin remote matches owner/repo. Return blocker or None."""
    if not expected or not isinstance(expected, str) or not expected.strip():
        return None
    expected = expected.strip()
    if not repo:
        return (
            f"expected_repository is '{expected}' but no git repo was found. "
            "cd into the canonical checkout."
        )
    origin = sh(["git", "-C", repo, "remote", "get-url", "origin"])
    if not origin:
        return (
            f"expected_repository is '{expected}' but origin remote is missing or empty. "
            "Set origin to the canonical GitHub repository."
        )
    actual = normalize_github_owner_repo(origin)
    if not actual:
        return (
            f"expected_repository is '{expected}' but origin URL is unparseable as "
            f"GitHub owner/repo: {origin!r}"
        )
    if actual != expected:
        return (
            f"origin repository '{actual}' does not match expected_repository '{expected}'. "
            "Use a checkout of the canonical repository."
        )
    return None


def dotenv_keys(ws):
    env_path = os.path.join(ws, ".env")
    keys = set()
    if not os.path.exists(env_path):
        return keys
    try:
        with open(env_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    keys.add(stripped.split("=", 1)[0].strip())
    except OSError:
        return set()
    return keys


def credential_groups_in_policy(policy):
    groups = policy.get("credential_groups")
    if isinstance(groups, dict) and groups:
        return groups
    return {"TaskTracker": ["TRACKER_TOKEN"]}


def main():
    ap = argparse.ArgumentParser(description="AOF preflight gate")
    ap.add_argument("--task", default=None, help="Task ID to bind")
    ap.add_argument("--bootstrap", action="store_true", help="Allow taskless intake only")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    cwd = os.getcwd()
    ws = workspace_root(cwd)
    repo = nearest_repo(cwd)
    blockers, warns = [], []
    policy = load_policy(ws)

    for migration in policy.get("policy_migrated_keys", []):
        warns.append(
            f"Legacy policy key honoured: {migration}. Rename it in .aof_policy.json "
            "to the modern key — the legacy name is deprecated."
        )

    bootstrap_allowed = bool(args.bootstrap and policy.get("allow_bootstrap_without_task"))
    if policy.get("require_task") and not args.task and not bootstrap_allowed:
        blockers.append(
            "No task bound. Run --bootstrap for intake only, then rerun --task <id>."
        )
    if policy.get("policy_error"):
        blockers.append(f"Invalid policy file: {policy.get('policy_error')}")

    if not repo:
        blockers.append("Not inside any git repo -- cd into a project first.")
        repo_name = branch = "-"
    else:
        repo_name = os.path.relpath(repo, ws) if repo.startswith(ws) else repo
        branch = sh(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
        dirty = sh(["git", "-C", repo, "status", "--porcelain"])
        if branch in ("main", "master"):
            warns.append(f"On {branch}: create a feature branch per task before editing.")
        if args.task and branch and branch not in ("main", "master", "HEAD") and args.task not in branch:
            blockers.append(f"Branch '{branch}' is for a different task than {args.task}. Create the correct branch and retry.")
        if dirty and branch in ("main", "master"):
            warns.append("Uncommitted changes on a shared branch.")

    # F3-2: error ledger — warn only (never blocker) on open / repeated fingerprints.
    try:
        from core.errors_ledger import preflight_error_warnings
        warns.extend(preflight_error_warnings())
    except Exception:
        pass

    expected = policy.get("expected_repository")
    identity_blocker = check_expected_repository(repo, expected)
    if identity_blocker:
        blockers.append(identity_blocker)

    rules_path = os.path.join(ws, "OPERATING_PROTOCOL.md")
    if not os.path.exists(rules_path):
        template_rules = os.path.join(ws, "core", "operating_protocol.md")
        if os.path.exists(template_rules):
            rules_path = template_rules

    env_keys = dotenv_keys(ws)
    cred_groups = credential_groups_in_policy(policy)
    credentials_present = []
    credentials_missing = {}
    for group, keys in cred_groups.items():
        missing = [k for k in keys if k not in env_keys and not os.environ.get(k)]
        if missing:
            credentials_missing[group] = missing
        else:
            credentials_present.append(group)

    status = "blocked" if blockers else ("warn" if warns else "clear")

    card = {
        "workspace": ws, "repo": repo_name, "branch": branch,
        "cwd": os.path.relpath(cwd, ws) if cwd.startswith(ws) else cwd,
        "task": args.task,
        "protocol": rules_path if os.path.exists(rules_path) else "OPERATING_PROTOCOL.md (missing)",
        "status": status, "blockers": blockers, "warnings": warns,
        "policy": {k: v for k, v in policy.items() if k != "policy_error"},
        "credentials_present": credentials_present,
        "credentials_missing": credentials_missing,
    }
    if args.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        cwd_rel = card["cwd"]
        print("─" * 64)
        print(f"  PREFLIGHT . repo={repo_name} . branch={branch}")
        print(f"  workspace={ws}")
        print(f"  cwd={cwd_rel}" + (f" . task={args.task}" if args.task else ""))
        print("─" * 64)
        print("  LOOP: preflight -> contract -> branch -> plan -> task -> delegate -> verify -> stop-check -> ship -> evidence")
        print("  CONTRACT: Task/Owner/Scope/DoD/Do-not/Stop-if/Return. Boundary -> return blocker, NEVER self-expand.")
        print("  Worker NO: publish/deploy/git/tracker-write (orchestrator-only).")
        print(f"  Protocol: {card['protocol']}")
        if policy.get("policy_loaded") or policy.get("require_task"):
            print(f"  POLICY: require_task={bool(policy.get('require_task'))} . "
                  f"require_contract={bool(policy.get('require_contract'))} . "
                  f"require_evidence={bool(policy.get('require_evidence'))} . "
                  f"require_handoff={bool(policy.get('require_handoff'))}")
        if args.bootstrap and not args.task:
            print("  BOOTSTRAP: taskless intake allowed only for creating/finding the task.")
        if credentials_present or credentials_missing:
            print("  CREDENTIALS (presence only, values never printed):")
            if credentials_present:
                print(f"    PRESENT: {', '.join(credentials_present)}")
            for group, missing in credentials_missing.items():
                print(f"    MISSING: {group} -> {', '.join(missing)}")
        for w in warns:
            print(f"  WARN: {w}")
        for b in blockers:
            print(f"  BLOCK: {b}")
        print("─" * 64)
    sys.exit(2 if blockers else 0)


if __name__ == "__main__":
    main()
