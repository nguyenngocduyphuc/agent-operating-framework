# Metrics — tracking hiệu quả AOF trên GitHub

## Ý tưởng

| Nơi | Chứa gì |
|---|---|
| `~/.aof/` (máy) | Ledger thật (audit, decisions, errors) |
| `~/.aof/estate/HIEU_QUA_HOM_NAY.md` | Pulse no-code (tự cập nhật) |
| **GitHub Issue** “Effectiveness Tracker” | Lịch sử công khai / cho team (comment) |
| `docs/metrics/*.json` (optional) | Snapshot commit vào repo |

CI **không** thay ledger host — CI chỉ nói code còn xanh.

## Cách dùng (1 lệnh)

```bash
# từ clone AOF, đã: gh auth login, pip install -e .
bash scripts/post_effectiveness_to_github.sh        # 7 ngày
bash scripts/post_effectiveness_to_github.sh 1      # 24h
bash scripts/post_effectiveness_to_github.sh 7 --save-json
```

Script sẽ:

1. Chạy `aof estate-report` (hoặc `python -m core.cli`)  
2. Tìm/tạo Issue tracking  
3. `gh issue comment` với pulse tiếng Việt/Anh  
4. (optional) ghi `docs/metrics/YYYY-MM-DD.json`

## No-code

Không bắt buộc script: hỏi agent **status_report** / **estate_report**,  
hoặc mở file `HIEU_QUA_HOM_NAY.md`.  
Script chỉ để **đưa số lên GitHub** cho tracking dài hạn.

## Privacy

Ledger có thể chứa path máy / task id.  
Trước khi `--save-json` + commit public: rà path nhạy cảm.  
Issue comment mặc định dùng KPI đã aggregate (ít path hơn full audit).
