# Changelog

## 1.8.0 — Chọn loại biển số, luồng hybrid rõ ràng và giao diện phát hành

- Thêm lựa chọn loại biển số theo batch: Xe máy, Ô tô hoặc Không tự định dạng.
- Chỉ tự thêm dấu gạch cho các mẫu được hỗ trợ; biển đặc biệt giữ nguyên và được đưa vào sheet `Bien_so_dac_biet`.
- Sửa tiến trình PaddleOCR + AI: OCR cục bộ hoàn tất trước, AI chỉ nhận ảnh cần kiểm tra và trạng thái hoàn tất không còn hiển thị “Đang xử lý”.
- Update Center rút gọn còn ba thẻ: ứng dụng, công cụ nhận diện PaddleOCR và Tesseract dự phòng.
- Thêm vùng cuộn dùng chung cho trang dài, bộ icon gốc, icon EXE/installer và cải thiện tương phản trạng thái.
- Tesseract chỉ cài một chạm từ gói do dự án xác minh; khi chưa có manifest, ứng dụng không tải installer bên thứ ba.

## 1.7.2 — Telegram first-notification rate-limit fix

- Fixed an edge case on freshly booted machines where the first Telegram
  notification could be treated as if it had already been rate-limited.

## 1.7.1 — Packaged GitHub Releases default

- Fresh packaged profiles now use the repository embedded in build metadata as
  their GitHub Releases source by default.
- An explicit operator choice to turn updates off is preserved.

## 1.7.0 — First managed-release version

- Added a single release version source and build metadata.
- Added isolated development/build dependency files, reproducible Windows asset scripts, and GitHub workflows.
- Added GitHub Release checksum fallback, pending verified-installer update helper, and release documentation.
- Kept PaddleOCR runtime staging separate from the main runtime.

This is the first version governed by this repository's release process; it is
not a claim about earlier historical release numbering.
