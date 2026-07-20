"""aof doctor / aof init — self-diagnosis and zero-knowledge setup. Stdlib only.

The target operator does not know git, pip, or MCP. After ``git clone`` and one
install command, ``aof init`` must leave a working workspace and ``aof doctor``
must answer, in plain language (vi/en): is this machine ready, and if not,
exactly what to do next. Every check is a real probe — the MCP check performs a
live stdio handshake with a spawned server, not an import guess. A doctor that
guesses is the false-success dispatcher all over again.

Exit codes: 0 = ready, 2 = needs attention (same convention as preflight).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any

from core import __version__
from core import lease as lease_mod
from core.preflight import load_policy, workspace_root

_T = {
    "vi": {
        "title": "AOF DOCTOR — kiểm tra sức khoẻ cài đặt",
        "ready": "✅ SẴN SÀNG — máy này vận hành được AOF",
        "broken": "⛔ CẦN XỬ LÝ — làm theo 'Bước tiếp theo' bên dưới",
        "next": "Bước tiếp theo",
        "checks": {
            "python": "Python đủ mới (>= 3.10)",
            "git": "Có git trên máy",
            "workspace": "Nhận diện được thư mục làm việc",
            "policy": "Tập luật (.aof_policy.json) đọc được",
            "mcp": "Máy chủ MCP trả lời thật (bắt tay + đủ 8 công cụ)",
            "lease": "Ổ khoá nhiệm vụ ghi được",
        },
        "fixes": {
            "python": "Cài Python 3.10 trở lên rồi chạy lại.",
            "git": "Cài git (macOS: xcode-select --install; Windows: git-scm.com) rồi chạy lại.",
            "workspace": "Chạy 'aof init' trong thư mục dự án để tạo dấu mốc làm việc.",
            "policy": "Chạy 'aof init' để tạo tập luật mặc định, hoặc sửa lỗi JSON trong .aof_policy.json.",
            "mcp": "Cài lại: pip install . (trong thư mục aof), rồi chạy lại 'aof doctor'.",
            "lease": "Kiểm tra quyền ghi thư mục ~/.aof (hoặc AOF_AUDIT_DIR).",
        },
        "all_good": "Không cần làm gì thêm. Đăng ký với trợ lý AI nếu chưa: claude mcp add aof -- aof start-mcp-server",
        "init_done": "AOF INIT — đã chuẩn bị xong thư mục làm việc",
        "policy_kept": "Giữ nguyên tập luật có sẵn",
        "policy_created": "Đã tạo tập luật mặc định (.aof_policy.json)",
        "marker": "Đã đặt dấu mốc làm việc (.agentframework)",
        "register": "Đăng ký với trợ lý AI (chạy 1 lần):",
        "migrated": "Luật cũ được tự dịch sang tên mới (nên đổi tên trong file)",
    },
    "en": {
        "title": "AOF DOCTOR — installation health check",
        "ready": "✅ READY — this machine can operate AOF",
        "broken": "⛔ NEEDS ATTENTION — follow 'Next step' below",
        "next": "Next step",
        "checks": {
            "python": "Python recent enough (>= 3.10)",
            "git": "git available",
            "workspace": "Workspace resolvable",
            "policy": "Policy file (.aof_policy.json) readable",
            "mcp": "MCP server answers for real (handshake + all 8 tools)",
            "lease": "Task-lease store writable",
        },
        "fixes": {
            "python": "Install Python 3.10+ and re-run.",
            "git": "Install git (macOS: xcode-select --install; Windows: git-scm.com) and re-run.",
            "workspace": "Run 'aof init' in your project directory to create the workspace marker.",
            "policy": "Run 'aof init' to create a default policy, or fix the JSON error in .aof_policy.json.",
            "mcp": "Reinstall: pip install . (inside the aof directory), then re-run 'aof doctor'.",
            "lease": "Check write permission on ~/.aof (or AOF_AUDIT_DIR).",
        },
        "all_good": "Nothing else to do. Register with your AI host if you have not: claude mcp add aof -- aof start-mcp-server",
        "init_done": "AOF INIT — workspace prepared",
        "policy_kept": "Kept existing policy",
        "policy_created": "Created default policy (.aof_policy.json)",
        "marker": "Workspace marker in place (.agentframework)",
        "register": "Register with your AI host (run once):",
        "migrated": "Legacy policy keys auto-translated (rename them in the file)",
    },
}

_DEFAULT_POLICY = {
    "workspace_name": "my-project",
    "require_task": False,
    "require_contract": True,
    "require_evidence": True,
    "require_handoff": True,
    "allow_bootstrap_without_task": True,
    "expected_repository": "",
    "report_language": "vi",
}


def _lang(lang: str | None) -> str:
    return lang if lang in ("vi", "en") else "vi"


def _check_mcp_handshake(ws: str) -> tuple[bool, str]:
    """Spawn the real server, do initialize + tools/list over stdio, count tools."""
    reqs = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-m", "core.mcp_server"],
            input=reqs, capture_output=True, text=True, timeout=20,
            cwd=ws, env=os.environ.copy(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"server did not answer: {exc}"
    tools = None
    for line in r.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 2 and "result" in msg:
            tools = msg["result"].get("tools")
    if tools is None:
        return False, "no tools/list reply on stdout"
    if len(tools) != 8:
        return False, f"expected 8 tools, server reported {len(tools)}"
    return True, f"8 tools, server v{__version__}"


def _check_lease_store(ws: str) -> tuple[bool, str]:
    probe = "__aof_doctor_probe__"
    r = lease_mod.acquire(probe, ws, "doctor")
    if not r.get("ok"):
        return False, r.get("error") or r.get("detail") or r.get("status", "unknown")
    lease_mod.release(probe, ws, "doctor")
    return True, str(lease_mod.lease_dir())


def run_doctor(path: str | None = None, lang: str | None = None) -> dict[str, Any]:
    """Run every probe. Returns a machine-readable report; render with format_doctor."""
    cwd = os.path.abspath(path or os.getcwd())
    ws = workspace_root(cwd)
    checks: dict[str, dict[str, Any]] = {}

    checks["python"] = {
        "ok": sys.version_info >= (3, 10),
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    checks["git"] = {"ok": shutil.which("git") is not None, "detail": shutil.which("git") or "-"}
    checks["workspace"] = {
        "ok": bool(ws) and os.path.isdir(ws),
        "detail": ws,
    }
    policy = load_policy(ws)
    checks["policy"] = {
        "ok": not policy.get("policy_error"),
        "detail": policy.get("policy_error") or policy.get("policy_file", ""),
        "migrated": policy.get("policy_migrated_keys", []),
        "loaded": bool(policy.get("policy_loaded")),
    }
    ok_mcp, detail_mcp = _check_mcp_handshake(ws)
    checks["mcp"] = {"ok": ok_mcp, "detail": detail_mcp}
    ok_lease, detail_lease = _check_lease_store(ws)
    checks["lease"] = {"ok": ok_lease, "detail": detail_lease}

    failed = [k for k, v in checks.items() if not v["ok"]]
    return {
        "version": __version__,
        "workspace": ws,
        "lang": _lang(lang or policy.get("report_language")),
        "checks": checks,
        "failed": failed,
        "ok": not failed,
    }


def format_doctor(report: dict[str, Any]) -> str:
    t = _T[_lang(report.get("lang"))]
    lines = [t["title"], ""]
    lines.append(t["ready"] if report["ok"] else t["broken"])
    lines.append("")
    for key, label in t["checks"].items():
        c = report["checks"][key]
        mark = "✔" if c["ok"] else "✘"
        lines.append(f"  {mark} {label}")
        if not c["ok"] and c.get("detail"):
            lines.append(f"      ({c['detail']})")
    migrated = report["checks"]["policy"].get("migrated")
    if migrated:
        lines.append("")
        lines.append(f"  ⚠ {t['migrated']}: {', '.join(migrated)}")
    lines.append("")
    if report["ok"]:
        lines.append(f"{t['next']}: {t['all_good']}")
    else:
        first = report["failed"][0]
        lines.append(f"{t['next']}: {t['fixes'][first]}")
    return "\n".join(lines)


def run_init(path: str | None = None, lang: str | None = None) -> dict[str, Any]:
    """Prepare a workspace: policy + marker, idempotent, pure Python (Windows-safe)."""
    target = os.path.abspath(path or os.getcwd())
    os.makedirs(target, exist_ok=True)
    policy_path = os.path.join(target, ".aof_policy.json")
    created = False
    if not os.path.exists(policy_path):
        with open(policy_path, "w", encoding="utf-8") as fh:
            json.dump(_DEFAULT_POLICY, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        created = True
    marker = os.path.join(target, ".agentframework")
    with open(marker, "a", encoding="utf-8"):
        pass
    return {"target": target, "policy_created": created, "lang": _lang(lang)}


def format_init(result: dict[str, Any]) -> str:
    t = _T[_lang(result.get("lang"))]
    lines = [t["init_done"], ""]
    lines.append(f"  ✔ {t['policy_created'] if result['policy_created'] else t['policy_kept']}")
    lines.append(f"  ✔ {t['marker']}")
    lines.append("")
    lines.append(t["register"])
    lines.append("  claude mcp add aof -- aof start-mcp-server")
    return "\n".join(lines)
