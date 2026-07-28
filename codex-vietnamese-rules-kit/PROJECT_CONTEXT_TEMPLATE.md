# PROJECT_CONTEXT.md

> Copy file này thành `PROJECT_CONTEXT.md` trong từng dự án rồi điền lại cho đúng bối cảnh.

## 1. Tên dự án

- Tên dự án: `<điền tên dự án>`
- Mục tiêu: `<điền mục tiêu>`
- Trạng thái hiện tại: `<điền trạng thái>`

## 2. Stack công nghệ

- Backend: `<Laravel/PHP/Node/...>`
- Frontend: `<Blade/vanilla JS/...>`
- Database: `<MySQL/PostgreSQL/SQLite/...>`
- CSS: `<plain CSS/...>`
- Build tool: `<không dùng npm/Vite nếu không cần/...>`

## 3. Quy tắc dự án

- Không đổi stack nếu chưa được yêu cầu.
- Không thêm framework frontend nếu chưa được yêu cầu.
- Không xoá chức năng cũ nếu chưa được yêu cầu.
- Không push/deploy nếu chưa được yêu cầu.
- Giữ tiếng Việt chuẩn, UTF-8 trực tiếp.
- Không dùng HTML entity cho chữ tiếng Việt.

## 4. Vai trò người dùng

- Admin: `<mô tả>`
- User: `<mô tả>`
- Vai trò khác: `<mô tả>`

## 5. Route/trang quan trọng

- `/`: `<mô tả>`
- `/login`: `<mô tả>`
- `/dashboard`: `<mô tả>`
- Route khác: `<mô tả>`

## 6. File/thư mục cần cẩn thận

- `routes/web.php`
- `app/Models`
- `app/Http/Controllers`
- `resources/views`
- `database/migrations`
- `database/seeders`

## 7. Lệnh kiểm tra thường dùng

```bash
php -l path/to/file.php
php artisan route:list
php artisan view:clear
php artisan config:clear
php scripts/check-vietnamese-encoding.php
git diff --check
git status --short
```

## 8. Ghi chú riêng

- `<điền ghi chú riêng của dự án>`
