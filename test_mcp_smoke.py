#!/usr/bin/env python3
"""Smoke test for the AOF MCP server (newline-delimited JSON transport).

Sends ONE small JSON-RPC message per request and blocks for the reply, sending
no further bytes — exactly the one-shot client pattern that deadlocked the old
Content-Length read(4096) loop. A hard queue.get(timeout=...) makes any regression
FAIL FAST instead of hanging forever.
"""
import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

TIMEOUT_S = 5.0


class Client:
    def __init__(self, server_path):
        self.proc = subprocess.Popen(
            [sys.executable, str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._q = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout:
            self._q.put(line)
        self._q.put(None)

    def request(self, method, params=None, req_id=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if req_id is not None:
            msg["id"] = req_id
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        try:
            line = self._q.get(timeout=TIMEOUT_S)
        except queue.Empty:
            self.proc.kill()
            raise TimeoutError(f"no response to {method!r} within {TIMEOUT_S}s (transport deadlock)")
        if line is None:
            raise RuntimeError(f"server closed stdout without answering {method!r}")
        return json.loads(line)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=TIMEOUT_S)
        except Exception:
            self.proc.kill()


def main():
    server_path = Path(__file__).resolve().parent / "core" / "mcp_server.py"
    client = Client(server_path)
    try:
        print("Sending initialize...")
        init = client.request("initialize", req_id=1)
        assert init["id"] == 1 and "result" in init, f"bad initialize response: {init}"
        print(f"  initialize OK: {init['result']['serverInfo']}")

        print("Sending tools/list...")
        tools = client.request("tools/list", req_id=2)
        names = [t["name"] for t in tools["result"]["tools"]]
        assert "check_contract" in names, f"tools/list missing check_contract: {names}"
        print(f"  tools/list OK: {names}")

        print("Sending tools/call check_contract...")
        brief = "Task: t\nOwner: o\nScope: s\nDoD: d\nDo not: x\nStop if: y\nReturn: r\n"
        call = client.request("tools/call", {"name": "check_contract", "arguments": {"brief": brief}}, req_id=3)
        assert call["result"]["ok"] is True, f"check_contract not ok: {call}"
        print(f"  tools/call OK: {call['result']}")

        print("\nSmoke test PASSED - initialize + tools/list + tools/call all answered.")
        return 0
    except Exception as e:  # noqa: BLE001 - top-level smoke reporting
        print(f"\nSmoke test FAILED: {e}")
        _, stderr = client.proc.communicate(timeout=2) if client.proc.poll() is None else ("", "")
        if stderr:
            print(f"Server stderr:\n{stderr}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
