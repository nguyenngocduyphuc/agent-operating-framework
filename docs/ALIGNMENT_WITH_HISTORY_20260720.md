# Đối chiếu v0.3 với toàn bộ lịch sử /aof — 2026-07-20

*Nguồn đã khai quật: 16 file `docs/AOF_*` (seed → assessment → pivot → spec →
proven value → community readiness), `artifacts/team/AOF-V2/` (waves 1–3, bench
transcripts), `artifacts/team/AOF-PRODUCT/` (CAUSAL-VERDICT n=105, effectiveness,
vs-anthropic, flywheel), skill `/aof` (workspace + ~/.claude), artifact_index
(41 mục, 13 AOF), docs.nampham.net.*

## Dòng lịch sử (tóm tắt trung thực)

Seed: framework cho ORCHESTRATOR điều phối fleet worker (ponytail + Asana +
governed orchestration). 07-03: benchmark v2 bác luận điểm governance đơn-agent
→ pivot "measured productivity" → spec "GxP-grade, enforce CLAUDE.md". 07-04:
quay về giá trị tầng fleet ("bảo hiểm, không phải phép màu", 8/8 defect detect).
07-14: wave2 chốt no-code onboarding (2 prompt + **4 trạng thái: Planning /
Needs approval / Blocked / Done**); community readiness = "alpha pilot, chưa
public". **07-16: CAUSAL-VERDICT n=105, luật khóa trước → GO-RISK-LANE**:
scope-block 100% vs 43% (p=0.049, tái lập 2 lần); pass +11.6pp / fabrication
−11.6pp (directional); overhead +35% → **full-chain CHỈ cho lane rủi ro, lane
thường dùng lite; contract mặc định = bản C 7 dòng**. 07-17: đối chiếu chuẩn
Anthropic (khớp hooks/skills/orchestrator-workers; thiếu evaluator-optimizer
inline, visual verification; audit.jsonl nhiễm 3 schema). 07-18/19: đo thật 56
phiên — /aof bị đi vòng; 07-20: audit 3 P0 lớp kiểm soát.

## v0.3 đã build KHỚP lịch sử ở đâu

| v0.3 | Khớp với |
|---|---|
| Contract 7 trường trong core | Chính là contract C 7 dòng — arm THẮNG bench 16/07 |
| Task lease (git-common-dir) | Roadmap C2 audit 07-20 + "multi-session 1 working dir là rủi ro cấu trúc" (codex review 07-14) |
| Policy compat chống fail-open | Sự cố policy lệch schema 07-20 |
| status_report + QUICKSTART_VI | Wave2 no-code brief 07-14 (đúng hướng, sai tên trạng thái — xem dưới) |
| aof watch (mtime/size) | Watchdog mù 18 phút 07-20 |
| Không claim ROI bừa | Kỷ luật effectiveness 07-17 ("không đủ data → nói không đủ data") |

## v0.3 LỆCH lịch sử ở đâu (đây là chỗ "khác nhiều")

1. **Risk-lane — lệch phán quyết đã khóa.** GO-RISK-LANE quy định: full-chain
   mặc định CHỈ cho lane rủi ro (deploy/publish/đa-file/ghi dữ liệu/git-write);
   lane thường dùng lite (preflight + evidence) vì thuế +35%. Core v0.3 đang
   ALWAYS-ON full chain mọi lúc → nặng hơn luật. **Fix v0.3.2: policy `lanes`.**
2. **Tên 4 trạng thái.** Wave2 chốt Planning / Needs approval / Blocked / Done.
   v0.3 đặt Đang chuẩn bị / Sẵn sàng / Bị chặn / Xong — **thiếu hẳn "Needs
   approval"**, trong khi plan-gate + CEO duyệt (ceo_inbox, duyệt 2 tốc độ) là
   nghiệp vụ trung tâm của vận hành thật. **Fix: map lại 4 trạng thái, thêm
   needs_approval.**
3. **/aof thật là "nhân viên" ~15 nghiệp vụ** (improve ledger, skill health,
   ws map, plan-gate, ship_ledger, artifact_index, pin, wt...) map vào MCP cũ.
   Core canonical mới cover ~8 nghiệp vụ gate. Số còn lại thuộc **NP_AI adapter**
   — khi rewire skill /aof sang core mới, KHÔNG được rơi nghiệp vụ nào.
4. **Claim bán hàng đã có số mà chưa dùng.** Được phép claim (đã khóa ràng buộc):
   "chặn 100% yêu cầu vượt-scope (p<0.05, n=105, 2 lần đo độc lập)" + luôn kèm
   "+~35% thời gian trên task có gate". README/direction đang nói "chưa có số" —
   sai: scope-block ĐÃ significant; chỉ pass/fabrication là directional.
5. **Flywheel/schema:** audit.jsonl cũ đã nhiễm 3 schema; core mới ghi schema
   riêng nữa là schema thứ 4. **Fix: khai schema audit v2 chính thức + migration
   note, một writer một schema.**

## Local còn thiếu gì so với "toàn bộ lịch sử"

Gần như đủ: docs + artifacts/team + artifact_index + transcripts ~/.claude/projects
đều local (docs.nampham.net render từ chính các file này). Thiếu thật sự:
(a) các artifact claude.ai mới sau 19/07 chưa vào artifact_index (index dừng ở
41 mục — vd "Chờ anh quyết — notebooklm-stack", "Sổ lỗi B2" chưa có); (b) nội
dung hội thoại duyệt/chỉnh trong chat web chưa export. Cách vá rẻ nhất: duy trì
kỷ luật `/aof artifacts add` cho mọi artifact trình CEO.

## Việc tiếp theo (v0.3.2 — theo đúng luật đã khóa 16/07)

1. Policy `lanes`: risk = full chain · normal = lite. Test cả hai lane.
2. status_report: Planning / Needs approval / Blocked / Done (vi/en).
3. README: đưa claim causal đúng ràng buộc trung thực.
4. Audit schema v2 thống nhất một writer.
5. Rewire skill /aof → core mới theo bảng nghiệp vụ, phần fleet ở adapter.
