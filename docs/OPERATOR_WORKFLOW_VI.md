# Vòng lặp vận hành AOF — workflow và giá trị cho người dùng

*Người dùng đích: cá nhân vận hành AI agent, không cần biết git / test / tracker.*

## Vòng lặp hằng ngày (5 động tác, toàn tiếng Việt)

```
   ① GIAO VIỆC          "Dùng AOF cho mục tiêu này: …"
        │                → máy tự khoá nhiệm vụ (không ai chen ngang)
        ▼                → máy tự lập hợp đồng: làm gì, ở đâu, khi nào là xong
   ② MÁY LÀM            các cổng cưỡng chế chạy ngầm, người dùng không phải nhớ gì
        │
        ▼
   ③ HỎI BẤT CỨ LÚC NÀO "Gọi status_report"
        │                → 1 trong 4 trạng thái + bước tiếp theo
        ▼
   ④ NGHIỆM THU         máy chỉ được nói "Xong" khi kiểm chứng + soát phạm vi đã đạt
        │                → không đạt thì đóng dạng "Bị chặn", không có vùng xám
        ▼
   ⑤ CUỐI NGÀY          aof log
                         → nhật ký: xong gì có bằng chứng, kẹt gì, va chạm gì
```

Thêm một động tác khi nghi máy treo: `aof watch <file-output>` — phán theo
file có lớn lên không, không tin "phiên còn sống".

## Giá trị vận hành — đo được, không phải khẩu hiệu

| # | Nỗi đau thật (đã xảy ra trong vận hành NP_AI) | Động tác AOF | Giá trị đo được |
|---|---|---|---|
| 1 | Máy báo "xong" nhưng chưa làm — false success | Nghiệm thu cưỡng chế (④) | Số báo cáo sai lệch → 0 theo thiết kế: "Done" không thể phát ra nếu gate chưa đạt |
| 2 | Hai phiên giẫm chân, đè mất công nhau — 3 lần/ngày | Khoá nhiệm vụ (①) | Mỗi va chạm bị chặn đều được đếm trong `aof log` — hôm qua là mất công, hôm nay là một dòng thống kê |
| 3 | Worker treo 18 phút, watchdog mù | `aof watch` | Phát hiện treo trong ≤5 phút (ngưỡng chỉnh được) thay vì "đến lúc mở ra xem mới biết" |
| 4 | Đổi cấu hình → luật âm thầm mất hiệu lực | Policy compat + `aof doctor` | Fail-open do đổi tên khoá: không thể xảy ra câm lặng |
| 5 | Cuối ngày không biết máy đã làm gì | `aof log` | 1 lệnh, 5 giây, tiếng Việt — thay cho việc đọc JSON hoặc hỏi lại từng phiên |
| 6 | Cài đặt hỏng mà không biết hỏng ở đâu | `aof doctor` | 6 probe thật, chỉ ra đúng 1 bước cần sửa |

## Nguyên tắc thiết kế (vì sao tin được)

1. **Máy chủ tự kiểm, không tin lời khai** — mọi bằng chứng do orchestrator
   chạy lại; worker không bao giờ được cung cấp lệnh kiểm.
2. **Fail-closed** — nghi ngờ thì chặn; mọi từ chối kèm cách sửa cụ thể.
3. **Không vùng xám** — chỉ có 4 trạng thái; "Bị chặn" hiển thị to bằng "Xong".
4. **Nhật ký không tô hồng** — `aof log` in nguyên số liệu từ sổ cưỡng chế,
   kể cả thất bại và va chạm của chính nó.
