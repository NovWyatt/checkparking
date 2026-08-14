# Check Vehicle OCR v1.9.5

## Fast Adaptive Verify

- Chế độ **Nhanh** tiếp tục dùng PP-OCRv6 Tiny cho đường quét chính.
- Nếu Tiny đọc được chuỗi giống biển số nhưng chuỗi đó không khớp một trong các cấu trúc biển Việt Nam chuẩn mà ứng dụng hỗ trợ, ứng dụng chỉ xác minh lại crop đó một lần bằng PP-OCRv6 Small.
- Predictor Small được khởi tạo lười; ảnh không có lỗi cấu trúc vẫn dùng Tiny và dừng sớm như trước.

## Kết quả nội bộ

Trên 16 ảnh xe máy 1920×2560 do người dùng cung cấp và được đối chiếu nhãn thủ công tại máy local, FAST đạt 16/16 exact match, 100% độ chính xác ký tự và 65,55 ảnh/phút. Bản 1.9.4 đạt 15/16 exact match, 98,13% độ chính xác ký tự và 75,12 ảnh/phút trên cùng điều kiện.

Nhãn benchmark là bằng chứng kiểm tra nội bộ, không đại diện cho mọi loại biển, camera hoặc điều kiện ánh sáng. OCR cục bộ không gửi ảnh ra ngoài.
