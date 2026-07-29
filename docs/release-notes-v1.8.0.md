# Check Vehicle OCR v1.8.0

- Chọn loại biển số theo batch: Xe máy, Ô tô hoặc Không tự định dạng.
- Tự định dạng đúng các mẫu biển xe máy và ô tô được hỗ trợ; biển đặc biệt được giữ nguyên và xuất thêm sheet `Bien_so_dac_biet`.
- Sửa trạng thái tiến trình khi OCR cục bộ đã xong nhưng AI hoặc tổng hợp kết quả còn chạy.
- Tối ưu chế độ PaddleOCR + AI: chỉ gửi ảnh cần kiểm tra theo mức người dùng chọn; mặc định không gửi ảnh rõ, độ tin cậy cao.
- Update Center tối giản: ứng dụng, công cụ nhận diện và Tesseract dự phòng đều có một hành động chính.
- Tesseract chỉ cài từ gói có manifest/SHA-256 do dự án kiểm soát; không tải installer bên thứ ba.
- Thêm cuộn cho trang dài, bộ icon Check Vehicle OCR gốc và tăng tương phản giao diện Light/Dark.

Xem báo cáo kiểm chứng, giới hạn và nguồn component tại `docs/v1.8.0-release-completion-report.md`.
