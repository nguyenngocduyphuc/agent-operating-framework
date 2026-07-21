# Kiểm soát worker — 4 luật đo được

*Chuẩn v0.4. Ngưỡng treo mặc định: 300s (`heartbeat.DEFAULT_STALE_AFTER_S` / policy `worker_stale_after_s`).*

1. **Giao việc = contract C 7 dòng + DoD-cmd chạy được**  
   Worker không nhận việc mơ hồ. Orchestrator `check_contract` trước khi dispatch.  
   Ví dụ: tool MCP `check_contract` với brief đủ Task/Owner/Scope/DoD/Do not/Stop if/Return.

2. **Canh bằng OUTPUT, không tin session sống**  
   `aof watch path/to/worker.log --stale-after 300` (hoặc tool `worker_watch`).  
   Stale/missing → dừng/khởi động lại; không chờ “session còn ping”.

3. **Worker không tự chấm**  
   Orchestrator chạy `verify_gate` + `audit_scope`; output worker chỉ là dữ liệu.  
   Ví dụ: tool `verify_gate` `gate_type=pytest`, rồi `audit_scope` với glob Scope.

4. **Đo hiệu quả per-task**  
   `aof log --task <id> --since-hours 24` (hoặc tool `op_log`).  
   Fail rate / bị chặn lộ trong recap — quy trình fail nhiều thì thấy ngay.
