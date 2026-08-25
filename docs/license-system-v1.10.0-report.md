# Báo cáo hệ thống bản quyền v1.10.0

## Mục tiêu

Chuẩn bị hệ thống key có thời hạn hoặc vĩnh viễn cho Check Vehicle OCR, có thể thu hồi từ trang quản trị Cloudflare mà không dùng Cloudflare Access email.

## Thành phần thay đổi

- `license_portal/`: Cloudflare Worker, D1 migration và dashboard quản trị dùng Fluent Web Components.
- `check_vehicle_ocr/license_service.py`: kiểm tra chứng nhận Ed25519 trên máy, kích hoạt và xác thực lại qua Worker.
- `check_vehicle_ocr/app.py` và `check_vehicle_ocr/ui/license_dialog.py`: cửa sổ kích hoạt, xác thực nền và chặn quét, xuất Excel, đối chiếu khi bản quyền chưa hợp lệ.
- `check_vehicle_ocr/config.py`: chỉ lưu mã cài đặt ngẫu nhiên, certificate đã ký và signature. Key gốc bị loại khi migrate cấu hình.
- `tools/generate_license_admin_secrets.py` và `tools/generate_license_signing_key.py`: sinh giá trị Cloudflare Secret tại máy quản trị và public key để nhúng vào bản release.
- `docs/cloudflare-license-deployment.md`: hướng dẫn tạo D1, secrets, Worker và custom domain.

## Thiết kế bảo mật

- D1 chỉ lưu HMAC của key và HMAC của mã cài đặt. Key gốc chỉ được hiển thị một lần lúc cấp.
- Mã quản trị được so sánh bằng SHA-256 hash. Phiên quản trị là cookie ký, HttpOnly, Secure và SameSite Strict.
- Private Ed25519 key chỉ nằm trong Cloudflare Secret. EXE chỉ chứa public key.
- Mã cài đặt là giá trị ngẫu nhiên riêng của ứng dụng, không thu thập serial ổ cứng, MAC hay hardware fingerprint.
- Certificate hợp lệ dùng offline tối đa 7 ngày trước khi yêu cầu kết nối lại. Thu hồi có hiệu lực khi máy xác thực lại.

## Kiểm tra đã chạy

```powershell
# Trong thư mục license_portal
npm.cmd test
npm.cmd run build
npx.cmd wrangler deploy --dry-run --config wrangler.jsonc

# Trong thư mục gốc project
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests tools main.py
.\.venv\Scripts\python.exe -B tests\license_service_test.py
.\.venv\Scripts\python.exe -B tests\license_app_integration_test.py
.\.venv\Scripts\python.exe -B tests\ui_smoke_test.py
.\.venv\Scripts\python.exe -B tests\services_test.py
.\.venv\Scripts\python.exe -B tests\ui_simplification_test.py
.\.venv\Scripts\python.exe -B tests\reconciliation_test.py
.\.venv\Scripts\python.exe -B tests\results_import_test.py
.\.venv\Scripts\python.exe -B tests\smoke_test.py
```

Các lệnh trên đã hoàn tất thành công trong môi trường phát triển.

## Hạ tầng đã triển khai

- D1 riêng `checkvehicle-license` đã tạo ở khu vực APAC và migration `0001_initial.sql` đã áp dụng thành công.
- Worker `checkvehicle-license` đã deploy cùng dashboard và D1 binding.
- Custom domain `https://license.wyattos.cyou` đã được Cloudflare gắn thành công.
- Bốn secrets đã được lưu trong Cloudflare. Private signing key và mã quản trị không được ghi vào repository.
- `GET https://license.wyattos.cyou/api/health` trả `{ "ok": true }`.
- `LICENSE_SERVICE_URL` và Ed25519 public key đã được đặt cho release desktop v1.10.0.

## Chưa hoàn tất

- Chưa thực hiện end-to-end bằng key thật vì mã quản trị không được đọc hoặc lưu trong Codex. Quản trị viên cần đăng nhập dashboard, cấp một key thử và kích hoạt nó trên bản đóng gói.
- Chưa xác nhận theo thao tác quản trị thực tế: cấp key thử, kích hoạt EXE, thu hồi key và dùng “Kiểm tra lại” trên EXE.

## Bản đóng gói

- `release/CheckVehicleOCR/CheckVehicleOCR.exe` đã build thành công (v1.10.0, 44.5 MB).
- Đã mở trực tiếp EXE portable bằng Windows UI automation: hộp thoại “Kích hoạt Check Vehicle OCR” hiển thị ngay; các thao tác quét, xuất Excel và đối chiếu phía sau bị khóa khi chưa có certificate hợp lệ.
- Inno Setup 6.7.3 đã được cài từ package chính thức có kiểm tra hash, sau đó build thành công `installer/Output/CheckVehicleOCR-1.10.0-windows-x64-setup.exe`.
- `build_release_assets.ps1 -SkipBuild` đã tạo installer, portable ZIP, OCR model component, Tesseract component, manifest và `SHA256SUMS.txt` tại `release-assets/`.

## Rủi ro và bước tiếp theo

Mã quản trị đang chỉ có trên clipboard của máy quản trị. Cần lưu nó vào password manager trước khi clipboard bị thay thế. Sau khi phát hành, cấp một key thử, kích hoạt EXE, thu hồi key và chọn “Kiểm tra lại” để hoàn tất kiểm tra end-to-end.
