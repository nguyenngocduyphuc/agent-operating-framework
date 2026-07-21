---
task: AOF v0.4 — auto-handoff đa-repo, error ledger chống tái phạm, chuẩn kiểm soát worker
owner: Pham Duc Phuong Nam (thực thi: phiên Claude Code mới)
scope: core/oplog.py, core/mcp_server.py, core/cli.py, core/preflight.py, core/lease.py (đọc identity), tests/, docs/, .github/workflows/ (mới), adapter NP_AI: scripts/aof_resume.sh + hook SessionStart (file mới, ngoài vendor)
dod: handoff/recap ghi vào repo đang làm việc + index tập trung ~/.aof/handoffs/index.jsonl; `aof resume` in RESUME BRIEF không cần copy-paste; session_handoff tự kèm recap cùng timestamp; errors.jsonl + preflight cảnh báo tái phạm + lessons liệt kê lỗi thiếu test_ref; policy worker_stale_after_s + doc chuẩn worker; CI ruff+pytest 3.10-3.12 xanh; toàn bộ test cũ vẫn xanh
do_not: sửa skill /aof đang sống khi chưa smoke; đổi semantics lanes/wave2-4-trạng-thái; đưa cmux vào core (cmux = adapter); push remote; hardcode số tool
stop_if: bất kỳ test cũ nào đỏ không giải thích được; index ghi được nhưng resume đọc sai repo; thay đổi đòi đụng NP_AI scripts ngoài aof_resume.sh + hook
return: commit trên feat/aof-v03-nocode-ops, tests xanh kèm số, smoke 2 môi trường, handoff + recap của chính phiên đó sinh bằng tool mới
references: docs/history/INDEX.md; docs/HISTORY_GOVERNANCE.md (History Gate — ĐỌC TRƯỚC); docs/ALIGNMENT_WITH_HISTORY_20260720.md; CAUSAL-VERDICT-20260716 (workspace); docs/ASSESSMENT_20260721.md; docs/sessions/HANDOFF_20260721_064104.md
---

# ExecPlan — AOF v0.4: bàn giao tự động, không tái phạm lỗi, worker chính xác

## GOAL

Đóng vòng bàn giao: một lệnh sinh trọn bộ (handoff + recap cùng timestamp),
lưu đúng repo đang làm, tra được từ một index, phiên mới tự nạp — CEO không
bao giờ phải copy-paste bàn giao nữa. Kèm: lỗi thật không được phép lặp lại.

## Tính năng 1 — Handoff đúng vị trí khoa học (đa-repo) + resume tự động

Vấn đề: AOF phục vụ nhiều repo/worktree; hiện handoff luôn ghi vào
AOF_WORKSPACE — sai chỗ khi làm trong repo con, và không có chỗ tra tập trung.

Thiết kế (2 tầng, ponytail):
1. **File nằm cạnh code**: `session_handoff`/`session_recap` ghi vào
   `<repo-đang-bound>/docs/sessions/` — repo xác định bằng đúng identity của
   lease (`git rev-parse --git-common-dir` từ bound_cwd; fallback AOF_WORKSPACE).
2. **Con trỏ nằm một chỗ**: mỗi lần ghi, append 1 dòng vào
   `~/.aof/handoffs/index.jsonl`: `{ts, repo_identity, repo_key, branch, task,
   handoff_path, recap_path, summary{sessions,done,blocked,collisions}}`.
   Append-only, một writer một schema.
3. **`aof resume`** (CLI + MCP tool thứ 13): `--task X | --repo <path> |`
   (mặc định: mới nhất). Đọc index → in **RESUME BRIEF**: nội dung handoff +
   luật bắt buộc + lệnh làm tiếp. Phiên mới chỉ gọi 1 tool — hết thủ công.
4. **Adapter NP_AI (ngoài vendor)**: `scripts/aof_resume.sh` đọc index chọn
   bản mới nhất → `cmux open` đúng workspace + đổ RESUME BRIEF làm prompt mồi;
   hook SessionStart gọi `aof resume --brief` để Claude Code tự nạp.
   cmux KHÔNG vào core.

Acceptance: làm việc trong repo A → file nằm trong A/docs/sessions; index có
dòng mới; `aof resume --task` trả đúng brief; test đa-repo (2 repo giả lập).

## Tính năng 2 — Handoff luôn kèm recap + timestamp

`session_handoff` tự sinh recap CÙNG stamp, link chéo ngay đầu file md
("Recap: ./RECAP_<stamp>.html"), cả hai vào chung 1 dòng index. Một lệnh =
trọn bộ bàn giao. Acceptance: gọi session_handoff → 2 file cùng stamp + link.

## Tính năng 3 — Error ledger: thống kê lỗi, kích hoạt không tái phạm

Nguyên liệu thật 2 ngày qua: 5 lỗi (2 fail-open, 3 shadow-import) — từng cái
đã thành test. Nay thành CƠ CHẾ:
1. `~/.aof/errors.jsonl`: `{ts, fingerprint, title, session, fix_commit,
   test_ref, status}` — fingerprint = chuỗi chuẩn hoá loại lỗi (vd
   `shadow-import:core`, `fail-open:policy-rename`).
2. Ghi qua `session_log` event `error` (fields trên trong data) — không thêm
   tool mới.
3. **Kích hoạt không tái phạm**: preflight đọc errors.jsonl, WARN khi có lỗi
   `status != closed` hoặc fingerprint lặp ≥2 lần; một lỗi CHỈ được đóng khi
   có `test_ref` (đường dẫn test chống tái phạm) — "mỗi lỗi thật → một test
   vĩnh viễn" thành luật máy kiểm.
4. `aof lessons`: liệt kê lỗi mở + lỗi thiếu test_ref (= nợ kỹ thuật hàng đầu).
5. Engineering loop cải tiến chính AOF: nhịp tuần = `op_log 168h` + `aof
   lessons` → đề xuất vào improve_ledger (adapter đã có) → việc được chọn phải
   qua đúng vòng 9 bước của chính AOF (dogfood).

Acceptance: seed 2 lỗi → preflight warn đúng; đóng lỗi thiếu test_ref bị từ
chối; lessons liệt kê đúng.

## Tính năng 4 — Kiểm soát worker hiệu quả & chính xác nhất

Chuẩn hoá thành 4 luật đo được (docs/WORKER_CONTROL_VI.md + policy):
1. **Giao việc = contract C 7 dòng + DoD-cmd** — worker nhận việc kèm lệnh
   chứng minh; không có DoD-cmd chạy được thì không giao.
2. **Canh bằng output, không tin session**: `worker_watch` với ngưỡng policy
   `worker_stale_after_s` (mặc định 300); stale → dừng/khởi động lại, không chờ.
3. **Worker không tự chấm**: orchestrator chạy `verify_gate dod` +
   `audit_scope`; output worker chỉ là dữ liệu, không bao giờ là lệnh.
4. **Đo hiệu quả per-task**: `op_log --task` (verify fail rate, số lần bị
   chặn) — worker/quy trình nào fail nhiều thì lộ ngay trong recap tuần.

Acceptance: policy key mới có test; doc 1 trang; op_log --task hiển thị đủ.

## Tính năng 5 — CI (kéo từ ASSESSMENT, chặn hồi quy cho mọi thứ trên)

`.github/workflows/ci.yml`: ruff + pytest, ma trận Python 3.10/3.11/3.12,
chạy trên push/PR. Không đụng release/publish (v0.4 sau).

## EXECUTION ORDER

1. History Gate: đọc references trước khi viết dòng code nào.
2. F2 (recap kèm handoff) — nhỏ nhất, mở đường index.
3. F1 (đa-repo + index + resume) — lõi wave.
4. F3 (error ledger) — dùng index/oplog vừa chuẩn hoá.
5. F4 (worker doc + policy) + F5 (CI).
6. Verify toàn bộ + smoke 2 môi trường + tự sinh handoff/recap bằng tool mới.

## VERIFICATION

```text
ruff check core/ tests/
.venv/bin/python -m pytest -q          # (>=140 kỳ vọng, 0 fail)
printf '<initialize+tools/list>' | python <abs>/core/mcp_server.py  # đủ 13 tools
aof resume --task <task-test>           # in đúng RESUME BRIEF
smoke Cowork: gọi session_handoff qua plugin → file vào đúng repo + index
```

## STOP RULES

- Không nới lỏng bất kỳ gate nào để test dễ pass.
- Index/errors: một writer một schema — phát hiện writer thứ hai → dừng, hỏi CEO.
- Mọi lỗi mới phát hiện trong lúc build → ghi errors.jsonl NGAY, sửa kèm test.
