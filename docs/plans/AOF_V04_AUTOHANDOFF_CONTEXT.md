## PHẦN 1 — HỆ THỐNG

Dự án: AOF v0.4 — auto-handoff đa-repo, error ledger chống tái phạm, chuẩn kiểm soát worker
Repo: /Users/phuongnam/02.AI/NP_AI_macos/vendors/agent-operating-framework (canonical duy nhất, upstream nguyenngocduyphuc/agent-operating-framework)
Nhánh: feat/aof-v03-nocode-ops
File lõi: core/mcp_server.py (MCP server, 12→13 tool), core/cli.py (CLI aof), core/oplog.py (recap/handoff/digest), core/lease.py (repo identity + khoá nhiệm vụ), core/preflight.py (gate)
Docs governance bắt buộc đọc trước khi sửa: docs/HISTORY_GOVERNANCE.md (History Gate), docs/history/INDEX.md, docs/plans/AOF_V04_AUTOHANDOFF_EXECPLAN_20260721.md (nguồn gốc plan, commit f47a0e9)
Dashboard: không có — vận hành qua CLI `aof` + MCP server stdio + Estate Console (docs.nampham.net/estate, tra cứu skill governance)
Tất cả dự án liên quan: agent-operating-framework (risk: high — core infra, đang public test), NP_AI_macos root (medium — chứa AOF_WORKSPACE mặc định), 1.Skills_management (low — chỉ tra cứu governance)
Pipeline phase của plan này: (1) History Gate, (2) F2 handoff+recap, (3) F1 đa-repo+index+resume, (4) F3 error ledger, (5) F4 worker control + F5 CI, (6) Verify toàn bộ + smoke 2 môi trường

## PHẦN 2 — KPI FRAMEWORK

Composite không tính bằng % (dự án không có kpi_collector.py) — đo bằng 4 chỉ số nhị phân/đếm được, trọng số bằng nhau 25% mỗi chỉ số vì cả 4 đều là điều kiện DoD cứng trong ExecPlan gốc:
- TESTS: pytest -q toàn repo, target = 0 fail, không được giảm số bài so với baseline
- RUFF: ruff check core/ tests/, target = 0 issue
- TOOLS: số MCP tool trong TOOLS catalog (core/mcp_server.py), target = 13 (hiện 12, F1 thêm aof_resume)
- FEATURES: số tính năng F1-F5 đã Done/5, target = 5/5

## PHẦN 3 — BASELINE 2026-07-21 06:58 — LIVE STATUS

| Metric | Score | Target | Status |
|---|---|---|---|
| TESTS | 134 passed, 0 fail (đo bằng `python3.10 -m pytest -q` trong sandbox, baseline trước F2 = 132) | 0 fail, không giảm | VƯỢT baseline (+2 test F2) |
| RUFF | 0 issue (`ruff check core/ tests/` → "All checks passed!") | 0 issue | PASS |
| TOOLS | 13 sau F1-3 (`aof_resume`); đếm động via `len(TOOLS)` / doctor | 13 | target met when F1-3 shipped |
| FEATURES | F2 + F1 (partial→full when index+resume ship); F3/F4 open | 5/5 | update after each checkpoint |
| GIT COMMIT | BLOCKED — `.git/index.lock` tồn tại, `rm` trả về "Operation not permitted" (không phải stale lock thông thường) | commit sạch trên feat/aof-v03-nocode-ops | Building (chờ CEO gỡ trên máy thật) |

Nguồn: chạy trực tiếp trong phiên này (pytest/ruff), đọc trực tiếp core/mcp_server.py dòng 49-104 (tool count), `ls -la .git/index.lock` + `rm` (git lock). Không suy đoán số nào.

## PHẦN 4 — ĐÃ HOÀN THÀNH

[DONE] F2 — session_handoff tự kèm recap cùng timestamp, link chéo đầu file md
  Files changed: core/oplog.py (+`write_session_bundle()`), core/mcp_server.py (branch session_handoff dùng bundle writer), core/cli.py (lệnh `handoff` ghi cả .md + .html), tests/test_recap_handoff.py (+2 test)
  Evidence: pytest 132→134 (+2, cả 2 xanh), ruff clean, chưa commit được (git lock) nhưng diff đã verify bằng test thật, không phải fabricate

[DONE] F1-1 — session_handoff/session_recap dùng đúng working-tree root của repo đang bound, không còn AOF_WORKSPACE
  Files changed: core/mcp_server.py (import `nearest_repo` từ core.preflight, thay `ws=bound_workspace or AOF_WORKSPACE` bằng `ws=nearest_repo(bound_cwd) or bound_cwd`)
  Bug phụ phát hiện khi tự verify: lần đầu dùng nhầm `lease_mod.repo_identity(bound_cwd)[0]` — hàm này trả về đường dẫn `.git` (đúng cho lease hashing, SAI cho chỗ ghi file — sinh ra `.git/docs/sessions/…`). Sửa lại dùng `nearest_repo()` (working-tree root thật, tôn trọng cả worktree). Ghi lại đây để không tái phạm.
  Evidence: tests/test_mcp_server.py::test_every_tool_answers_with_the_envelope sửa lại preflight vào repo giả lập thay vì REPO thật (tránh ghi bẩn vào chính repo khi chạy test); assert thêm "không leak vào AOF_WORKSPACE"

[DONE] F1-4 — Test đa-repo (2 repo giả lập)
  File mới: tests/test_multirepo_handoff.py (2 test: đa-repo không tráo lẫn, gọi lặp lại không trôi vị trí)
  Evidence: pytest 134→136 (+2), ruff clean, chạy 5 lần liên tiếp đều xanh (loại trừ flaky)

[DONE] Baseline handoff thật đầu phiên (bằng chứng sống cho bug F1, TRƯỚC khi sửa)
  File: /Users/phuongnam/02.AI/NP_AI_macos/docs/sessions/HANDOFF_20260721_065222.md — ghi VÀO WORKSPACE GỐC thay vì repo đang làm, đúng như F1 mô tả. Đối chứng thêm: tìm lại được file gốc mà ExecPlan tham chiếu, `docs/sessions/HANDOFF_20260721_064104.md` — cũng nằm ở NP_AI_macos/docs/sessions/ (không phải trong vendors/agent-operating-framework), cùng một bug, từ phiên trước (không phải phiên này).

## GHI CHÚ RIÊNG — được yêu cầu bổ sung 21/07 (không thuộc F1-F5 gốc)

[TODO] F3-4 đã thêm vào PHẦN 5 checkpoint 3 (engineering loop / self-improve, xem chi tiết dưới) — anh Nam chỉ ra đây là phần "quan trọng nhất" còn thiếu trong /aof-operations:aof, tham khảo kiến trúc bài https://x.com/nifinet/status/2078851409068654639 (Codex self-improving outbound). Quyết định: KHÔNG tách F6/v0.5 — gộp vào F3 vì đã có sẵn trong ExecPlan gốc điểm 5 (improve_ledger, nhịp tuần), chỉ chưa từng tách thành task riêng.

## PHẦN 5 — ROADMAP + AGENT PROMPTS ĐẦY ĐỦ

==========================================================================
CHECKPOINT 2 · F1 — ĐA-REPO + INDEX + AOF RESUME
==========================================================================

--------------------------------------------------------------------------
TASK F1-1: Sửa session_handoff/session_recap dùng nearest_repo (working tree) thay AOF_WORKSPACE    [DONE] Core · Priority: HIGH
--------------------------------------------------------------------------
Mục tiêu: file handoff/recap ghi vào đúng repo đang làm việc, không lệch sang workspace gốc khi làm trong repo con/worktree.
Lý do: bug sống vừa quan sát — HANDOFF_20260721_065222.md ghi vào NP_AI_macos thay vì vendors/agent-operating-framework.

**LANDMINE FIXED 2026-07-21:** KHÔNG dùng `repo_identity()[0]` làm base ghi file — hàm đó trả `.git` common-dir (đúng cho lease/index key, SAI cho write). Dùng `nearest_repo(bound_cwd)` từ `core.preflight`. Xem `docs/ARCHITECTURE.md`.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: (ĐÃ SHIP) session_handoff/session_recap dùng nearest_repo(bound_cwd). Nếu regression: kiểm tra core/mcp_server.py nhánh session_handoff — `ws=nearest_repo(bound_cwd) or bound_cwd`, KHÔNG `repo_identity(...)[0]`.

Verify: `python3 -m pytest -q tests/test_multirepo_handoff.py tests/test_mcp_server.py -q`
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F1-2: ~/.aof/handoffs/index.jsonl — writer khi ghi handoff/recap    [DONE — verify in tests/test_handoff_index_resume.py] Core · Priority: HIGH
--------------------------------------------------------------------------
Mục tiêu: mỗi lần ghi handoff/recap, append 1 dòng index tập trung tra được từ mọi repo.
Lý do: ExecPlan F1 — "con trỏ nằm một chỗ", index.jsonl append-only một writer một schema.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm hàm `append_handoff_index()` vào core/oplog.py, gọi từ nhánh session_handoff trong mcp_server.py ngay sau write_session_bundle().

Bước 1: Đọc `core/enforcement.py::audit_dir()` để biết cách AOF tính thư mục `~/.aof` hiện tại (audit_dir() có thể đã trỏ đúng gốc, chỉ cần audit_dir().parent / "handoffs" / "index.jsonl" hoặc tương đương).
  Báo: đường dẫn audit_dir() trả về thực tế trong sandbox này.

Bước 2: Implement trong core/oplog.py:
  ```python
  def append_handoff_index(repo_identity_path: str, repo_key: str, branch: str,
                            task: str | None, bundle: dict[str, str]) -> str:
      """Append-only index: một dòng mỗi lần session_handoff ghi file.

      Một writer một schema (STOP RULE của ExecPlan) — không ai khác được ghi
      vào file này ngoài hàm này.
      """
      idx_path = Path.home() / ".aof" / "handoffs" / "index.jsonl"
      idx_path.parent.mkdir(parents=True, exist_ok=True)
      row = {
          "ts": time.time(), "repo_identity": repo_identity_path, "repo_key": repo_key,
          "branch": branch, "task": task, "handoff_path": bundle["handoff_path"],
          "recap_path": bundle["recap_path"],
      }
      with open(idx_path, "a", encoding="utf-8") as fh:
          fh.write(json.dumps(row, ensure_ascii=False) + "\n")
      return str(idx_path)
  # === END append_handoff_index ===
  ```

Bước 3: Verify
  Gọi session_handoff 2 lần từ 2 cwd khác nhau (tmp_path) → index.jsonl có đúng 2 dòng, mỗi dòng repo_identity khác nhau.

EVIDENCE REQUIRED:
  1. Test mới: 2 lần gọi → 2 dòng index đúng schema (ts, repo_identity, repo_key, branch, task, handoff_path, recap_path)
  2. File index dùng mode "a" (append), không bao giờ ghi đè
  3. pytest toàn repo vẫn xanh
  STOP và báo CEO nếu phát hiện writer thứ hai ghi vào index.jsonl.
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F1-3: `aof resume` — CLI + MCP tool thứ 13    [DONE — verify tools/list + tests/test_handoff_index_resume.py] Core · Priority: HIGH
--------------------------------------------------------------------------
Mục tiêu: phiên mới gọi 1 lệnh, đọc index, in RESUME BRIEF — hết copy-paste thủ công.
Lý do: ExecPlan F1 mục 3 — "phiên mới chỉ gọi 1 tool".

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm subparser `resume` vào core/cli.py (--task X | --repo <path> | mặc định mới nhất) + tool thứ 13 trong core/mcp_server.py TOOLS catalog.

Bước 1: Đọc core/cli.py dòng 43-58 (mẫu subparser recap/handoff/watch) để giữ đúng convention argparse hiện có.

Bước 2: Implement hàm `format_resume_brief(index_rows, task=None, repo=None)` trong core/oplog.py — lọc theo task/repo, mặc định lấy dòng mới nhất theo ts, đọc nội dung handoff_path, in kèm luật bắt buộc (từ operating_protocol.md) + lệnh làm tiếp.

Bước 3: Verify
  `aof resume --task <task-test>` trả đúng brief đã seed; MCP tool `aof_resume` handshake → 13 tools đúng như doctor.py đối chiếu động.

EVIDENCE REQUIRED:
  1. Test mới: seed 2 dòng index, `aof resume --repo B` chỉ trả brief của repo B
  2. `printf '<initialize+tools/list>' | python core/mcp_server.py` → đủ 13 tool
  3. core/doctor.py không hardcode số tool (đã đối chiếu động — verify không bị vỡ)
  STOP và báo CEO nếu resume đọc sai repo.
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F1-4: Test đa-repo (2 repo giả lập, không tráo lẫn)    [DONE] Test · Priority: HIGH
--------------------------------------------------------------------------
Mục tiêu: chứng minh bằng test tự động rằng F1-1..F1-3 thật sự sửa đúng bug đa-repo, không chỉ "chạy tay thấy đúng".
Lý do: acceptance criteria gốc của F1 trong ExecPlan đòi "test đa-repo (2 repo giả lập)" — không có test này thì F1 chưa coi là Done.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm test mới vào tests/test_recap_handoff.py (hoặc file mới tests/test_multirepo_handoff.py) dựng 2 repo git giả trong tmp_path, gọi session_handoff (qua mcp_server hoặc trực tiếp write_session_bundle+bound_cwd) ở mỗi repo, xác nhận file nằm đúng repo tương ứng.

Bước 1: Đọc tests/test_lease.py để lấy pattern dựng repo git giả (subprocess.run(["git","init",...]) trong tmp_path).
  Báo: pattern dựng repo giả hiện có trong file này.

Bước 2: Viết test:
  ```python
  def test_handoff_writes_into_bound_repo_not_workspace(tmp_path, aof_home, monkeypatch):
      repo_a = tmp_path / "repo_a"; repo_b = tmp_path / "repo_b"
      for r in (repo_a, repo_b):
          r.mkdir(); subprocess.run(["git", "init", "-q"], cwd=r, check=True)
      # gọi handoff trong repo_a, xác nhận file nằm trong repo_a/docs/sessions
      # gọi handoff trong repo_b, xác nhận file nằm trong repo_b/docs/sessions
      # xác nhận repo_a KHÔNG có file của repo_b và ngược lại
  ```

Bước 3: Verify
  `python3.10 -m pytest -q tests/test_recap_handoff.py -k multirepo` — xanh.

EVIDENCE REQUIRED:
  1. Test mới pass — 2 repo, file không tráo lẫn
  2. pytest toàn repo >= 135 pass (134 hiện tại + test này)
  3. Chạy lại được nhiều lần không phụ thuộc thứ tự (idempotent, dùng tmp_path)
  STOP và báo CEO nếu test flaky (pass/fail không ổn định giữa các lần chạy).
--- END PROMPT ---

==========================================================================
CHECKPOINT 3 · F3 — ERROR LEDGER CHỐNG TÁI PHẠM
==========================================================================

--------------------------------------------------------------------------
TASK F3-1: ~/.aof/errors.jsonl qua session_log event "error"    [TODO] Core · Priority: MED
--------------------------------------------------------------------------
Mục tiêu: mọi lỗi thật trong lúc build phải thành 1 dòng ghi được, không thêm tool mới.
Lý do: ExecPlan F3 — nguyên liệu thật 2 ngày qua (5 lỗi: 2 fail-open, 3 shadow-import) đã thành test riêng lẻ, nay cần thành cơ chế chung.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: mở rộng nhánh `session_log` trong mcp_server.py (dòng ~764) — khi `event == "error"`, ghi thêm 1 dòng vào ~/.aof/errors.jsonl với fields {ts, fingerprint, title, session, fix_commit, test_ref, status}.

Bước 1: Đọc mcp_server.py dòng 764-773 (nhánh session_log hiện tại) để không phá vỡ needs_approval/approved logic đang có.

Bước 2: Thêm nhánh con trong session_log:
  ```python
  # === error ledger write ===
  if ev == "error":
      err_row = {
          "ts": time.time(), "fingerprint": a.get("data", {}).get("fingerprint"),
          "title": a.get("data", {}).get("title"), "session": _state.get("session_id"),
          "fix_commit": a.get("data", {}).get("fix_commit"),
          "test_ref": a.get("data", {}).get("test_ref"), "status": "open",
      }
      err_path = Path.home() / ".aof" / "errors.jsonl"
      err_path.parent.mkdir(parents=True, exist_ok=True)
      with open(err_path, "a", encoding="utf-8") as fh:
          fh.write(json.dumps(err_row, ensure_ascii=False) + "\n")
  # === END error ledger write ===
  ```

Bước 3: Verify
  Seed session_log event=error 2 lần với fingerprint trùng → errors.jsonl có 2 dòng, cùng fingerprint.

EVIDENCE REQUIRED:
  1. Test mới: seed 2 lỗi → file có đúng 2 dòng đúng schema
  2. Không thêm tool mới vào TOOLS catalog (vẫn dùng session_log)
  3. pytest toàn repo xanh
  STOP và báo CEO nếu schema errors.jsonl bị viết bởi nơi khác ngoài nhánh này.
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F3-2: preflight WARN khi có lỗi mở/tái phạm    [TODO] Core · Priority: MED
--------------------------------------------------------------------------
Mục tiêu: preflight đọc errors.jsonl, WARN khi status != closed hoặc fingerprint lặp >= 2 lần.
Lý do: "kích hoạt không tái phạm" — không chỉ ghi sổ mà phải cảnh báo chủ động.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm bước đọc errors.jsonl vào core/preflight.py, cộng dòng warn vào `warns` list hiện có (theo mẫu dòng 214 "On {branch}: create a feature branch...").

Bước 1: Đọc core/preflight.py dòng 200-224 (chỗ warns.append hiện tại) để chèn đúng vị trí, đúng convention.

Bước 2: Thêm logic đếm fingerprint từ ~/.aof/errors.jsonl, warn nếu có status != "closed" hoặc fingerprint xuất hiện >= 2 lần trong file.

Bước 3: Verify
  Seed 2 lỗi cùng fingerprint (status=open) → chạy preflight → warns chứa đúng cảnh báo tái phạm.

EVIDENCE REQUIRED:
  1. Test mới: seed 2 lỗi → preflight warns đúng nội dung
  2. Không lỗi nào → preflight không warn (không false positive)
  3. pytest toàn repo xanh
  STOP và báo CEO nếu preflight block cứng thay vì chỉ warn (ExecPlan chỉ định warn, không phải blocker).
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F3-3: đóng lỗi bắt buộc test_ref + lệnh `aof lessons`    [TODO] Core · Priority: MED
--------------------------------------------------------------------------
Mục tiêu: một lỗi CHỈ được đóng khi có test_ref; `aof lessons` liệt kê lỗi mở + lỗi thiếu test_ref.
Lý do: "mỗi lỗi thật → một test vĩnh viễn" — luật máy kiểm, không dựa vào lời hứa.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm subparser `lessons` vào core/cli.py + hàm `format_lessons()` trong core/oplog.py đọc errors.jsonl.

Bước 1: Đọc core/cli.py dòng 36-42 (mẫu subparser `log`) để giữ convention.

Bước 2: Implement rule đóng lỗi — khi `session_log event=error data.status=closed` mà `data.test_ref` rỗng → từ chối (giữ status=open, không cho đóng), audit lý do.

Bước 3: Verify
  `aof lessons` in đúng danh sách lỗi mở + lỗi thiếu test_ref (2 nhóm riêng).

EVIDENCE REQUIRED:
  1. Test mới: đóng lỗi thiếu test_ref → status vẫn "open", có audit lý do từ chối
  2. `aof lessons` liệt kê đúng 2 nhóm
  3. pytest toàn repo xanh
  STOP và báo CEO nếu đóng lỗi thiếu test_ref lại được chấp nhận (đây là gate cứng theo ExecPlan).
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F3-4: Engineering loop cải tiến chính AOF (improve_ledger, nhịp tuần)    [TODO] Core · Priority: MED
--------------------------------------------------------------------------
Mục tiêu: đóng vòng self-improve cho chính AOF — không chỉ ghi lỗi (F3-1..F3-3) mà đề xuất SỬA policy/config dựa trên dữ liệu thật, có eval gate, người duyệt mới merge.
Lý do: đã cam kết trong ExecPlan gốc F3 điểm 5 (chưa từng tách task) + anh Nam 21/07 chỉ ra đây là phần "quan trọng nhất" còn thiếu. Tham khảo kiến trúc: https://x.com/nifinet/status/2078851409068654639 (Codex self-improving outbound: law file → visible config → outcomes-với-lý-do → eval gate bắt ca xấu → 1 đề xuất/lần → PR người duyệt → nhịp tuần). Ánh xạ vào AOF: law=docs/HISTORY_GOVERNANCE.md+operating_protocol.md (đã có), config=.aof_policy.json (đã có), outcomes=~/.aof/audit.jsonl+decisions.jsonl+errors.jsonl (đã có/F3-1), eval=verify_gate (đã có, cần fixture riêng cho policy-tuning), người duyệt=session_log needs_approval (đã có). `improve_ledger` cũ nằm ở "adapter NP_AI" (docs/REWIRE_MAP_AOF_SKILL.md nhóm 2) — KHÔNG đưa logic Asana/cmux vào core, core chỉ cung cấp cơ chế đề xuất+eval.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm lệnh `aof improve-check` (CLI, core-only, không đụng Asana) đọc op_log 168h + errors.jsonl, đề xuất ĐÚNG 1 thay đổi policy (vd nâng/hạ 1 ngưỡng trong .aof_policy.json) kèm lý do trích từ số liệu thật, KHÔNG tự ghi — chỉ in đề xuất + gọi session_log event=needs_approval.

Bước 1: Đọc lại ExecPlan gốc mục F3 điểm 5 + docs/REWIRE_MAP_AOF_SKILL.md nhóm 2 để không lấn sang phần đã chủ đích để ở adapter NP_AI (Asana/cmux/ceo_inbox).
  Báo: xác nhận ranh giới — core chỉ đề xuất + eval, KHÔNG tự merge, KHÔNG gọi Asana.

Bước 2: Implement hàm `propose_policy_change()` trong core/oplog.py (hoặc file core/improve.py mới):
  ```python
  # === propose_policy_change ===
  def propose_policy_change(window_hours: float = 168) -> dict[str, Any]:
      """Đọc op_log window + errors.jsonl, đề xuất ĐÚNG 1 thay đổi policy.

      Không tự ghi .aof_policy.json — chỉ trả đề xuất kèm bằng chứng.
      Nếu không đủ dữ liệu → trả {"proposal": None, "reason": "CHƯA ĐỦ DATA"}.
      """
      digest = build_digest(since_ts=time.time() - window_hours * 3600)
      # ví dụ luật: verify_fail_rate cao bất thường cho 1 task → đề xuất
      # nới/siết multi_trial_min; không bịa nếu mẫu quá nhỏ (n < 5)
      ...
  # === END propose_policy_change ===
  ```

Bước 3: Verify
  Fixture 3 ca: (a) đủ dữ liệu rõ ràng → có đề xuất kèm số liệu trích dẫn, (b) dữ liệu mỏng (n<5) → trả "CHƯA ĐỦ DATA", không bịa, (c) không có gì bất thường → trả proposal=None. `aof improve-check` không bao giờ tự ghi file policy.

EVIDENCE REQUIRED:
  1. Test 3 fixture case trên đều đúng hành vi
  2. `aof improve-check` chỉ IN đề xuất + gọi needs_approval, không tự merge (grep code xác nhận không có write vào .aof_policy.json trong core/improve.py)
  3. pytest toàn repo xanh
  STOP và báo CEO nếu phát hiện cần dữ liệu ngoài core (Asana/cmux) — đúng ranh giới adapter, dừng lại hỏi thay vì tự lấn.
--- END PROMPT ---

==========================================================================
CHECKPOINT 4 · F4 + F5 — WORKER CONTROL + CI
==========================================================================

--------------------------------------------------------------------------
TASK F4-0: docs/WORKER_CONTROL_VI.md — 4 luật đo được, 1 trang    [TODO] Docs · Priority: MED
--------------------------------------------------------------------------
Mục tiêu: chuẩn 1 trang cho 4 luật kiểm soát worker, tách riêng khỏi việc thêm policy key (F4-1) vì đây là tài liệu, không phải code.
Lý do: ExecPlan F4 acceptance đòi rõ "doc 1 trang" như một sản phẩm riêng, không lẫn vào commit code.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Viết docs/WORKER_CONTROL_VI.md (<=50 dòng) mô tả 4 luật: (1) giao việc = contract C 7 dòng + DoD-cmd, (2) canh bằng output (worker_watch mtime), không tin session, (3) worker không tự chấm — orchestrator chạy verify_gate+audit_scope, (4) đo hiệu quả per-task qua op_log --task.

Bước 1: Đọc docs/OPERATOR_WORKFLOW_VI.md để giữ đúng văn phong/format các doc VI hiện có trong repo.

Bước 2: Viết doc theo 4 mục trên, mỗi mục có 1 ví dụ lệnh CLI thật (aof watch, aof log --task, verify_gate, audit_scope).

Bước 3: Verify
  `wc -l docs/WORKER_CONTROL_VI.md` <= 50 dòng; đọc lại đảm bảo mỗi luật có ví dụ lệnh chạy được thật (không phải giả định).

EVIDENCE REQUIRED:
  1. File tồn tại, <=50 dòng
  2. Mỗi luật trong 4 luật có ít nhất 1 lệnh CLI thật trích từ core/cli.py
  3. Không mâu thuẫn với core/heartbeat.py::DEFAULT_STALE_AFTER_S hiện có
  STOP và báo CEO nếu 4 luật cần đổi (đây là tài liệu hoá luật đã có trong ExecPlan, không phải tự nghĩ luật mới).
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F4-1: policy key worker_stale_after_s (code, sau khi F4-0 có doc)    [TODO] Core · Priority: MED
--------------------------------------------------------------------------
Mục tiêu: cho phép override ngưỡng "worker treo" qua policy thay vì hardcode 300 trong heartbeat.py.
Lý do: ExecPlan F4 — worker canh bằng output (mtime), không tin session sống; ngưỡng phải cấu hình được per-workspace.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Thêm `worker_stale_after_s` (mặc định 300, theo khuôn `DEFAULT_STALE_AFTER_S` trong core/heartbeat.py) vào `_workspace_policy()` defaults trong mcp_server.py.

Bước 1: Đọc core/mcp_server.py dòng 803-808 (nhánh worker_watch hiện tại dùng heartbeat_mod.DEFAULT_STALE_AFTER_S) để nối đúng policy key mới vào đó thay vì hardcode.

Bước 2: Sửa nhánh worker_watch dùng `int(a.get("stale_after_s") or _workspace_policy().get("worker_stale_after_s") or heartbeat_mod.DEFAULT_STALE_AFTER_S)` — thứ tự ưu tiên: tham số gọi > policy > default cứng.

Bước 3: Verify
  Policy key mới có test trong tests/test_policy_compat.py; test cả 3 nhánh ưu tiên (param/policy/default).

EVIDENCE REQUIRED:
  1. Test policy mới: worker_stale_after_s đọc đúng từ .aof_policy.json, fallback đúng default 300
  2. Không đổi semantics DEFAULT_STALE_AFTER_S hiện có (vẫn 300, chỉ thêm override)
  3. pytest toàn repo xanh
  STOP và báo CEO nếu cần đổi giá trị mặc định 300 (ExecPlan chỉ định thêm override, không đổi default).
--- END PROMPT ---

--------------------------------------------------------------------------
TASK F5-1: .github/workflows/ci.yml — ruff + pytest ma trận 3.10-3.12    [TODO] CI · Priority: LOW
--------------------------------------------------------------------------
Mục tiêu: chặn hồi quy cho toàn bộ F1-F4 vừa build, chạy trên push/PR.
Lý do: ExecPlan F5 — kéo từ ASSESSMENT_20260721.md, một trong 4 thứ vành đai trước publish.

--- COPY PROMPT NÀY CHO AGENT ---
Nhiệm vụ: Tạo .github/workflows/ci.yml — matrix python-version [3.10, 3.11, 3.12], steps: checkout, setup-python, pip install ruff pytest, ruff check core/ tests/, pytest -q.

Bước 1: Không có workflow nào tồn tại hiện tại (.github/workflows/ chưa có) — tạo mới hoàn toàn, không sửa release/publish.

Bước 2: Viết YAML chuẩn actions/checkout@v4 + actions/setup-python@v5, trigger on: [push, pull_request].

Bước 3: Verify
  YAML lint sạch (yamllint nếu có, hoặc python -c "import yaml; yaml.safe_load(open(...))" để parse thử).

EVIDENCE REQUIRED:
  1. File .github/workflows/ci.yml parse được bằng yaml.safe_load
  2. Không đụng gì tới release/publish workflow (không có file nào khác bị sửa)
  3. Ma trận đúng 3 phiên bản Python như ExecPlan yêu cầu
  STOP và báo CEO nếu cần thêm secret/token — CI chỉ chạy ruff+pytest, không cần credential nào.
--- END PROMPT ---

## PHẦN 6 — SESSION END PROTOCOL

Thứ tự bắt buộc cuối mỗi checkpoint (tối thiểu 4 lệnh):
1. `python3.10 -m ruff check core/ tests/` — phải "All checks passed!"
2. `python3.10 -m pytest -q` — phải 0 fail, số bài không được giảm so với PHẦN 3
3. `git status --short` + `git diff --stat` — xác nhận đúng file trong scope, không lệch
4. Gọi MCP tool `session_handoff` (host-side, aof-operations plugin) — sinh handoff+recap mới cùng stamp, cập nhật PHẦN 3/4 của file này với số liệu mới

## PHẦN 7 — NGUYÊN TẮC BẤT BIẾN

1. Không nới lỏng bất kỳ gate nào để test dễ pass.
2. Index/errors: một writer một schema — phát hiện writer thứ hai → dừng, hỏi CEO.
3. Mọi lỗi mới phát hiện trong lúc build → ghi errors.jsonl NGAY, sửa kèm test.
4. Không sửa skill /aof đang sống khi chưa smoke; không đổi semantics lanes/wave2 4-trạng-thái.
5. Mọi thay đổi hướng sản phẩm phải cite History Gate (docs/HISTORY_GOVERNANCE.md) trước khi viết code.
6. Canonical duy nhất = repo này, mọi đăng ký MCP/CLI dùng đường dẫn tuyệt đối, không bao giờ `-m core.*` từ cwd khác.
7. STOP và báo CEO nếu bất kỳ test cũ nào đỏ không giải thích được.

## PHẦN 8 — CÁCH DÙNG

Hội thoại mới — paste 2 dòng:
  "Đọc file docs/plans/AOF_V04_AUTOHANDOFF_CONTEXT.md
   Task tiếp theo: F1-1 — Sửa session_handoff/session_recap dùng repo_identity"

Sau mỗi task xong:
  - Đổi [TODO] → [DONE] trong Phần 5
  - Cập nhật Phần 3 baseline với số mới (chạy PHẦN 6 trước khi cập nhật)
  - Ghi timestamp dòng "Last updated" đầu file

Task tiếp theo ngay bây giờ: F1-1 — Sửa session_handoff/session_recap dùng repo_identity thay vì AOF_WORKSPACE
Prompt sẵn ở Phần 5, mục TASK F1-1. Copy prompt, paste vào agent, done. (Điều kiện tiên quyết: CEO gỡ .git/index.lock trên máy thật trước — chưa commit được F2.)

---
*AOF v0.4 Master Context v1 — 2026-07-21 06:58*
*Plain text. Không click. Agent đọc thẳng. CEO paste 2 dòng là tiếp tục.*
