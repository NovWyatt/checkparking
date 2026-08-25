# Báo cáo sửa đăng nhập portal bản quyền

## Mục tiêu

Sửa lỗi `Cannot read properties of null (reading 'elements')` khi quản trị viên đăng nhập tại `license.wyattos.cyou`.

## Nguyên nhân

`fluent-text-field` và `fluent-select` là Web Component, không được browser đăng ký trong `HTMLFormElement.elements` như input HTML thuần. Portal đọc trực tiếp qua `form.elements`, khiến login thất bại và có thể gây lỗi tương tự tại biểu mẫu cấp key.

## Files changed

- `license_portal/src/admin.js`
- `license_portal/test/admin-ui.test.mjs`

## Thay đổi chính

- Thêm `formControl()` dùng `form.querySelector('[name="…"]')` để lấy trường biểu mẫu tương thích với Fluent Web Components.
- Áp dụng cho đăng nhập, chọn loại key, ngày hết hạn, số thiết bị và ghi chú.
- Reset rõ ràng giá trị của Fluent controls sau khi tạo key.
- Bổ sung test bảo vệ để portal không quay lại cách truy cập `form.elements`.

## Commands và kết quả

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run deploy
```

Tất cả hoàn thành thành công. Sau deploy, kiểm tra trực tiếp `https://license.wyattos.cyou/` cho thấy màn đăng nhập hiển thị đúng và không có console error.

## Không kiểm tra

Không tự gửi mã quản trị vào form. Quản trị viên cần dán mã từ clipboard để xác nhận luồng đăng nhập và cấp key thực tế.
