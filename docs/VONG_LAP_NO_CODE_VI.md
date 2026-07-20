# Vòng lặp no-code — già trẻ lớn bé đều dùng được

*Người dùng chỉ cần nói được việc mình muốn. Toàn bộ 9 bước dưới đây do MÁY tự
chạy và tự chứng minh; người dùng chỉ chạm vào 3 điểm: nói việc, gật đầu khi
được hỏi, và đọc recap.*

## Người dùng chỉ cần MỘT câu

> **Dùng AOF làm việc này cho tôi: «nói việc bằng lời thường».**
> Lập kế hoạch, chia việc nhỏ, làm từng bước có kiểm soát, hỏi tôi trước
> bước rủi ro, kiểm chứng bằng máy, và cuối buổi đưa tôi recap.

Muốn biết tình hình giữa chừng: **"tình hình sao rồi?"** → máy trả 1 trong 4
trạng thái: Đang làm · Chờ duyệt · Bị chặn · Xong-có-bằng-chứng.

## 9 bước máy tự chạy — điều kiện nghiệm thu từng bước

| # | Bước | Máy làm gì | Nghiệm thu (điều kiện để qua bước) |
|---|---|---|---|
| 1 | Kiểm tra môi trường | `preflight` (+ nhận khoá nhiệm vụ, chọn làn) | status `clear`; nhiệm vụ bị phiên khác giữ → dừng ngay |
| 2 | Lập kế hoạch — **suy nghĩ trước** | Viết hợp đồng 7 dòng + Assumptions + DoD-cmd + Scope hẹp | `check_contract` ok=true; **Karpathy gate**: thiếu suy nghĩ ghi được thành chữ → bị chặn |
| 3 | Phân rã & giao việc | Chia việc nhỏ theo Scope; việc rủi ro tách riêng làn risk | Mỗi việc con có DoD riêng; việc rủi ro → bước 4 |
| 4 | Chốt người thật (nếu rủi ro) | `session_log needs_approval` → hỏi người dùng 1 câu | Người dùng gật ("approved") mới đi tiếp — không gật là đứng |
| 5 | Thực thi có kiểm soát | Làm trong Scope; ngoài Scope là dừng (Stop-if) | Không file nào ngoài Scope (`audit_scope` sẽ soát ở bước 6) |
| 6 | Kiểm chứng bằng máy | `verify_gate` (test/lint/DoD-cmd) + `audit_scope` | verify passed=true VÀ scope ok=true — lời khai không được tính |
| 7 | Chốt bằng chứng | `post_evidence` | Chỉ 2 kết cục: **Done** (mọi gate xanh) hoặc **Blocked** — không có vùng xám |
| 8 | Bàn giao | `aof handoff` → docs/sessions/HANDOFF_*.md | File tồn tại; việc mở được liệt kê để phiên sau nhận |
| 9 | Recap + báo cáo | `aof recap` → docs/sessions/RECAP_*.html | File HTML mở được, số khớp `aof log` — docs tự cập nhật MỖI phiên |

## Vì sao tin được (3 luật máy không phá được)

1. **Máy phải suy nghĩ trước khi làm** — Karpathy gate bật mặc định: hợp đồng
   thiếu Assumptions thật / DoD-cmd chạy được / Scope hẹp là bị chặn từ bước 2.
2. **Máy không chấm bài của mình bằng lời** — bước 6 do server chạy lại lệnh
   kiểm; bước 7 chỉ mở khi bước 6 xanh.
3. **Sổ sách không tô hồng** — recap/report in nguyên số từ sổ cưỡng chế,
   kể cả thất bại và va chạm.

## Ánh xạ đủ yêu cầu vận hành

Lập kế hoạch (2) · phân rã/giao việc (3) · kiểm soát thực thi (5) · nghiệm thu
theo điều kiện (6) · verify/test (6) · evidence (7) · done (7) · handoff (8) ·
recap HTML + report (9) · docs update từng session (8+9 ghi vào docs/sessions/).
