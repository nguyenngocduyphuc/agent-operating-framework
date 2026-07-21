# HANDOFF.md — AOF v0.4 (Auto-Handoff / Self-Improve)
Generated: 2026-07-21 | From: Claude (Cowork) | To: Grok (audit + complete)

## Project Overview
- Dự án: `vendors/agent-operating-framework` (AOF) — portable preflight/gate/contract-enforcement MCP server + CLI cho AI-agent workspaces.
- Repo canonical: local checkout tại đường dẫn trên (không phải NP_AI_macos root).
- Branch: `feat/aof-v03-nocode-ops`.
- Mục tiêu phiên này: nâng cấp v0.4 theo `docs/plans/AOF_V04_AUTOHANDOFF_EXECPLAN_20260721.md` — 5 feature: F1 multi-repo handoff+index+resume, F2 handoff auto-recap, F3 error ledger + self-improve loop, F4 worker control, F5 CI.
- **Vai trò của Grok trong lần bàn giao này: audit lại toàn bộ những gì Claude đã làm (đặc biệt phần tự-verify), rồi hoàn thiện các task còn lại (danh sách ở "Next Actions").**

## Decisions Already Made
1. **F1-1 dùng `nearest_repo()` (core/preflight.py), KHÔNG dùng `repo_identity()` (core/lease.py)** để xác định nơi ghi `docs/sessions/`. Lý do: `repo_identity()` trả về đường dẫn `.git/` (đúng cho lease-hashing, nhưng ghi file vào đó sẽ lọt vào `.git/docs/sessions/` — bug thật, Claude tự bắt được khi verify). `nearest_repo()` trả về working-tree root, tôn trọng worktree.
2. **F2 (`session_handoff`) luôn sinh cặp file cross-link**: `HANDOFF_<stamp>.md` + `RECAP_<stamp>.html`, cùng stamp `%Y%m%d_%H%M%S`. Áp dụng cả cho MCP tool và CLI (`aof handoff`/`aof recap`) — trước đây CLI dùng format stamp khác (`%Y%m%d_%H%M`), đã hợp nhất.
3. **F3-4 (self-improve loop) gộp vào F3, KHÔNG tách F6/v0.5.** Lý do: ExecPlan gốc đã cam kết "improve_ledger, nhịp tuần" ở F3 điểm 5 — gộp không phải mở rộng scope. Kiến trúc tham chiếu: bài X/Twitter của Nicolas Finet (nifinet) — AGENTS.md=law, config file hiển thị=scoring.yaml, outcomes log có field `reason` (không chỉ pass/fail), eval gate với ugly-case fixtures, MỘT thay đổi mỗi lần đề xuất, PR cho người duyệt, nhịp tuần không phải mỗi sự kiện.
4. **Ranh giới bắt buộc cho self-improve (F3-4)**: theo `docs/REWIRE_MAP_AOF_SKILL.md`, improve_ledger thuộc "Nhóm 2 — Ở LẠI adapter NP_AI" — core AOF chỉ được ĐỀ XUẤT + eval, KHÔNG được tự merge/tự ghi `.aof_policy.json`, KHÔNG được đụng Asana/cmux. Mọi thay đổi chính sách phải qua `session_log needs_approval` để người duyệt.
5. **Plan review bắt buộc dùng skill canonical `unified-roadmap-architect`** (tương đương `deliverable-factory` — kho skill riêng của anh Nam, KHÔNG sync vào Cowork), validate bằng `scripts/validate_output.py` của chính skill đó — KHÔNG tự bịa khung HTML review. Xem `docs/PLAN_REVIEW_STANDARD.md`.

## Tech Stack (confirmed)
- Ngôn ngữ: Python 3 (stdlib-only cho `core/preflight.py`), MCP server qua stdio JSON-RPC 2.0 (`core/mcp_server.py`).
- Test: pytest, harness tự viết `_Client` (subprocess + queue + threading) để nói chuyện với MCP server qua stdio.
- Lint: ruff.
- Không DB, không network ngoài (trừ khi policy yêu cầu credential check).

## Key Findings (verified ngay trước khi bàn giao — 2026-07-21)
- `python3 -m pytest -q` → **136 passed**, 0 fail, 0 flaky trong lần chạy này.
- `python3 -m ruff check core/ tests/` → **All checks passed**.
- `git branch --show-current` → `feat/aof-v03-nocode-ops` (đúng nhánh).
- `.git/index.lock` **vẫn tồn tại**, `rm -f` → `Operation not permitted`. Đây KHÔNG phải stale lock thường (loại đó xóa được). Có khả năng một process ở tầng OS/host đang giữ nó. **Chưa commit được bất kỳ dòng code nào trong toàn bộ phiên làm việc.**
- Bug tự bắt: lần đầu F1-1 dùng sai `repo_identity()` → file lọt vào `.git/docs/sessions/`. Đã sửa + có regression test (`tests/test_multirepo_handoff.py`) chặn tái phát.
- Tìm thấy nguồn gốc file handoff ban đầu (`HANDOFF_20260721_064104.md`) — nó nằm ở `NP_AI_macos/docs/sessions/` (workspace cha), KHÔNG nằm trong repo AOF — chính là bằng chứng sống của bug F1 sửa.

## Open Questions (chưa trả lời)
- [ ] `.git/index.lock` — cần anh Nam kiểm tra ở tầng máy (process nào đang giữ, có phải IDE/Git GUI khác đang mở không). Grok không tự ý force-remove.
- [ ] Có Claude Project riêng tên "Skill & Process Intelligence System" (2026-07-19) cũng nhắm mục tiêu self-improve skill/workflow — chưa đối chiếu được nội dung (Cowork không đọc được Project khác). Cần anh Nam export system prompt + knowledge files của project đó để Grok/Claude đối chiếu, tránh xây trùng.
- [ ] `docs/plans/AOF_V04_AUTOHANDOFF_ROADMAP.html` đang STALE — sinh trước khi F1-1/F1-4 DONE và trước khi thêm F3-4, chưa regenerate lại (cần chạy lại `unified-roadmap-architect` Phase 3 + `validate_output.py`).

## Constraints
- **History Gate**: mọi thay đổi trong AOF phải cite `docs/HISTORY_GOVERNANCE.md`, `docs/history/INDEX.md` trước khi code.
- **Không tự merge chính sách tự-cải-tiến** — F3-4 chỉ đề xuất, người duyệt qua `needs_approval`.
- **Không rời F3-4 khỏi core** sang Asana/cmux — vi phạm REWIRE_MAP Nhóm 2.
- Test cho repo `git init` mới PHẢI checkout feature branch (`git checkout -q -b feat/fixture`) ngay sau `init`, vì preflight coi `main`/`master` là "warn" (không bind `bound_cwd`) chứ không phải "clear".

## Files Created / Modified (chưa commit — nằm trong working tree)
- `core/oplog.py` — thêm `write_session_bundle()` (F2), key `recap_link` trong `_HANDOFF_T`.
- `core/mcp_server.py` — import `nearest_repo`; sửa base dir tính `outdir` cho handoff/recap (F1-1); tách nhánh `session_recap` vs `session_handoff` (F2).
- `core/cli.py` — hợp nhất stamp format, `handoff`/`recap` dùng `write_session_bundle` (F2).
- `tests/test_recap_handoff.py` — 2 test mới cho F2.
- `tests/test_mcp_server.py` — sửa `test_every_tool_answers_with_the_envelope` dùng repo tạm + feature branch, assert đúng thư mục.
- `tests/test_multirepo_handoff.py` — **mới**, 2 test cho F1-4 (multi-repo isolation).
- `docs/plans/AOF_V04_AUTOHANDOFF_CONTEXT.md` — **mới**, Master Context 8-PHẦN (sinh qua `unified-roadmap-architect` Phase 2), chứa đủ COPY PROMPT cho từng task còn lại.
- `docs/plans/AOF_V04_AUTOHANDOFF_ROADMAP.html` — **mới**, Interactive Roadmap (Phase 3), **STALE** (xem Open Questions).
- `docs/PLAN_REVIEW_STANDARD.md` — **mới**, quy chuẩn review plan (đã tự sửa sau khi bị nhắc dùng đúng skill).
- `docs/plans/AOF_V04_AUTOHANDOFF_EXECPLAN_20260721_REVIEW.html` — file review HTML đầu tiên (đã superseded, giữ lại không xóa).

## Next Actions (cho Grok)
1. **[HIGH] Audit trước khi tin bất kỳ dòng nào ở trên** — tự chạy lại `python3 -m pytest -q` và `python3 -m ruff check core/ tests/`, đọc diff thật của 6 file đã sửa, đối chiếu với mô tả trong "Decisions Already Made". Đừng tin báo cáo, verify bằng tool.
2. **[HIGH] F1-2** — `~/.aof/handoffs/index.jsonl` append-only writer. Spec đầy đủ + COPY PROMPT có sẵn trong `docs/plans/AOF_V04_AUTOHANDOFF_CONTEXT.md`, PHẦN 5, TASK F1-2.
3. **[HIGH] F1-3** — `aof resume` CLI subcommand + MCP tool #13. Spec ở CONTEXT.md TASK F1-3.
4. **[MEDIUM] F3-1/F3-2/F3-3** — error ledger (`errors.jsonl` qua `session_log event=error`; preflight WARN khi fingerprint lặp; `aof lessons` command + rule bắt buộc test_ref khi đóng).
5. **[MEDIUM] F3-4** — self-improve loop (`aof improve-check`, `propose_policy_change()`). BẮT BUỘC đọc lại Constraints ở trên trước khi code — sai ranh giới này là vi phạm kiến trúc đã duyệt.
6. **[MEDIUM] F4-0/F4-1** — `docs/WORKER_CONTROL_VI.md` + policy key `worker_stale_after_s`.
7. **[LOW] F5-1** — `.github/workflows/ci.yml` (ruff + pytest matrix Python 3.10–3.12).
8. **[LOW] Regenerate `AOF_V04_AUTOHANDOFF_ROADMAP.html`** sau khi các task trên xong, validate lại bằng `validate_output.py` của `unified-roadmap-architect`.
9. **[BLOCKER — không tự xử lý]** `.git/index.lock` — báo lại cho anh Nam nếu vẫn còn khi Grok bắt đầu; KHÔNG commit thay, KHÔNG force-delete lock mà không hỏi.

## How to Resume
Mở `docs/plans/AOF_V04_AUTOHANDOFF_CONTEXT.md` trước (chứa full spec + COPY PROMPT từng task), đối chiếu với `docs/plans/AOF_V04_AUTOHANDOFF_EXECPLAN_20260721.md` (ExecPlan gốc). Bắt đầu từ Next Actions #1 (audit), sau đó #2 (F1-2).
