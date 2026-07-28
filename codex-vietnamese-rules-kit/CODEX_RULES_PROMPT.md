# CODEX_RULES_PROMPT.md

File này là rule tổng hợp để Codex đọc trước khi sửa dự án.

## 1. Nguyên tắc làm việc

- Đọc kỹ yêu cầu trước khi sửa.
- Sửa đúng phạm vi, không tự ý làm lan sang phần không liên quan.
- Không phá chức năng cũ để làm chức năng mới.
- Không tự ý đổi kiến trúc lớn nếu chưa được yêu cầu.
- Không tự ý thêm framework frontend nặng.
- Không tự ý đổi database engine, auth flow, role flow, permission flow.
- Không tự ý xoá migration, seeder, dữ liệu mẫu, route, controller, view đang được dùng.
- Không push, không deploy, không chạy lệnh nguy hiểm nếu chưa được yêu cầu rõ.

## 2. Quy tắc tiếng Việt bắt buộc

Luôn tuân thủ `ENCODING_RULES.md`.

Tóm tắt bắt buộc:

1. Tất cả file phải là UTF-8.
2. Không tạo mojibake như: `Ã`, `Â`, `Ä`, `Æ`, `�`, `á»`, `áº`, `Â·`.
3. Không dùng teencode như: `ko`, `k`, `dc`, `đc`, `mk`, `mn`, `ae`, `vs`, `j`, `z`, `hok`, `khum`.
4. Dùng tiếng Việt chuẩn, trang trọng.
5. Nếu có `ENCODING_RULES.md`, `CODEX_RULES_PROMPT.md`, `AGENTS.md`, `PROJECT_CONTEXT.md` thì phải đọc trước khi sửa.
6. Khi sửa file, mọi chữ tiếng Việt mới hoặc chữ tiếng Việt nằm trong phạm vi sửa phải dùng UTF-8 trực tiếp, không dùng HTML entity như `&#...;`. Đặc biệt không đặt HTML entity trong `{{ ... }}` của Blade.

## 3. Ví dụ đúng/sai về tiếng Việt trong source

Sai:

```php
echo 'Ng&#224;y t&#7841;o';
```

Đúng:

```php
echo 'Ngày tạo';
```

Sai:

```blade
<span>{{ 'R&#250;t ti&#7873;n' }}</span>
```

Đúng:

```blade
<span>{{ 'Rút tiền' }}</span>
```

Sai:

```js
const message = 'ÄÃ£ lá»ưu thÃ nh cÃ´ng';
```

Đúng:

```js
const message = 'Đã lưu thành công';
```

## 4. Quy trình trước khi sửa

1. Xác định stack dự án.
2. Xác định file liên quan.
3. Kiểm tra các rule trong repo.
4. Sửa nhỏ theo từng nhóm file.
5. Chạy kiểm tra cú pháp phù hợp.
6. Chạy kiểm tra encoding nếu có script.
7. Báo cáo rõ đã sửa file nào, kiểm tra gì, còn gì chưa làm.

## 5. Quy trình kiểm tra gợi ý

Với Laravel/PHP:

```bash
php -l path/to/file.php
php artisan route:list
php artisan view:clear
php artisan config:clear
php scripts/check-vietnamese-encoding.php
```

Với JavaScript:

```bash
node --check path/to/file.js
```

Với Git:

```bash
git diff --check
git status --short
```

## 6. Quy tắc báo cáo sau khi sửa

Báo cáo ngắn gọn:

- Đã sửa những file nào.
- Đã thay đổi nội dung gì.
- Đã chạy kiểm tra gì.
- Có lỗi còn lại hay không.
- Có file nào chưa đụng vì ngoài phạm vi hay không.
