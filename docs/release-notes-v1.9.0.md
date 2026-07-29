# Check Vehicle OCR v1.9.0

## Công cụ nhận diện mới đã kiểm thử

- Runtime đóng gói dùng PaddleOCR 3.7.0, PaddlePaddle 3.3.1 và PaddleX 3.7.2.
- PP-OCRv6 Small là mặc định; PP-OCRv6 Tiny phục vụ chế độ tiết kiệm tài nguyên.
- PP-OCRv5 Mobile vẫn tồn tại để quay lại model trước mà không cài lại ứng dụng.
- Thẻ Công cụ nhận diện hiển thị version thực tế và model đang active.

## Tesseract dự phòng cài một chạm

- Bổ sung component Windows x64 Tesseract 5.5.3 build từ source chính thức,
  kèm `eng`/`osd` của tessdata_fast đã pin.
- Nút Cài đặt/Cập nhật tải từ GitHub Release của dự án, kiểm SHA-256 archive và
  từng file, chạy smoke test rồi mới kích hoạt vào LocalAppData.
- Cài đặt, cập nhật và rollback không yêu cầu quyền Administrator, PATH hoặc
  installer bên thứ ba.

## Pipeline an toàn hơn

- Tesseract chỉ là fallback khi PaddleOCR không đọc được, độ tin cậy thấp,
  có ambiguity, không khớp format hoặc người dùng bật OCR dự phòng.
- Ứng dụng lưu candidate/confidence của cả PaddleOCR và Tesseract, chỉ chọn tự
  động khi bằng chứng đủ rõ; trường hợp khác được đánh dấu kiểm tra.
- Model và component dùng staging versioned, hash, giới hạn archive và chống
  Zip Slip trước khi kích hoạt.

Không có API hoặc Telegram thật nào được gọi trong automated tests.
