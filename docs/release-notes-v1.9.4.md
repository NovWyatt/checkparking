# Check Vehicle OCR v1.9.4

## Ưu tiên tốc độ vẫn đọc được biển số

- Preset **Ưu tiên tốc độ** nay dùng PP-OCRv6 Tiny đúng theo lựa chọn trên giao diện; chế độ Cân bằng giữ PP-OCRv6 Small.
- Khi detector crop không đọc được biển, FAST thực hiện một lượt OCR toàn ảnh có giới hạn, sau đó chỉ thử tối đa hai vùng trung tâm xe nếu vẫn chưa có biển hợp lệ.
- Các ảnh đã có biển rõ vẫn dừng sớm, nên rescue không áp dụng cho đa số ảnh.

## Kiểm chứng nội bộ

Trên 16 ảnh điện thoại 1920×2560 do người dùng cung cấp, FAST + Tiny đọc được 16/16 ảnh:

- 57,08 ảnh/phút khi detector ONNX đã sẵn sàng trong cache;
- 6,76 ảnh/phút khi tắt detector ONNX, vẫn đọc đủ 16/16 nhờ fallback cục bộ.

Bộ ảnh không có manifest nhãn chuẩn, vì vậy số liệu trên không phải tuyên bố về độ chính xác exact-match hoặc ký tự. OCR cục bộ không gửi ảnh ra ngoài.

Model detector ONNX có điều khoản phân phối riêng; file weights không được đưa vào commit source này khi chưa có manifest nguồn và điều khoản đã xác minh.
