# Quản trị lịch sử — luật cho mọi phiên phát triển AOF

*2026-07-21. Sinh ra từ hai sự cố cùng ngày: (1) một phiên build 3 phase lệch
phán quyết causal đã khóa vì không đọc lịch sử; (2) đăng ký MCP bằng `-m
core.mcp_server` nạp nhầm bản `core/` copy ở root workspace — server trả 7
tool thay vì 8. Cả hai đều là lỗi "hành động không grounding" — đúng loại lỗi
AOF tồn tại để chặn, xảy ra ngay trong lúc phát triển AOF.*

## Luật 1 — History Gate (chặn build mù)

Mọi thay đổi hướng sản phẩm / enforcement semantics PHẢI cite trong plan:
`ALIGNMENT_WITH_HISTORY_20260720.md`, `CAUSAL-VERDICT-20260716.md` (luật
GO-RISK-LANE), và artifact_index 30 ngày gần nhất. Không cite được = không build.

## Luật 2 — Một canonical, mọi tham chiếu tuyệt đối

Canonical duy nhất: repo này. Mọi đăng ký MCP/CLI phải trỏ **đường dẫn file
tuyệt đối vào repo này**, không bao giờ `-m core.*` từ cwd (root workspace có
bản copy `core/` cũ sẽ shadow — đã xảy ra 21/07). Smoke bắt buộc sau đăng ký:
handshake phải trả **đúng 8 tools**.

## Luật 3 — Artifact trình CEO phải vào sổ ngay

Trình xong → `artifact_index.py add` cùng phiên. Index là bộ nhớ quyết định
của CEO; artifact ngoài sổ = quyết định sẽ bị phiên sau bỏ qua.

## Luật 4 — Quyết định mới phải thành file trong repo

Phán quyết bench, pivot định vị, quy tắc vận hành mới → `docs/decisions/`
(repo này) hoặc `artifacts/team/AOF-PRODUCT/` (workspace), cùng ngày. Chat
không phải nơi lưu quyết định.

## Luật 5 — Nhật ký là bằng chứng, không tô hồng

`aof log` in nguyên số từ sổ cưỡng chế, kể cả thất bại và va chạm. Mọi recap
cuối ngày dẫn số từ đây, không dẫn từ trí nhớ.
