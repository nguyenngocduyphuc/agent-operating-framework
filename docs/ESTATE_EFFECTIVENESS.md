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

## Multi-workspace identity (từ 2026-07-21)

Mỗi `session_start` / `preflight` ghi host context (nếu env có):

| Field | Nguồn |
|---|---|
| `aof_workspace` | `$AOF_WORKSPACE` |
| `cwd` | process cwd / bound cwd |
| `cmux_workspace_id` | `$CMUX_WORKSPACE_ID` |
| `cmux_surface_id` | `$CMUX_SURFACE_ID` |
| `cmux_panel_id` / `cmux_tab_id` | cmux env |
| `cmux_agent_kind` / `cmux_agent_cwd` | `$CMUX_AGENT_LAUNCH_*` |

`aof estate-report` section **Per workspace** groups sessions by
`cmux_workspace_id` (preferred) else AOF workspace path.

**From this deploy forward**, multi-workspace stats work for sessions launched
inside cmux (env present). Older audit rows without these fields stay under
`(unknown)` or path-only keys.

## Ranh giới

- **Không** nhét logic điều khiển cmux vào core — chỉ **đọc env identity**.  
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
