# AOF — Kế hoạch tốt nhất (90 ngày) + DoD đo được

*Sinh sau clean-machine audit 2026-07-21. Không claim ngoài số đã đo.*

## Mục tiêu

| Cột mốc | Ý nghĩa | Điểm publish-ready mục tiêu |
|---|---|---|
| **T0 (hôm nay)** | Clean clone install + doctor + 163 tests | ~4.5–5.5 → **5.5** sau hygiene |
| **T+14** | Dogfood số sạch + README/semver khớp | **6.5** |
| **T+45** | TestPyPI + pilot 2 no-code | **7.5** |
| **T+90** | Tag public beta + bench honest | **8.0+** (vẫn beta, không fake v1.0) |

## Nguyên tắc (Karpathy)

1. **Think before code** — mỗi tuần 1 DoD số, không ship feature “cho đủ wave”.  
2. **Simplicity** — no-code = MCP + file auto + 1 câu hỏi tiếng Việt; CLI optional.  
3. **Surgical** — chỉ đụng path publish/dogfood/measure.  
4. **Goal-driven** — stop-if: dogfood handoff/resume/blocked vẫn 0 sau 14 ngày → dừng feature mới, chỉ coach.

## Phase 0 — Hygiene (tuần này) ✅/đang

| Việc | DoD |
|---|---|
| Clean clone `pip install -e .` | `aof --version` = 0.3.0b1 |
| `aof init` + `aof doctor` máy sạch | doctor ok, MCP 14 tools |
| `pytest` clean venv | 163 pass (cần `pip install pytest` hoặc extra dev) |
| Extra `[dev]` trong pyproject | `pip install -e ".[dev]"` có pytest+ruff |
| README tool list = 14 tools + no-code estate | không stale |
| Docs: CLEAN_MACHINE_AUDIT + plan này | có số đo |

## Phase 1 — Dogfood 14 ngày (ưu tiên #1)

| Việc | DoD số |
|---|---|
| Mỗi ngày làm việc: preflight→contract(Karpathy)→verify→evidence→handoff | `handoffs ≥ 1/ngày làm việc` |
| Phiên sau: resume | `resumes ≥ 3/tuần` |
| Kẹt = Blocked | `blocked ≥ 1` nếu có kẹt thật |
| Bug = error + test_ref | `open_errors` có đóng được |
| Đọc auto file | Mở `~/.aof/estate/HIEU_QUA_HOM_NAY.md` (không CLI) |

**Stop-if:** sau 14 ngày handoff vẫn ≈0 → **không** thêm MCP tool; sửa skill `/aof` + kỷ luật host.

## Phase 2 — Packaging public (T+15…45)

| Việc | DoD |
|---|---|
| Tag `v0.3.0b1` khớp pyproject | `git tag` = version |
| TestPyPI upload | `pip install` từ TestPyPI trên máy sạch |
| CI badge shield thật | README xanh |
| Coverage tối thiểu core (optional 60%) | CI không đỏ |

## Phase 3 — Pilot + bench (T+45…90)

| Việc | DoD |
|---|---|
| 2–3 người no-code 1 vòng 9 bước | feedback / Needs approval / Blocked có thật |
| AOF-Bench n≥30/arm WITH vs WITHOUT | số README = số đo; p-value hoặc không claim |
| English quickstart parity | 1 page EN |

## Việc **không** làm (trừ khi Phase 1 xong)

- Orchestrator / fleet UI trong core  
- Cmux control plane phức tạp  
- Claim ROI %  
- v1.0 tag khi còn beta dogfood  

## Owner

| Lane | Owner |
|---|---|
| Code publish hygiene | agent (PR) |
| Dogfood hàng ngày | CEO + agent host MCP |
| Pilot stranger | CEO |
| PyPI/tag public | CEO approve (tier-4) |

## Success criteria “tốt nhất” (không phải “nhiều feature nhất”)

1. Stranger: clone → install → doctor xanh → MCP → status_report thấy hiệu quả.  
2. Anh: 14 ngày estate cho thấy handoff/resume/blocked có thật.  
3. Public: TestPyPI + tag khớp + 0 claim ngoài số.  
