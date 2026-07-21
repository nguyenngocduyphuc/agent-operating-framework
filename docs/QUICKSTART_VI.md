# AOF — Bắt đầu trong 5 phút (không cần biết code)

Bạn không cần biết git, không cần biết test, không cần biết MCP là gì.
Bạn chỉ cần trả lời được 4 câu khi máy làm việc cho mình:

1. Máy đang làm gì?
2. Xong chưa — bằng chứng đâu?
3. Kẹt ở đâu, tôi phải làm gì?
4. Có phiên nào giẫm chân nhau không?

AOF trả lời cả 4 câu đó, tự động.

**Hiệu quả dùng AOF (không cần gõ lệnh):** khi trợ lý đã gắn MCP AOF,
hỏi “trạng thái” / gọi `status_report` — máy tự kèm khối **Hiệu quả 24 giờ**.
File luôn có sẵn để mở: `~/.aof/estate/HIEU_QUA_HOM_NAY.md` (cập nhật mỗi phiên).

## Bước 1 — Cài (1 lần duy nhất)

Mở Terminal, dán từng dòng:

```bash
git clone https://github.com/nguyenngocduyphuc/agent-operating-framework
cd agent-operating-framework
pip install .
```

## Bước 2 — Chuẩn bị thư mục dự án của bạn

```bash
cd /đường/dẫn/dự/án/của/bạn
aof init
```

Lệnh này tạo tập luật mặc định và dấu mốc làm việc. Chạy lại bao nhiêu lần
cũng an toàn.

## Bước 3 — Kiểm tra máy sẵn sàng chưa

```bash
aof doctor
```

Máy tự kiểm 6 thứ và in kết quả tiếng Việt. Nếu có dấu ✘, làm đúng một việc
ghi ở dòng "Bước tiếp theo" rồi chạy lại. Khi thấy `✅ SẴN SÀNG` là xong.

## Bước 4 — Nối với trợ lý AI (1 lần duy nhất)

Dùng Claude Code:

```bash
claude mcp add aof -- aof start-mcp-server
```

Dùng Codex/Cursor: mở phần cấu hình MCP của ứng dụng và thêm:

```json
{ "mcpServers": { "aof": { "command": "aof", "args": ["start-mcp-server"] } } }
```

## Dùng hằng ngày — chỉ cần 2 câu

Dán vào trợ lý AI khi giao việc:

> Dùng AOF cho mục tiêu này: «mô tả việc bằng lời thường».
> Lên kế hoạch, giữ đúng phạm vi, hỏi tôi trước việc rủi ro,
> kiểm chứng kết quả, và báo cáo bằng tiếng Việt thường.

Muốn biết tình hình bất cứ lúc nào:

> Gọi status_report cho tôi.

Máy sẽ trả về 1 trong 4 trạng thái — **Bị chặn / Đang chuẩn bị / Sẵn sàng /
Xong-có-bằng-chứng** — luôn kèm "Bước tiếp theo". Không có trạng thái thứ năm,
không có báo cáo mơ hồ.

## AOF bảo vệ bạn khỏi những gì

| Rủi ro thật (đã xảy ra) | AOF chặn thế nào |
|---|---|
| Máy báo "xong" nhưng thực ra chưa làm | Bằng chứng phải do máy chủ tự kiểm, không tin lời khai |
| Hai phiên cùng sửa một việc, đè mất công nhau | Ổ khoá nhiệm vụ: phiên thứ hai bị từ chối ngay |
| Sửa lan sang chỗ không được đụng | Soát phạm vi tự động trước khi cho đóng việc |
| Đổi cấu hình xong luật âm thầm mất hiệu lực | Luật cũ được tự dịch + cảnh báo, không bao giờ tắt câm |
