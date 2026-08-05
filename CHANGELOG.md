# Changelog

## 1.9.3 — Giao diện mượt hơn khi quét

- Tách công việc nhận diện khỏi giao diện để giảm hiện tượng đứng hoặc khựng trong lúc PP-OCRv6 Small xử lý ảnh.
- Giữ nguyên PP-OCRv6 Small, detector, chính sách resize FAST/Cân bằng và kết quả regression OCR.
- Giới hạn một lần tự khởi động lại công cụ nhận diện cho mỗi batch; nếu không phục hồi được, app dừng an toàn và giữ kết quả đã hoàn thành.
- Bổ sung kiểm tra heartbeat, startup/shutdown, thứ tự kết quả, cancel, crash/restart và không để lại tiến trình sau khi đóng app.

## 1.9.2 — Tăng tốc ảnh độ phân giải cao

- FAST và Cân bằng giới hạn ảnh làm việc ở cạnh dài 1280 trước detector/OCR để giảm chi phí trên ảnh điện thoại độ phân giải cao.
- Kích thước ảnh và bbox trong kết quả vẫn dùng tọa độ ảnh gốc; crop, formatter, one-plate-per-image và bộ lọc nhiễu được giữ nguyên.
- PP-OCRv6 Small tiếp tục là model mặc định; chế độ Quét kỹ không thay đổi hành vi.
- Thêm regression guard không phụ thuộc tốc độ máy để khóa kích thước ảnh làm việc, số lần OCR, early exit, output định dạng và phép ánh xạ bbox.

## 1.9.1 — Sửa nhận nhầm chữ trên ảnh thành biển số

- Mặc định mỗi ảnh chỉ xuất một biển số primary; lựa chọn nhiều biển chỉ giữ các vùng biển vật lý khác nhau do detector tìm thấy.
- FAST và Cân bằng chuyển sang detector-first, OCR crop giới hạn và early exit; không còn OCR toàn cảnh sau khi đã có biển rõ.
- Lọc timestamp, watermark, địa chỉ và text overlay bằng điều kiện plate-like; nhiễu bị lưu debug là `REJECTED_NOISE`, không xuất Excel hoặc sheet `Bien_so_dac_biet`.
- Tesseract chỉ nhận crop detector, còn AI hybrid chỉ nhận ảnh mà primary plate thật sự cần review.
- Thêm thống kê detector/OCR/fallback, phần chẩn đoán candidate ẩn mặc định và regression gate 18 ảnh/18 primary plates.

## 1.9.0 — OCR runtime đã kiểm thử và Tesseract cài một chạm

- Nâng runtime đóng gói lên PaddleOCR 3.7.0, PaddlePaddle 3.3.1 và PaddleX 3.7.2.
- Đặt PP-OCRv6 Small làm model mặc định; PP-OCRv6 Tiny phục vụ chế độ tiết kiệm tài nguyên, còn PP-OCRv5 được giữ để quay lại khi cần.
- Thêm metadata runtime có version, model, hash và commit build; giao diện hiển thị version thực tế của công cụ nhận diện.
- Đóng gói Tesseract 5.5.3 Windows x64 từ source tag chính thức, kèm tessdata_fast `eng`/`osd` đã pin, hash từng file và cài đặt một chạm vào LocalAppData.
- Tesseract chỉ được dùng làm fallback có điều kiện; ứng dụng giữ bằng chứng từ cả hai engine và đánh dấu review khi hai kết quả không đủ rõ ràng.
- Thêm manifest/model component, kiểm tra hash, giới hạn kích thước, chống Zip Slip, staging nguyên tử và rollback theo version.

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
