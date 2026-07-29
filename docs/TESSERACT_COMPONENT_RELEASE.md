# Phát hành Tesseract dự phòng

Tesseract là thành phần tùy chọn. Check Vehicle OCR không tải installer Windows ngẫu nhiên từ Internet.

Chỉ tạo asset component khi người phát hành đã xác minh nguồn, license, nội dung ZIP và SHA-256.

ZIP phải có tối thiểu:

- `tesseract.exe` và DLL cần thiết;
- `tessdata/eng.traineddata`;
- `LICENSE` hoặc `NOTICE` của bản build;
- `component-manifest.json` chứa phiên bản, Windows x64, URL asset, SHA-256, loại `zip`, license và nguồn.

Trước khi upload vào GitHub Release của `NovWyatt/checkparking`, chạy `tesseract --version`, `--list-langs` với thư mục `tessdata`, OCR smoke trên fixture nội bộ, rồi ghi checksum thật. Khi chưa có asset thỏa các điều kiện này, để trống nguồn manifest trong ứng dụng; người dùng vẫn có thể chọn bản Tesseract đã cài mà không ảnh hưởng PaddleOCR.
