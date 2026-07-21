# Chuẩn: mọi ExecPlan phải có bản HTML để CEO duyệt

*2026-07-21, sửa lần 2 cùng ngày. Bản đầu (luật 1-5 cũ) là em tự bịa khung
5 mục — SAI, vì CEO đã có chuẩn sẵn (skill `deliverable-factory` mode roadmap
trong `.agent/skills/`, hậu duệ của `unified-roadmap-architect`) mà em không
tra trước. Xem [[estate-console-skill-governance]]. Sửa lại: dùng ĐÚNG skill
canonical, không tự nghĩ format mới.*

## Luật

1. **Mọi ExecPlan đụng nhiều file/core infra phải có cặp Master Context (.md)
   + Interactive Roadmap (.html)**, sinh **trước khi sửa dòng code đầu tiên**,
   bằng skill `unified-roadmap-architect` (Cowork) — hậu duệ trực tiếp của
   `deliverable-factory` mode roadmap (`.agent/skills/deliverable-factory/`)
   trên máy CEO. KHÔNG tự viết HTML tay từ đầu.
2. Cấu trúc bắt buộc theo skill, không tự chế: .md = 8 PHẦN (Hệ thống, KPI
   Framework, Baseline, Đã hoàn thành, Roadmap+Agent Prompts, Session End
   Protocol, Nguyên tắc bất biến, Cách dùng); .html = 4 layer (KPI cards,
   Maturity bar, Timeline ≥5 hàng gồm hàng L→L+1 Gap + UI/CEO riêng, Gap
   analysis cards).
3. **Validate bằng script thật trước khi trình**, không tự chấm bằng mắt:
   `python3 .agent/skills/deliverable-factory/scripts/validate_output.py
   <html>` (hoặc bản trong Cowork skill nếu không có quyền đọc `.agent/skills`)
   — phải PASS cả 6 gate (sendPrompt≥20, timeline≥5, milestone≥3, Gap row,
   UI/CEO row, task≥20) trước khi present cho CEO.
4. Số liệu trong .md/.html phải lấy từ chạy lệnh thật trong phiên (pytest,
   ruff, git, đọc code) — không suy đoán; thiếu số thì ghi `(unknown)` hoặc
   `(inferred)`, không bịa.
5. Sau khi CEO xem (duyệt bằng artifact trong phiên — không treo duyệt
   trong chat, theo luật "Duyệt bằng artifact" 18/07 của CEO) và gật
   (`session_log` event `approved`), mới bắt đầu sửa code. Hình thức cụ thể
   của luật "needs_approval" trong skill `/aof`.
6. Khi ExecPlan có nhiều tính năng độc lập (như v0.4: F1-F5), mỗi checkpoint
   là 1 hàng riêng trong timeline — CEO duyệt từng phần, không phải
   tất-cả-hoặc-không-gì.
7. Trước khi tự nghĩ format mới cho BẤT KỲ deliverable nào (không riêng
   plan), tra Estate Console (`docs.nampham.net/estate`, mở qua Claude in
   Chrome vì trang render JS) — rất có thể CEO đã có skill/quy chuẩn sẵn.

## Vì sao

Markdown thô tốt cho agent đọc grounding, nhưng CEO ra quyết định nhanh hơn và
chính xác hơn khi nhìn bảng/số liệu có cấu trúc, đúng format quen thuộc mỗi
lần — đó là lý do skill `deliverable-factory`/`unified-roadmap-architect` đã
tồn tại từ trước, không cần bịa lại. Bài học 2026-07-21: bịa khung riêng dù
tinh thần đúng vẫn là lỗi — quy trình đã có, việc của agent là TRA và DÙNG,
không phải sáng tạo lại.

## Áp dụng

Có hiệu lực từ ExecPlan `AOF_V04_AUTOHANDOFF_EXECPLAN_20260721.md`. Bản đúng
chuẩn: `docs/plans/AOF_V04_AUTOHANDOFF_CONTEXT.md` +
`docs/plans/AOF_V04_AUTOHANDOFF_ROADMAP.html` (validate_output.py: PASS
6/6 — sendPrompt 35, timeline 6 hàng, milestone 3, Gap row YES, UI/CEO row
YES, task 20). Bản cũ `AOF_V04_AUTOHANDOFF_EXECPLAN_20260721_REVIEW.html`
(tự chế, không qua skill canonical) giữ nguyên làm tham khảo lịch sử, KHÔNG
xoá (workspace folder không cho xoá không hỏi), nhưng không còn là bản CEO
nên dùng để duyệt.
