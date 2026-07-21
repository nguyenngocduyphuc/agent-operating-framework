# AOF Master Plan — phát triển toàn diện

*SSoT roadmap. Chi tiết 90 ngày: `plans/AOF_BEST_PATH_90D.md`.  
Audit: `CLEAN_MACHINE_AUDIT_20260721.md`. Bypass: `BYPASS_AND_KARPATHY.md`.*

## 1. Sản phẩm là gì / không là gì

| Là | Không là |
|---|---|
| Lớp **tin cậy vận hành** (preflight → contract → verify → evidence) | Orchestrator / multi-agent chat product |
| Portable core + MCP + CLI | Asana/cmux business logic trong core |
| Đo được / fail-closed / honest claims | Claim ROI khi n thiếu |

## 2. North star (12 tháng)

```text
Stranger:  clone/pip → doctor xanh → MCP 1 câu → làm việc an toàn
CEO:       mỗi tuần thấy hiệu quả theo workspace trên GitHub Issue (số thật)
Public:    beta có tag khớp, TestPyPI/PyPI, bench n≥30 khi claim
```

## 3. Phases toàn diện

| Phase | Tên | DoD | Trạng thái |
|---|---|---|---|
| **P0** | Core trust (lease, lanes, policy, Karpathy default) | tests + doctor clean clone | **Done** (2026-07) |
| **P1** | Handoff loop + error ledger + improve propose | F1–F4 + CI | **Done** |
| **P2** | Measure + no-code auto pulse | estate, cmux id, `HIEU_QUA_HOM_NAY.md`, status_report | **Done** |
| **P3** | Publish hygiene | `.[dev]`, README 14 tools, clean audit, **tag v0.3.0b1** | **In progress** |
| **P4** | GitHub as effectiveness cockpit | Tracking issue + `gh` post script + metrics folder | **This PR** |
| **P5** | Dogfood 14 ngày | handoff/resume/blocked > 0 trên tracker | **CEO + host** |
| **P6** | TestPyPI + pilot 2 no-code | stranger Ready path | Next |
| **P7** | Bench n≥30 + EN quickstart | honest public claims | Later |
| **P8** | v0.4.0 / v1.0 decision | CEO only | Gate |

## 4. GitHub = nơi tracking hiệu quả (cách dùng)

| Cơ chế | Vai trò |
|---|---|
| **Issue ghim** `AOF Effectiveness Tracker` | Timeline comment = pulse hàng ngày/tuần |
| **`scripts/post_effectiveness_to_github.sh`** | Máy anh (có `~/.aof`) → `estate-report` → `gh issue comment` |
| **`docs/metrics/`** | Lưu JSON snapshot (tuỳ chọn commit/PR) — lịch sử trong git |
| **Labels** `effectiveness`, `dogfood`, `publish` | Lọc việc |
| **Projects** (optional) | Board: Dogfood / Packaging / Pilot / Bench |
| **CI** | Chỉ chứng minh *code* xanh — **không** giả vờ đo vận hành host |

**Vì sao không chỉ CI?**  
Số hiệu quả nằm ở **ledger host** (`~/.aof`), không có trong git. CI đo “repo build”, Issue đo “repo được dùng thế nào”.

**No-code path:** MCP vẫn auto-ghi `HIEU_QUA_HOM_NAY.md`.  
**GitHub path:** 1 lệnh script (hoặc agent gọi script) đăng lên Issue — CEO mở browser.

## 5. Tuần chuẩn (sau P4)

| Ngày | Tự động / người |
|---|---|
| Mỗi session MCP | Auto file hiệu quả + status_report pulse |
| Cuối ngày (optional) | `bash scripts/post_effectiveness_to_github.sh 1` |
| Chủ nhật | `bash scripts/post_effectiveness_to_github.sh 7` + đọc Issue |
| Khi số xấu | `aof lessons` / improve-check — không spam feature |

## 6. Stop rules

- Handoff/resume = 0 sau 14 ngày dogfood → **cấm** feature mới.  
- Claim public chỉ từ `docs/metrics/` + bench file có n.  
- Không nhét cmux/Asana vào core.

## 7. Owner map

| Lane | Owner |
|---|---|
| Code / PR / CI | Agent (surgical) |
| Post metrics to GitHub | Agent hoặc CEO (1 lệnh) |
| Dogfood thật | CEO + mọi session MCP |
| Tag / PyPI / public announce | CEO (tier-4) |

## 8. Liên kết

- 90 ngày chi tiết: `plans/AOF_BEST_PATH_90D.md`  
- Clean audit: `CLEAN_MACHINE_AUDIT_20260721.md`  
- Metrics how-to: `metrics/README.md`  
- Dogfood: `DOGFOOD_7DAY_VI.md`  
