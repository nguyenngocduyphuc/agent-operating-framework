# DR 2026-07-20 — Repo canonical duy nhất + hướng no-code operator

## Quyết định

1. **Repo này (`agent-operating-framework`) là AOF canonical duy nhất.**
   Các runtime song song (MCP `operating-framework` cũ trỏ `npflight_mcp.py`,
   bản copy ở root `core/`, repo standalone cũ, bản incubate) là nợ vận hành —
   migrate về đây rồi khai tử. Kiến trúc: `một core portable → adapter per workspace`.
2. **Người dùng đích mở rộng thành cá nhân no-code.** Mọi tool phải trả lời được
   bằng ngôn ngữ thường; `status_report` là mặt tiền, không bao giờ bị gate.
3. **Định danh repo cho lease = `git rev-parse --git-common-dir`**, không phải
   đường dẫn checkout. Lý do: worktree chung repo phải chung ổ khoá — đặc tả
   ngược lại đã bị bác trong review 2026-07-20 vì gây phân mảnh.
4. **repository-harness: nhận pattern, không merge code.** Harness = lớp ngữ cảnh,
   AOF = lớp cưỡng chế. Hai lớp lắp chồng được trên cùng một repo.

## Bối cảnh

Audit sâu 2026-07-20 (codex, được xác minh độc lập) tìm thấy 3 P0 trong lớp
kiểm soát của workspace NP_AI: false-success khi cứu log dispatcher,
DoD thực thi shell từ output của worker, và không có khoá nhiệm vụ (3 lần
trong một ngày hai phiên giẫm chân). Core AOF trong repo này đã fail-closed
đúng chỗ (verify allowlist, git inventory tin cậy, TOCTOU check) nhưng thiếu
lease, thiếu policy compat, thiếu mặt tiền cho người không kỹ thuật.

## Hệ quả

- Mọi tính năng chống-giẫm-chân, chống-fail-open đi vào core (mọi workspace hưởng).
- Cơ chế fleet-specific (tmux, cứu log, heartbeat watchdog) ở adapter NP_AI,
  nhưng nguyên tắc "evidence artifact ≠ deliverable" và "đo heartbeat bằng
  log size/mtime" là chuẩn chung ghi trong docs.
- Publish (do anh Nam quyết) chỉ sau khi: P0 workspace đóng, policy v2 có
  compat test, bench có số n≥30.

## Bằng chứng tại thời điểm quyết định

- 80 → 100 tests pass, ruff clean, nhánh `feat/aof-v03-nocode-ops`.
- Xác minh audit: commit nhiễm `551c9259c` (7.558 file), worktree sạch tại
  `51be94ece`, policy mismatch v1/v2 tái hiện được bằng test.
