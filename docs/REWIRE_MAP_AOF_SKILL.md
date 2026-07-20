# Bản đồ rewire skill /aof → core canonical (strangler, không lãng phí)

*2026-07-21. Nguyên tắc: mặt tiền `/aof` (CEO gõ tiếng Việt) GIỮ NGUYÊN.
Chỉ đổi động cơ từng nghiệp vụ từ MCP cũ (`scripts/npflight_mcp.py`) sang core
mới, khi và chỉ khi core đạt parity cho nghiệp vụ đó. MCP cũ chạy song song
đến khi cutover xong — không tắt sớm, không mất nghiệp vụ nào.*

## Nhóm 1 — Core mới ĐÃ có, rewire được ngay (shadow trước, cutover sau)

| Nghiệp vụ /aof | MCP cũ | Core mới | Ghi chú |
|---|---|---|---|
| `/aof check` | preflight | `preflight` (+ lease, + lane) | core mới THÊM khoá nhiệm vụ + làn |
| `/aof contract` | check_contract | `check_contract` | cùng 7 trường (= contract C thắng bench) |
| `/aof verify` | verify_gate | `verify_gate` | core mới có venv-python + dod gate |
| `/aof scope` | audit_scope | `audit_scope` | core mới dùng git inventory tin cậy + TOCTOU |
| `/aof evidence` | post_evidence | `post_evidence` | core mới thêm lane lite theo GO-RISK-LANE |
| `/aof rules` | operating_protocol | `operating_protocol` | tương đương |
| `/aof log <event>` | session_log | `session_log` | core mới thêm needs_approval/approved |
| (mới) trạng thái | — | `status_report` | wave2 4 trạng thái, thay cho việc CEO tự đọc JSON |
| (mới) nhật ký ngày | — | CLI `aof log` | thay cho đọc audit.jsonl tay |
| (mới) canh worker | — | CLI `aof watch` | thay watchdog session-alive |
| (mới) sức khoẻ cài đặt | — | CLI `aof doctor` | 6 probe thật |

## Nhóm 2 — Ở LẠI adapter NP_AI (fleet/business-specific, không vào core)

`/aof improve` (improve_ledger), `/aof skill` (skill health), `/aof ws`
(workspace map/names, cmux), `/aof plan` + `/aof duyệt` (ceo_inbox, plan-gate),
`/aof gate` (verify_gates registry), `/aof wt` (wt.py), `/aof ledger`
(ship_ledger → Asana), `/aof artifacts` (artifact_index), `/aof pin`
(dispatch pin). Lý do: gắn Asana/cmux/console — đúng kiến trúc
"core portable + NP_AI adapter". Adapter nên gọi core cho phần gate.

## Nhóm 3 — Đã retire, không mang sang

`verify_worker_output`, `pack_context` (retired 2026-07-13, 0 usage).

## Trình tự cutover an toàn

1. Đăng ký core mới SONG SONG dưới tên `aof` (MCP cũ giữ tên `operating-framework`).
2. Skill /aof: thêm ghi chú "nghiệp vụ nhóm 1 ưu tiên server `aof`, fallback cũ".
3. Chạy shadow ≥2 ngày vận hành thật; so audit hai bên bằng `aof log`.
4. Parity đạt → đổi bảng nghiệp vụ nhóm 1 sang server mới; MCP cũ chỉ còn nhóm 2.
5. Sau 1 tuần sạch: gỡ handler nhóm 1 khỏi npflight_mcp.py (adapter gọi core).

## Điều kiện dừng (stop-if)

- Bất kỳ nghiệp vụ nào lệch kết quả giữa 2 server → dừng cutover, ghi sổ improve.
- audit schema: core mới ghi schema v2 thống nhất; nếu tool nào còn ghi schema
  cũ vào cùng file → chặn cutover (tránh lặp lỗi 3-schema đã phát hiện 17/07).
