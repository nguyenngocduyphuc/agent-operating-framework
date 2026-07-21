# Thẩm định sản phẩm AOF — 2026-07-21

*Hai góc nhìn độc lập: chuyên gia phần mềm và người dùng no-code. Mọi điểm số
neo vào bằng chứng chạy được trong repo; không có điểm nào từ cảm tính.*

## Góc chuyên gia phần mềm

| Chiều | Điểm | Bằng chứng / Lỗ hổng |
|---|---|---|
| Kiến trúc | 9/10 | Core portable zero-dep + adapters; fail-closed nhất quán; lease theo git-common-dir; lanes theo luật causal. Trừ 1: audit schema v2 chưa hợp nhất (nợ từ 17/07) |
| Enforcement đúng chuẩn MCP | 9/10 | Envelope content/isError đúng; refusal là tool-result đọc được kèm fix; preconditions luôn bật ở handler chain; 8 tools; E2E stdio xanh |
| Testing | 9/10 | **132 tests**: unit + adversarial (decoy shadow, race, escalation) + policy-compat + **E2E hành trình người dùng 9 bước thật** (không mock). Trừ 1: chưa có CI tự động chạy |
| Bảo mật | 8/10 | Không shell từ worker; metachar deny; HTML escape; lease sanitize; SECURITY.md. Chưa: fuzz DoD-cmd, threat model doc |
| Đóng gói / phát hành | 5/10 | pip-installable, CLI entry, CHANGELOG kỷ luật. **Chưa: CI workflow, tag/release, PyPI, semver policy** |
| Tài liệu | 8/10 | VI đầy đủ từ quickstart tới governance; decisions + history index. Chưa: English parity cho docs mới |
| Khả năng quan sát | 8/10 | audit + decisions ledger, log/recap/handoff tự sinh. Chưa: schema v2 |
| Tương thích/di trú | 9/10 | Policy v1→v2 compat có test end-to-end; lease/lanes đều opt-in an toàn |

**Điểm mạnh nhất (hiếm có):** sản phẩm tự phá mình — 3 sự cố shadow-import và
2 fail-open đều bị bắt bằng chính quy trình của nó trong 2 ngày, và mỗi lỗi
thành một test vĩnh viễn. **Điểm yếu nhất:** vành đai phát hành (CI/tag/PyPI)
chưa có — code đạt production, *quy trình phát hành* chưa.

## Góc người dùng no-code

| Chiều | Điểm | Ghi chú |
|---|---|---|
| Tới giá trị đầu tiên | 7/10 | 4 lệnh + doctor xanh tiếng Việt. Rào còn lại: bước `pip install` (installer 1 lệnh còn nợ) |
| Ngôn ngữ & trạng thái | 9/10 | Mặt tiền 100% tiếng Việt; đúng 4 trạng thái wave2; luôn có "bước tiếp theo" |
| Vòng lặp hằng ngày | 9/10 | 1 câu giao việc → recap HTML cuối buổi; docs/sessions tự cập nhật |
| Tin được không | 9/10 | Máy không tự chấm bằng lời; Blocked hiện to bằng Done; số đối chiếu được |
| Khi hỏng thì sao | 8/10 | doctor chỉ đúng 1 bước sửa; mọi refusal kèm fix. Chưa: kênh báo lỗi cho người không đọc terminal |

## Verdict: "MCP chuyên nghiệp chưa?"

**Nội bộ (production cho vận hành của anh): ĐẠT.** Giao thức chuẩn, kỷ luật
enforcement luôn bật, 132 test, E2E thật, đã đăng ký chạy song song trong
workspace thật.

**Công khai (publish): CHƯA — thiếu đúng 4 thứ, đều thuộc vành đai phát hành,
không thuộc lõi:** ① CI tự động (GitHub Actions: ruff + pytest ma trận
3.10–3.12), ② audit schema v2 hợp nhất, ③ installer 1 lệnh (harness-style),
④ tag v0.4.0 + quy ước semver. Lõi không cần đập gì.

## Kế hoạch phát triển

| Bản | Nội dung | Điều kiện qua |
|---|---|---|
| **v0.4** (kế tiếp) | CI workflow · audit schema v2 (một writer một schema) · installer 1 lệnh `curl \| bash` + PowerShell · tag v0.4.0 | CI xanh trên 3.10–3.12; installer test trên máy sạch |
| v0.4.x | Shadow parity: so 2 server bằng `aof log` trên vận hành thật ≥2 ngày → cutover nhóm 1 skill /aof | 0 lệch không giải thích được |
| v0.5 | AOF-Bench chạy lại trên core mới theo exec plan AOF_BENCH_V1 (n≥30, scorer độc lập) · English docs parity · TestPyPI | Số mới công bố được trong ràng buộc trung thực |
| v1.0 | Anh quyết publish: PyPI + GitHub release + đóng gói plugin (MCP + skill + policy mẫu) | Pilot ≥2 người no-code thật dùng trọn vòng 9 bước |

*Nguyên tắc xuyên suốt: History Gate trước mọi thay đổi; GO-RISK-LANE là luật;
mỗi bug thật → một test vĩnh viễn; không claim gì ngoài số đã đo.*
