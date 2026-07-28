# Checklist kiểm tra Telegram thủ công

Không nhập bot token hoặc Chat ID vào source, test tự động, ảnh chụp màn hình hay issue. Tất cả bước dưới đây phải do người vận hành chủ động thực hiện trong trang **Telegram** của app.

| Tình huống | Thao tác | Kết quả mong đợi |
|---|---|---|
| Token đúng, Chat ID đúng | Bật Telegram, nhập thông tin, bấm **Gửi tin thử** | Status báo gửi thành công; chat nhận một tin thử. |
| Chat ID sai | Dùng Chat ID không hợp lệ, bấm tin thử | Status báo lỗi Telegram; app vẫn dùng được, không hiện token. |
| Token sai | Dùng token cố ý sai, bấm tin thử | Status báo lỗi xác thực; không log token đầy đủ. |
| Bot chưa được start | Dùng Chat ID đúng nhưng chưa mở cuộc trò chuyện với bot | Status báo lỗi từ Telegram; OCR không bị ảnh hưởng. |
| Timeout/mất mạng | Ngắt mạng tạm thời rồi bấm tin thử | Worker nền timeout ngắn và status báo lỗi; UI không treo. |
| Batch start | Bật `notify start`, chạy batch local nhỏ | Tối đa một thông báo bắt đầu. |
| Batch progress | Bật `notify progress`, step 10% | Không gửi mỗi ảnh, không trùng mốc phần trăm; tôn trọng minimum interval. |
| Batch complete | Bật `notify complete` | Tối đa một thông báo hoàn tất. |
| Batch error/cancel | Tạo lỗi ảnh local hoặc dừng batch | Nếu bật notify error, có thông báo phù hợp; kết quả đã hoàn thành vẫn giữ. |

Tự động test chỉ dùng fake notifier. Không có Telegram thật nào được gửi trong CI/smoke test.
