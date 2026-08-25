# Triển khai máy chủ bản quyền Cloudflare

Tài liệu này triển khai `license_portal` cho Check Vehicle OCR. Worker dùng D1 để lưu HMAC của key và thiết bị, không lưu key dạng chữ thường. Mã quản trị và khoá ký chỉ tồn tại trong Cloudflare Secrets.

## Chuẩn bị

- Đăng nhập đúng tài khoản Cloudflare đang quản lý tên miền.
- Chọn một subdomain riêng, ví dụ `license.ten-mien-cua-ban`. Không dùng chung với website đang vận hành.
- Cài Node.js 20+ và đăng nhập Wrangler trong thư mục `license_portal`.

## Tạo D1 và cập nhật cấu hình

Tại `license_portal`, chạy:

```powershell
npx.cmd wrangler d1 create checkvehicle-license
```

Lệnh trả về `database_id`. Thay đúng giá trị đó vào trường `database_id` trong `license_portal/wrangler.jsonc`, rồi áp dụng schema:

```powershell
npx.cmd wrangler d1 migrations apply checkvehicle-license --remote --config wrangler.jsonc
```

## Tạo bí mật

Sinh bộ secrets quản trị và cặp ký Ed25519 bằng các lệnh sau trên máy quản trị. Các lệnh chỉ in giá trị ra màn hình, không tự tạo file bí mật. Công cụ đầu tiên sẽ yêu cầu nhập mã quản trị hai lần mà không hiện ký tự đã gõ.

```powershell
.\.venv\Scripts\python.exe -B tools\generate_license_admin_secrets.py
.\.venv\Scripts\python.exe -B tools\generate_license_signing_key.py
```

Đặt bốn secrets bằng các lệnh dưới đây. Wrangler sẽ hỏi giá trị bằng một prompt riêng. Không chép những giá trị này vào file `.env`, Git, ảnh chụp màn hình hoặc release.

```powershell
npx.cmd wrangler secret put ADMIN_CODE_SHA256 --config wrangler.jsonc
npx.cmd wrangler secret put ADMIN_SESSION_SECRET --config wrangler.jsonc
npx.cmd wrangler secret put LICENSE_KEY_PEPPER --config wrangler.jsonc
npx.cmd wrangler secret put LICENSE_SIGNING_PRIVATE_KEY_B64 --config wrangler.jsonc
```

Giá trị cho từng secret:

- `ADMIN_CODE_SHA256`: SHA-256 Base64URL của mã quản trị do chủ sở hữu tự chọn. Mã gốc không được lưu trên Cloudflare.
- `ADMIN_SESSION_SECRET`: chuỗi ngẫu nhiên dài, dùng ký phiên quản trị.
- `LICENSE_KEY_PEPPER`: chuỗi ngẫu nhiên dài, dùng HMAC key, thiết bị và IP đã ẩn danh.
- `LICENSE_SIGNING_PRIVATE_KEY_B64`: dòng private key do công cụ sinh ra.

Thời hạn offline mặc định 7 ngày được đặt bằng biến không nhạy cảm `OFFLINE_GRACE_DAYS` trong `wrangler.jsonc`. Có thể đổi từ 1 đến 30 ngày trước khi deploy.

## Deploy và gắn tên miền

```powershell
npm.cmd run build
npx.cmd wrangler deploy --config wrangler.jsonc
```

Để Worker tự gắn custom domain khi deploy, thêm route sau vào `wrangler.jsonc`. Cloudflare sẽ tự tạo DNS record trong zone đang quản lý.

```json
"routes": [
  {
    "pattern": "license.ten-mien-cua-ban",
    "custom_domain": true
  }
]
```

Có thể gắn cùng custom domain trong Cloudflare Dashboard tại **Worker > Settings > Domains & Routes > Add > Custom Domain**.

Kiểm tra không cần đăng nhập bằng cách mở:

```text
https://license.ten-mien-cua-ban/api/health
```

Kết quả phải là JSON có `"ok": true`.

## Khóa bản phát hành desktop

Trước khi build Check Vehicle OCR v1.10.0, điền hai giá trị công khai vào `check_vehicle_ocr/license_config.py`:

- `LICENSE_SERVICE_URL`: URL HTTPS Worker trên subdomain vừa gắn.
- `LICENSE_SIGNING_PUBLIC_KEY_B64`: dòng public key từ công cụ sinh key.

Không đóng gói EXE nếu một trong hai giá trị còn trống. Chỉ public key được phép đi cùng ứng dụng.

## Vận hành

- Mở URL subdomain trong trình duyệt để vào trang quản trị, nhập mã quản trị bí mật.
- Key mới chỉ hiện một lần. Sao chép và gửi người dùng ngay.
- Mặc định mỗi key có một thiết bị. Dùng **Đặt lại máy** khi đổi máy hợp lệ.
- Dùng **Thu hồi** để vô hiệu hoá key. Bản đã kích hoạt sẽ bị chặn ở lần xác thực tiếp theo, tối đa sau 7 ngày offline.
- Nếu mất mã quản trị, thay `ADMIN_CODE_SHA256` và `ADMIN_SESSION_SECRET`, sau đó deploy lại Worker. Phiên cũ sẽ hết hiệu lực.

## Kiểm tra sau triển khai

1. Tạo một key có thời hạn và kích hoạt trên một máy thử.
2. Khởi động lại ứng dụng khi không có mạng, xác nhận còn chạy trong thời gian offline grace.
3. Thu hồi key trong dashboard, kết nối lại máy thử và chọn **Kiểm tra lại**.
4. Xác nhận quét ảnh, xuất Excel và đối chiếu đều bị chặn sau thu hồi.
5. Kiểm tra `settings.json` trên máy thử không chứa key gốc.
