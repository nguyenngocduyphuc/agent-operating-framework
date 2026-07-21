# Estate effectiveness — biết AOF đang hiệu quả ra sao

## Vấn đề

Gate + ledger local không đủ để CEO thấy **nhiều workspace / nhiều repo**
đang vận hành thế nào. Không có thống kê estate thì không thể nói hiệu quả
vận hành (chỉ có smoke lab 3 failure mode).

## Giải pháp (host-side, core portable)

```bash
aof estate-report --days 7
aof estate-report --days 7 --json
aof estate-report --days 7 --html --out docs/sessions/ESTATE_WEEK.html
aof estate-report --days 7 --snapshot   # ~/.aof/estate/snapshots/ + latest.json
```

Nguồn (chỉ ledger AOF, không gọi cmux/Asana):

| Ledger | Dùng cho |
|---|---|
| `audit.jsonl` | sessions, preflight status/workspace, lease_conflict, handoff, resume |
| `decisions.jsonl` | verify pass/fail, contract, done/blocked |
| `errors.jsonl` | open errors, fingerprint lặp |
| `handoffs/index.jsonl` | per-repo handoff density |

## KPI

- `preflight_clear_rate` — bắt đầu đúng chỗ  
- `lease_collisions` — đã chặn giẫm task (số cao + không lọt = gate làm việc)  
- `verify_fail_rate` — chất lượng DoD  
- `blocked_share` — closeout trung thực  
- `open_errors` / `repeated_fingerprints` — tái phạm  
- `handoffs` / `resumes` / `resume_to_handoff_rate` — bàn giao có được nạp lại  

## Telemetry mới

Mỗi `preflight` MCP ghi audit:

`event=preflight, status, workspace, repo, branch, task, cwd, lane`

→ estate mới “thấy” workspace/repo. Bản audit cũ trước thay đổi này
không có preflight rows (KPI preflight = 0 cho đến khi có traffic mới).

## Ranh giới

- **Không** nhét cmux vào core. Join cmux workspace map = adapter NP_AI sau.  
- **Không** claim ROI n≥30 từ estate-report.  
- Multi-host: sau này `AOF_ESTATE_SOURCES` (nhiều audit dir) — chưa ship.  

## Vòng tuần (CEO)

1. `aof estate-report --days 7 --snapshot --html --out …`  
2. `aof lessons`  
3. `aof improve-check` (1 đề xuất)  
4. Duyệt / PR  

## Liên quan

- Smoke lab: `docs/EFFECTIVENESS_SMOKE_20260721.md`  
- Self-improve: `docs/ENGINEERING_WORKFLOW.md`  
- Architecture: `docs/ARCHITECTURE.md`  
