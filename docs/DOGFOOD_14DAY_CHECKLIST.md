# AOF — Checklist dogfood 14 ngày (dán bàn / 1 trang)

**Mục tiêu:** chứng minh AOF **được dùng**, không chỉ được cài.  
**DoD 14 ngày:** handoff ≥1/ngày làm việc · resume ≥3/tuần · blocked >0 nếu có kẹt · mở được `HIEU_QUA_HOM_NAY.md`.

---

## Mỗi phiên làm việc (bắt buộc)

| # | Việc | Cách (no-code) | ✔ |
|---|---|---|---|
| 1 | Mở agent **đã gắn MCP AOF** | cmux / Claude như mọi ngày | ☐ |
| 2 | Giao việc 1 câu | “Dùng AOF làm: …” | ☐ |
| 3 | Cho máy preflight + contract | Agent tự gọi; **có task** nếu policy yêu cầu | ☐ |
| 4 | Brief có **Assumptions + DoD-cmd + Scope hẹp** | Karpathy — thiếu thì sửa, đừng bypass | ☐ |
| 5 | Duyệt nếu **Chờ duyệt** | Gật “approved” / từ chối | ☐ |
| 6 | Kết thúc: **Done** hoặc **Blocked** | Cấm im lặng “coi như xong” | ☐ |
| 7 | Có **handoff** cuối phiên | Agent `session_handoff` / “bàn giao phiên” | ☐ |
| 8 | Phiên sau: **resume** | “Tiếp việc hôm qua” / `aof_resume` | ☐ |

**Tự động (không gõ lệnh):** hết phiên → cập nhật  
`~/.aof/estate/HIEU_QUA_HOM_NAY.md` · hỏi “tình hình?” → `status_report` có hiệu quả 24h.

---

## Cuối ngày (2 phút)

| # | Việc | ✔ |
|---|---|---|
| 1 | Mở `~/.aof/estate/HIEU_QUA_HOM_NAY.md` | ☐ |
| 2 | Ghi nhanh 1 dòng nhật ký bên dưới (ngày / handoff? / resume? / kẹt?) | ☐ |
| 3 | (Tuỳ chọn) post GitHub: `bash scripts/post_effectiveness_to_github.sh 1` | ☐ |

### Nhật ký 14 ngày (viết tay / note)

| Ngày | Handoff | Resume | Blocked | Ghi chú 1 dòng |
|------|---------|--------|---------|----------------|
| D1 | ☐ | ☐ | ☐ | |
| D2 | ☐ | ☐ | ☐ | |
| D3 | ☐ | ☐ | ☐ | |
| D4 | ☐ | ☐ | ☐ | |
| D5 | ☐ | ☐ | ☐ | |
| D6 | ☐ | ☐ | ☐ | |
| D7 | ☐ | ☐ | ☐ | |
| D8 | ☐ | ☐ | ☐ | |
| D9 | ☐ | ☐ | ☐ | |
| D10 | ☐ | ☐ | ☐ | |
| D11 | ☐ | ☐ | ☐ | |
| D12 | ☐ | ☐ | ☐ | |
| D13 | ☐ | ☐ | ☐ | |
| D14 | ☐ | ☐ | ☐ | |

---

## Cuối tuần (10 phút)

| # | Việc | ✔ |
|---|---|---|
| 1 | `bash scripts/post_effectiveness_to_github.sh 7` | ☐ |
| 2 | Mở [Issue #21 Effectiveness Tracker](https://github.com/nguyenngocduyphuc/agent-operating-framework/issues/21) | ☐ |
| 3 | So KPI: handoffs · resumes · blocked · noise · verify_fail | ☐ |
| 4 | **Stop-if:** handoff cả tuần = 0 → **không** xin feature mới; chỉ siết thói quen MCP | ☐ |

---

## Cấm (bypass)

- Làm việc agent **không** qua MCP AOF rồi bảo “đã dùng AOF”  
- Contract không Assumptions / DoD-cmd / Scope `*`  
- Chỉ Done, không bao giờ Blocked khi thực sự kẹt  
- Bỏ handoff “mai nhớ”

---

## 4 trạng thái nhớ thuộc

| Thấy | Ý nghĩa |
|---|---|
| Đang làm | Preflight ok, đang trong chuỗi |
| Chờ duyệt | Cần anh gật |
| Bị chặn | Sửa blocker rồi preflight lại |
| Xong-có-bằng-chứng | verify + evidence ok |

---

**Bắt đầu:** ____/____/______ · **Kết thúc:** ____/____/______ · **Owner:** ________________  
*Chi tiết vòng 9 bước: `VONG_LAP_NO_CODE_VI.md` · Plan: `MASTER_PLAN.md`*
