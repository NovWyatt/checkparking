# Check Vehicle OCR v1.9.2

## Thay đổi chính

- Tăng tốc FAST và Cân bằng trên ảnh độ phân giải cao bằng cách giới hạn ảnh làm việc ở cạnh dài 1280 trước detector/OCR.
- Giữ nguyên metadata kích thước ảnh và ánh xạ bbox về tọa độ ảnh gốc để preview, review và xuất dữ liệu không bị sai lệch.
- Giữ PP-OCRv6 Small làm model mặc định và không thay đổi hành vi của chế độ Quét kỹ.
- Giữ detector-first, one-plate-per-image, định dạng biển số, lọc timestamp/watermark và chính sách AI/Tesseract có điều kiện của v1.9.1.
- Bổ sung regression guard cho resize, bbox, early exit, số lần OCR và output định dạng.

Trên bộ ảnh nội bộ được cấp quyền, bản vá giảm thời gian FAST và Cân bằng, đồng thời giảm số kết quả cần review so với pipeline trước khi tối ưu. Đây không phải tuyên bố accuracy trên dữ liệu production.
