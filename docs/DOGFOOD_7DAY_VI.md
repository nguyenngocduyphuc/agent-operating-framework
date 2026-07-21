# Dogfood 7 ngày — AOF có bị bypass không?

## Câu trả lời thẳng (2026-07-21)

**Có — AOF đang bị bypass theo nhiều lớp**, không chỉ “quên bật Karpathy”.

| Lớp | Trạng thái | Ý nghĩa |
|---|---|---|
| Policy NP_AI (máy anh) | `require_ponytail` → Karpathy **ON**, `require_task` ON | Workspace này **khai** hard mode |
| `aof init` / doctor default | `require_karpathy: true` | Đúng product claim |
| `load_policy` khi **không** có file | Trước đây **thiếu** key → Karpathy **OFF** (fail-open) | **Bug bypass** — đã sửa default `true` |
| `setup.sh` template | Trước đây **không** ghi `require_karpathy` | **Bug bypass** — đã sửa |
| Agent chỉ dùng shell/editor, không gọi MCP | Gate **không chạy** | Bypass **cấu trúc** — AOF không chặn bàn phím |
| Tool report (`op_log`, `handoff`, `status`) | Không cần preflight | Cố ý; không thay verify/evidence |
| `blocked=0` / handoff≈0 / resume=0 / errors=0 | Ledger 7 ngày | Loop **không được dùng** dù tool có |

**Kết luận:** Karpathy **không phải lúc nào cũng mặc định trong code path cài đặt**.  
Dù policy ON, agent vẫn bypass bằng cách **không đi qua MCP gates**.  
Số estate: nhiều session noise (test MCP), ít handoff/resume → “có AOF” ≠ “dùng AOF”.

## Protocol 7 ngày (bắt buộc nếu muốn biết hiệu quả)

Mỗi session **việc thật** (không tính pytest spam):

1. `preflight` (có `--task` / task id khi policy require_task)  
2. `check_contract` brief **đủ 7 field + Karpathy** (`Assumptions:`, `DoD-cmd:`, Scope bound)  
3. Làm việc trong Scope  
4. `verify_gate` (DoD-cmd / pytest) — orchestrator chạy, worker không tự chấm  
5. `audit_scope`  
6. `post_evidence` → **Done** hoặc **Blocked** (cấm im lặng)  
7. `session_handoff` cuối phiên  
8. Phiên sau: `aof resume`  

Bug thật → `session_log event=error` + sửa kèm test → close có `test_ref`.

## Checklist cuối ngày

```bash
aof estate-report --days 1 --lang vi
aof lessons --lang vi
```

| Tín hiệu | Mục tiêu 7 ngày |
|---|---|
| handoffs / ngày làm việc | ≥ 1 |
| resumes > 0 | ≥ 1 lần/tuần |
| blocked > 0 nếu có kẹt | không chỉ Done |
| sessions_noise_rate | giảm (ít MCP spam thuần) |
| untagged_task_activity | giảm |
| karpathy_contract_blocks | > 0 nếu brief lười (gate đang cắn) |

## Bypass còn lại (chấp nhận có ý)

- Agent **không** đăng ký MCP / không gọi tool → ngoài tầm AOF. Giải pháp: skill `/aof` + MCP registration + kỷ luật host, không phải thêm tool.  
- Multi-cmux chưa gắn estate tự động → dùng `scripts/estate_weekly.sh`.  

## Liên quan

- Estate KPI: `docs/ESTATE_EFFECTIVENESS.md`  
- Bypass history: policy notes NP_AI (advisory → hard 2026-07-12)  
- Sửa default Karpathy: `core/preflight.py` load_policy + `setup.sh`  
