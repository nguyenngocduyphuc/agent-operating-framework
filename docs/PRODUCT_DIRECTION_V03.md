# AOF v0.3 — Định hướng sản phẩm: Vận hành tin được cho người không viết code

*Ngày: 2026-07-20 · Trạng thái: đang thực thi · Chủ sở hữu: Phạm Đức Phương Nam*

## Luận điểm

AOF không phải orchestrator. AOF là **lớp tin cậy vận hành** (operational trust layer)
đứng trước mọi orchestrator: fail-closed preflight, khoá nhiệm vụ độc quyền,
kiểm chứng do máy sở hữu, và báo cáo trung thực bằng ngôn ngữ thường.

Bài học đắt nhất (audit 2026-07-20, NP_AI workspace): **cả ba lỗ hổng nghiêm trọng
đều nằm trong chính lớp kiểm soát** — dispatcher tự chế false-success, DoD chạy
shell do worker cung cấp, không có gì chặn hai phiên cùng ghi một nhiệm vụ.
Framework chỉ có giá trị khi nó tự chịu được thử phá.

## Người dùng đích

Cá nhân vận hành **không biết git, không biết tracker, không biết test**.
Họ cần trả lời được 4 câu, không cần hiểu công cụ:

1. Máy đang làm gì cho tôi?
2. Đã xong chưa — và lấy gì làm bằng chứng?
3. Nếu chưa xong, kẹt ở đâu, tôi phải làm gì?
4. Có ai/phiên nào đang giẫm chân nhau không?

Chính người dùng kỹ thuật cũng cần lớp này — vì báo cáo sai lệch xảy ra
với cả người biết test (đã chứng minh bằng chính vận hành NP_AI).

## Ba trụ v0.3 (đã ship trong nhánh này)

1. **Task lease (C2 portable)** — `core/lease.py`. Một nhiệm vụ, một phiên sống.
   Định danh repo bằng `git rev-parse --git-common-dir` nên mọi worktree của cùng
   repo dùng chung một ổ khoá (bài học đặc tả C6 bị bác). Phiên chết → lease
   stale → phiên sau takeover có ghi vết. Phiên sống → từ chối thẳng, nói rõ ai giữ.
2. **Policy compat v1→v2** — khoá cũ (`require_asana_task`, `require_ponytail`)
   được honour + cảnh báo di trú, không bao giờ fail-open câm lặng khi đổi schema.
3. **`status_report`** — tool MCP thứ 8: báo cáo 4 trạng thái bằng tiếng Việt/Anh
   thường (Bị chặn / Đang chuẩn bị / Sẵn sàng / Xong-có-bằng-chứng), luôn kèm
   "Bước tiếp theo". Không bao giờ bị gate — người bị chặn cần thấy lý do nhất.

## Tích hợp repository-harness (quyết định)

`hoangnb24/repository-harness` là lớp **ngữ cảnh** (AGENTS.md shim, product
contract, story packets, TEST_MATRIX, decision records). AOF là lớp **cưỡng chế**.
Không merge code (Rust vs Python), chỉ nhận pattern:

- Installer 1 lệnh với `--merge/--override/--dry-run` (roadmap v0.4 cho `setup.sh`).
- 4 trạng thái plain-language → đã thành `status_report`.
- Decision records → `docs/decisions/` trong repo này.
- Tương thích: repo đã cài harness thì AOF đọc được AGENTS.md shim như protocol nguồn.

## Roadmap

| Phase | Nội dung | Điều kiện chuyển |
|---|---|---|
| v0.3 (nhánh này) | lease + policy compat + status_report | test + adversarial xanh |
| v0.3.1 | heartbeat cho worker (log size/mtime, không tin "session sống") — bài học watchdog mù 18 phút | v0.3 merge |
| v0.4 | installer no-code 1 lệnh; policy schema v2 chính thức + `aof doctor` | pilot 3 người dùng no-code |
| v0.5 | AOF-Bench n≥30, publish số liệu — bench chính là marketing | v0.4 ổn định |
| v1.0 | đóng gói plugin (MCP server + skill + policy mẫu); anh Nam publish | bench chứng minh giá trị |

## Điều KHÔNG làm

- Không làm orchestrator, không quản lý fleet — đó là việc của adapter (NP_AI scripts).
- Không claim ROI khi bench n<30 mỗi arm.
- Không phát hành public khi còn bất kỳ P0 nào mở trong lớp kiểm soát.
- Không nuôi nhiều bản AOF: repo này là canonical duy nhất; mọi runtime khác
  (npflight_mcp cũ, bản copy root, incubate) phải migrate về đây rồi khai tử.
