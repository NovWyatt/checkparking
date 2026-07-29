# Check Vehicle OCR v1.9.1

## Sửa nhận nhiều biển giả trong một ảnh

- Mặc định **Một biển số — Khuyên dùng**: mỗi ảnh chỉ xuất một biển số primary tốt nhất. Chế độ nhiều biển chỉ xuất khi detector tìm thấy nhiều vùng biển vật lý khác nhau.
- `Nhanh` và `Cân bằng` nay chạy detector-first, OCR crop có giới hạn và dừng sớm ngay khi có biển hợp lệ, đủ tin cậy. Không còn quét OCR toàn cảnh sau khi đã đọc đúng biển.
- Timestamp, watermark, địa chỉ, nhãn ứng dụng và text ngắn như `M`, `Y`, `LOL` bị loại là nhiễu; chúng không xuất Excel, không tăng tổng biển và không vào sheet `Bien_so_dac_biet`.

## Review và fallback chính xác hơn

- Biển đặc biệt chỉ được đánh dấu khi vẫn có cấu trúc giống biển đăng ký; text OCR rác không còn bị coi là biển đặc biệt.
- Tesseract chỉ chạy trên crop vùng biển, không OCR toàn ảnh điện thoại.
- Hybrid AI chỉ nhận ảnh mà primary plate thật sự không đọc được, confidence thấp, mơ hồ hoặc không khớp mẫu; ảnh rõ không chờ AI.
- Chi tiết ảnh có phần chẩn đoán mở rộng (ẩn mặc định) để xem candidate được chọn, candidate bị loại và số lần gọi detector/OCR/fallback.

Không có API, Telegram hoặc dữ liệu ảnh người dùng nào được dùng trong automated tests.
