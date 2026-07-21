# Bản đồ repo — đọc từ đây, không còn rời rạc

*Repo này là NƠI DUY NHẤT phát triển sản phẩm AOF (production, dài hạn).
Mọi tri thức sản phẩm nằm ở đây; dữ liệu vận hành riêng tư của workspace
NP_AI (Asana, cmux, artifact nội bộ) KHÔNG copy vào — chỉ chưng cất và trỏ.*

## Người dùng đọc gì

| Bạn là | Đọc |
|---|---|
| Người dùng mới (không code) | `QUICKSTART_VI.md` → `VONG_LAP_NO_CODE_VI.md` |
| Người vận hành hằng ngày | `OPERATOR_WORKFLOW_VI.md` → `ENGINEERING_WORKFLOW.md` (kỹ thuật) |
| Dev / reviewer / agent | **`ARCHITECTURE.md`** → `HISTORY_GOVERNANCE.md` → `DOCUMENT_GOVERNANCE.md` |
| Người phát triển AOF | History Gate trước mọi thay đổi semantics; `CONTRIBUTING.md` ở root |
| Wave v0.4 đang chạy | `plans/AOF_V04_AUTOHANDOFF_EXECPLAN_20260721.md` + `plans/AOF_V04_AUTOHANDOFF_CONTEXT.md` (đối chiếu ARCHITECTURE nếu COPY PROMPT lệch) |

## Cấu trúc

```
core/           động cơ: preflight, contract, gates, lease, lanes,
                mcp_server (TOOLS catalog — đếm động), doctor, oplog, heartbeat
adapters/       tracker adapters (Asana) — không phải lõi portable
tests/          unit + adversarial + policy-compat + lanes + E2E + multirepo
docs/
  ARCHITECTURE.md             lớp, ranh giới, identity write vs key
  ENGINEERING_WORKFLOW.md     vòng dev + self-improve + stop rules
  DOCUMENT_GOVERNANCE.md      luật docs production (chống stale/landmine)
  HISTORY_GOVERNANCE.md       5 luật History Gate
  QUICKSTART_VI.md            5 phút bắt đầu
  VONG_LAP_NO_CODE_VI.md      9 bước máy + nghiệm thu
  OPERATOR_WORKFLOW_VI.md     vòng vận hành hằng ngày
  WORKER_CONTROL_VI.md        4 luật kiểm soát worker (đo được)
  PRODUCT_DIRECTION_V03.md    định hướng sản phẩm
  REWIRE_MAP_AOF_SKILL.md     strangler /aof → core
  PLAN_REVIEW_STANDARD.md     chuẩn review plan
  ASSESSMENT_*.md             thẩm định có bằng chứng
  EFFECTIVENESS_SMOKE_*.md    smoke WITH vs WITHOUT AOF (không phải bench n≥30)
  history/INDEX.md            dòng thời gian (chưng cất)
  decisions/                  decision records
  plans/                      ExecPlan + context (working; có thể STALE)
  examples/                   mẫu recap
```

## Sự thật vận hành (đối chiếu được)

Mọi claim trong docs đối chiếu bằng lệnh trong **repo này**:

```bash
python3 -m pytest -q
ruff check core/ tests/
PYTHONPATH=. python3 -m core.doctor --json   # từ canonical tree
```

Claim đo lường công bố: README “Measured results” trong đúng ràng buộc
CAUSAL-VERDICT 2026-07-16. Không hardcode số MCP tools trong prose — xem
`len(TOOLS)` / output doctor.
