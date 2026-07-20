# Dòng thời gian sản phẩm AOF — chưng cất từ lịch sử phân tán

*Nguyên tắc: artifact gốc nằm trong workspace vận hành (private, không publish).
File này là bản chưng cất đủ để mọi phiên phát triển sau grounding được mà
không cần đào lại. Nguồn gốc ghi kèm từng mốc — xem History Gate trong
`../HISTORY_GOVERNANCE.md`.*

| Mốc | Sự kiện | Kết luận còn hiệu lực | Nguồn gốc (workspace NP_AI) |
|---|---|---|---|
| ~06/2026 | Seed: framework cho orchestrator điều phối fleet | 3 trụ: ponytail (tối giản) · task tracker · governed orchestration | `docs/AOF_ORIGINAL_FRAMEWORK_SEED.md` |
| 03/07 | Benchmark v2 bác governance đơn-agent | Không bán "phanh" cho dev đơn lẻ; giá trị ở tầng fleet | `docs/AOF_STRATEGIC_ASSESSMENT_2026-07-03.md` |
| 03/07 | Pivot "measured productivity" | Mọi tính năng phải kèm bằng chứng đo được | `docs/AOF_PIVOT_MEASURED_PRODUCTIVITY_2026-07-03.md` |
| 04/07 | Proven value: 8/8 defect detect có MCP vs 2/8 không | AOF = bảo hiểm, không phải phép màu | `docs/AOF_FRAMEWORK_PROVEN_VALUE.md` |
| 14/07 | Wave2 chốt no-code | 2 prompt copy-paste + 4 trạng thái: Planning / Needs approval / Blocked / Done | `artifacts/team/AOF-V2/wave2-nocode-onboarding-brief.md` |
| **16/07** | **CAUSAL-VERDICT n=105, luật khóa trước** | **GO-RISK-LANE**: scope-block 100% vs 43% (p<0.05, tái lập); overhead +35% → full chain chỉ cho lane rủi ro; **contract mặc định = bản 7 dòng** | `artifacts/team/AOF-PRODUCT/CAUSAL-VERDICT-20260716.md` |
| 17/07 | Đối chiếu chuẩn Anthropic (8 nguồn) | Khớp hooks/skills/orchestrator-workers; nợ: evaluator-optimizer inline, visual verification; audit.jsonl nhiễm 3 schema | `artifacts/team/AOF-PRODUCT/aof-vs-anthropic-20260717.md` |
| 18/07 | Đo thật 56 phiên: /aof bị đi vòng | Thuế gate đè việc thường → càng khẳng định risk-lane | artifact_index #"Đo thật 56 phiên" |
| 20/07 | Audit 3 P0 lớp kiểm soát (codex, đã xác minh độc lập) | false-success rescue · DoD shell từ worker · thiếu C2 lease | `docs/handoffs/ASANA-…-C6-…md` + exec plan hardening |
| 20-21/07 | v0.3 → v0.3.3 trên repo này | lease · policy compat · status_report · init/doctor · log/watch · lanes · needs_approval · recap/handoff · Karpathy mặc định | `../../CHANGELOG.md`, `../decisions/` |
| 21/07 | 3 sự cố shadow-import trong 1 ngày | LUẬT: mọi đăng ký/CLI dùng đường dẫn file tuyệt đối; smoke 8 tools bắt buộc | `../HISTORY_GOVERNANCE.md` luật 2 |

## Luật còn hiệu lực khi phát triển tiếp

1. GO-RISK-LANE là luật đã khóa — thay đổi enforcement phải tôn trọng hoặc chạy bench mới n≥30.
2. Claim công khai chỉ trong ràng buộc: scope-block significant; pass/fabrication directional; luôn kèm +35% chi phí.
3. Không claim tổng quát hoá cross-worker khi chưa đo.
4. Wave2 4 trạng thái là hợp đồng UX với người dùng — không thêm trạng thái thứ 5.
