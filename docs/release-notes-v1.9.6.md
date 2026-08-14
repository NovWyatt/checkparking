# Check Vehicle OCR v1.9.6

## Detector cục bộ có quyền phân phối rõ ràng

- Detector biển số mặc định là YuNet từ OpenCV Zoo, được phát hành theo Apache-2.0 và đóng gói cùng ứng dụng.
- Bản cài/portable không tự tải detector ngoài Internet khi quét; model có SHA-256, attribution, commit nguồn và bản license trong gói.
- Detector YOLOv9 trước đây không còn được bundle hoặc tải runtime vì nguồn weights không cho đủ căn cứ xác nhận quyền phân phối.

## Fast Adaptive Verify

- FAST vẫn dùng PP-OCRv6 Tiny trên đường chính.
- Khi crop YuNet quá chặt, ứng dụng thử một crop lớn hơn có giới hạn; khi biển nghiêng mạnh hoặc Tiny không tạo chuỗi biển chuẩn, Small xác minh cùng crop một lần.

## Kết quả nội bộ

Trên 16 ảnh xe máy 1920×2560 do người dùng cung cấp và được đối chiếu nhãn thủ công tại máy local, FAST đạt 16/16 exact match, 100% độ chính xác ký tự và 47,68 ảnh/phút với detector YuNet Apache-2.0 đã bundle.

Đây là số liệu kiểm tra nội bộ, không đại diện cho mọi loại biển, camera hoặc điều kiện ánh sáng. OCR cục bộ không gửi ảnh ra ngoài.
