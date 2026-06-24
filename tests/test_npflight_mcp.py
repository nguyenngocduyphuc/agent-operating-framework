#!/usr/bin/env python3
"""Unit tests for npflight_mcp.py — agent-operating-framework MCP server."""
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from npflight_mcp import (
    t_audit_scope,
    t_check_contract,
    t_operating_protocol,
    t_query_audit,
    t_session_log,
    t_verify_gate,
)

FULL_BRIEF = """
Task: Add query_audit tool to the MCP server
Owner: Claude Code agent
Scope: src/npflight_mcp.py, tests/test_npflight_mcp.py
DoD: all tests pass, no ruff violations
Do not: edit files outside Scope, push to main
Stop if: any file outside Scope is needed
Return: git diff + test output summary
"""


class TestCheckContract(unittest.TestCase):
    def test_all_fields_present(self):
        r = json.loads(t_check_contract({"brief": FULL_BRIEF}))
        self.assertTrue(r["ok"])
        self.assertEqual(r["missing"], [])
        self.assertIn("decision_id", r)

    def test_missing_all_fields(self):
        r = json.loads(t_check_contract({"brief": "some vague task description"}))
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["missing"]), 7)

    def test_missing_dod_and_return(self):
        brief = "Task: fix\nOwner: agent\nScope: src/\nDo not: push\nStop if: out of scope"
        r = json.loads(t_check_contract({"brief": brief}))
        self.assertFalse(r["ok"])
        self.assertIn("DoD", r["missing"])
        self.assertIn("Return", r["missing"])

    def test_markdown_bold_style(self):
        brief = ("**Task:** Fix\n**Owner:** Agent\n**Scope:** src/\n"
                 "**DoD:** pass\n**Do not:** push\n**Stop if:** oos\n**Return:** diff")
        self.assertTrue(json.loads(t_check_contract({"brief": brief}))["ok"])

    def test_list_dash_style(self):
        brief = ("- Task: Fix\n- Owner: Agent\n- Scope: src/\n"
                 "- DoD: pass\n- Do not: push\n- Stop if: oos\n- Return: diff")
        self.assertTrue(json.loads(t_check_contract({"brief": brief}))["ok"])

    def test_empty_brief_fails_all(self):
        r = json.loads(t_check_contract({"brief": ""}))
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["missing"]), 7)

    def test_decision_id_is_8_hex_chars(self):
        r = json.loads(t_check_contract({"brief": FULL_BRIEF}))
        self.assertRegex(r["decision_id"], r"^[0-9a-f]{8}$")

    def test_suggestions_for_missing_fields(self):
        brief = "Task: fix\nOwner: me\nScope: src/"
        r = json.loads(t_check_contract({"brief": brief}))
        self.assertIn("DoD", r["suggestions"])
        self.assertIn("Return", r["suggestions"])

    def test_found_captures_field_values(self):
        r = json.loads(t_check_contract({"brief": FULL_BRIEF}))
        self.assertIn("Task", r["found"])
        self.assertIn("query_audit", r["found"]["Task"])


class TestAuditScope(unittest.TestCase):
    def test_all_in_scope_exact(self):
        r = json.loads(t_audit_scope({
            "scope": "src/npflight_mcp.py, tests/test_npflight_mcp.py",
            "changed_files": ["src/npflight_mcp.py", "tests/test_npflight_mcp.py"],
        }))
        self.assertTrue(r["ok"])
        self.assertEqual(r["out_of_scope"], [])

    def test_glob_pattern_matches(self):
        r = json.loads(t_audit_scope({
            "scope": "src/*.py",
            "changed_files": ["src/npflight_mcp.py", "src/npflight.py"],
        }))
        self.assertTrue(r["ok"])

    def test_out_of_scope_detected(self):
        r = json.loads(t_audit_scope({
            "scope": "src/*.py",
            "changed_files": ["src/npflight_mcp.py", "README.md"],
        }))
        self.assertFalse(r["ok"])
        self.assertIn("README.md", r["out_of_scope"])
        self.assertIn("SCOPE VIOLATION", r["verdict"])

    def test_empty_changed_files_is_ok(self):
        r = json.loads(t_audit_scope({"scope": "src/", "changed_files": []}))
        self.assertTrue(r["ok"])

    def test_newline_separated_scope(self):
        r = json.loads(t_audit_scope({
            "scope": "src/npflight_mcp.py\ntests/",
            "changed_files": ["src/npflight_mcp.py", "tests/test_npflight_mcp.py"],
        }))
        self.assertTrue(r["ok"])

    def test_directory_prefix_match(self):
        r = json.loads(t_audit_scope({
            "scope": "src/",
            "changed_files": ["src/npflight.py", "src/npflight_mcp.py"],
        }))
        self.assertTrue(r["ok"])


class TestVerifyGate(unittest.TestCase):
    def test_unknown_gate_returns_error(self):
        r = json.loads(t_verify_gate({"gate_type": "nonexistent"}))
        self.assertFalse(r["ok"])
        self.assertIn("unknown gate", r["error"])

    @patch("npflight_mcp.subprocess.run")
    def test_ruff_pass(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="All checks passed.", stderr="")
        r = json.loads(t_verify_gate({"gate_type": "ruff", "cwd": "/tmp"}))
        self.assertEqual(r["status"], "pass")
        self.assertEqual(r["exit_code"], 0)

    @patch("npflight_mcp.subprocess.run")
    def test_pytest_fail(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="1 failed", stderr="")
        r = json.loads(t_verify_gate({"gate_type": "pytest", "cwd": "/tmp"}))
        self.assertEqual(r["status"], "fail")

    @patch("npflight_mcp.subprocess.run")
    def test_includes_duration(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        r = json.loads(t_verify_gate({"gate_type": "ruff", "cwd": "/tmp"}))
        self.assertIn("duration_s", r)
        self.assertGreaterEqual(r["duration_s"], 0)

    @patch("npflight_mcp.subprocess.run")
    def test_extra_args_passed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        t_verify_gate({"gate_type": "ruff", "cwd": "/tmp", "extra_args": ["--select", "E501"]})
        call_cmd = mock_run.call_args[0][0]
        self.assertIn("--select", call_cmd)

    @patch("npflight_mcp.subprocess.run",
           side_effect=subprocess.TimeoutExpired(cmd="ruff", timeout=120))
    def test_timeout_handled(self, _):
        r = json.loads(t_verify_gate({"gate_type": "ruff", "cwd": "/tmp"}))
        self.assertEqual(r["status"], "timeout")
        self.assertEqual(r["exit_code"], -1)


class TestOperatingProtocol(unittest.TestCase):
    def test_returns_non_empty_string(self):
        result = t_operating_protocol({})
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 30)

    def test_contains_key_protocol_terms(self):
        result = t_operating_protocol({})
        self.assertTrue(any(t in result.upper() for t in ["CONTRACT", "LOOP", "SCOPE", "PREFLIGHT"]))


class TestSessionLog(unittest.TestCase):
    def test_returns_ok(self):
        r = json.loads(t_session_log({"event": "dod_met", "data": {"task": "1234"}}))
        self.assertTrue(r["ok"])

    def test_event_name_preserved(self):
        r = json.loads(t_session_log({"event": "blocker_hit"}))
        self.assertEqual(r["logged"]["event"], "blocker_hit")

    def test_session_id_in_logged(self):
        r = json.loads(t_session_log({"event": "test"}))
        self.assertIn("session_id", r["logged"])


class TestQueryAudit(unittest.TestCase):
    def test_returns_ok_when_no_log(self):
        # Works even with no audit file (fresh install)
        import npflight_mcp
        original = npflight_mcp.AUDIT_FILE
        npflight_mcp.AUDIT_FILE = "/tmp/nonexistent_audit_xyz.jsonl"
        try:
            r = json.loads(t_query_audit({"limit": 10}))
            self.assertTrue(r["ok"])
            self.assertEqual(r["entries"], [])
        finally:
            npflight_mcp.AUDIT_FILE = original

    def test_returns_summary_stats(self):
        # Write some entries then query
        import npflight_mcp, tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for tool in ["preflight", "check_contract", "preflight"]:
                f.write(json.dumps({"ts": "2026-01-01T00:00:00Z", "session_id": "abc",
                                    "tool": tool, "args": {}, "result": "ok", "duration_ms": 10}) + "\n")
            tmp_path = f.name
        original = npflight_mcp.AUDIT_FILE
        npflight_mcp.AUDIT_FILE = tmp_path
        try:
            r = json.loads(t_query_audit({}))
            self.assertTrue(r["ok"])
            self.assertEqual(r["summary"]["tool_counts"]["preflight"], 2)
            self.assertEqual(r["summary"]["tool_counts"]["check_contract"], 1)
        finally:
            npflight_mcp.AUDIT_FILE = original
            os.unlink(tmp_path)

    def test_tool_filter_works(self):
        import npflight_mcp, tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for tool in ["preflight", "check_contract", "preflight"]:
                f.write(json.dumps({"ts": "Z", "session_id": "s1",
                                    "tool": tool, "args": {}, "result": "ok", "duration_ms": 0}) + "\n")
            tmp_path = f.name
        original = npflight_mcp.AUDIT_FILE
        npflight_mcp.AUDIT_FILE = tmp_path
        try:
            r = json.loads(t_query_audit({"tool": "preflight"}))
            self.assertEqual(r["total_filtered"], 2)
            self.assertTrue(all(e["tool"] == "preflight" for e in r["entries"]))
        finally:
            npflight_mcp.AUDIT_FILE = original
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
