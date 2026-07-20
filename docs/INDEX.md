# Bản đồ repo — đọc từ đây, không còn rời rạc

*Repo này là NƠI DUY NHẤT phát triển sản phẩm AOF (production, dài hạn).
Mọi tri thức sản phẩm nằm ở đây; dữ liệu vận hành riêng tư của workspace
NP_AI (Asana, cmux, artifact nội bộ) KHÔNG copy vào — chỉ chưng cất và trỏ.*

## Người dùng đọc gì

| Bạn là | Đọc |
|---|---|
| Người dùng mới (không code) | `QUICKSTART_VI.md` → `VONG_LAP_NO_CODE_VI.md` |
| Người vận hành hằng ngày | `OPERATOR_WORKFLOW_VI.md` |
| Dev tích hợp / reviewer | `../README.md` → `ALIGNMENT_WITH_HISTORY_20260720.md` → `decisions/` |
| Người phát triển AOF | **BẮT BUỘC** `HISTORY_GOVERNANCE.md` (History Gate) trước mọi thay đổi |

## Cấu trúc

```
core/           động cơ: preflight, contract(+Karpathy), gates, lease, lanes,
                mcp_server (8 tools), doctor, oplog (log/recap/handoff), heartbeat
adapters/       tracker adapters (Asana)
tests/          132 test: unit + adversarial + policy-compat + lanes
                + no-shadow-import + E2E user journey (hành trình 9 bước thật)
docs/
  QUICKSTART_VI.md            5 phút bắt đầu, không cần biết code
  VONG_LAP_NO_CODE_VI.md      9 bước máy tự chạy + điều kiện nghiệm thu
  OPERATOR_WORKFLOW_VI.md     vòng vận hành + bảng giá trị đo được
  PRODUCT_DIRECTION_V03.md    định hướng sản phẩm
  ALIGNMENT_WITH_HISTORY_*.md đối chiếu với toàn bộ lịch sử /aof
  HISTORY_GOVERNANCE.md       5 luật quản trị lịch sử (History Gate)
  REWIRE_MAP_AOF_SKILL.md     strangler map skill /aof → core
  history/INDEX.md            dòng thời gian sản phẩm (chưng cất, trỏ nguồn)
  decisions/                  decision records
  examples/recap_example.html recap HTML mẫu (sinh từ dữ liệu thật)
```

## Sự thật vận hành (đối chiếu được)

Mọi claim trong docs đối chiếu được bằng: `python3 -m pytest` (từ repo này),
`aof doctor`, `aof log`. Claim đo lường: xem README mục "Measured results" —
trong đúng ràng buộc trung thực đã khóa tại CAUSAL-VERDICT 2026-07-16.
