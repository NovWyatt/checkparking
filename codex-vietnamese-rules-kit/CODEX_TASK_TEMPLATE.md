# CODEX_TASK_TEMPLATE.md

Dùng mẫu này để giao việc cho Codex ở mỗi phase.

---

## Prompt mẫu

Bạn đang sửa dự án `<TÊN_DỰ_ÁN>`.

Trước khi sửa, bắt buộc đọc các file sau nếu tồn tại:

- `AGENTS.md`
- `CODEX_RULES_PROMPT.md`
- `ENCODING_RULES.md`
- `PROJECT_CONTEXT.md`
- `README.md`

Yêu cầu cực kỳ quan trọng về tiếng Việt/encoding:

1. Tất cả file phải là UTF-8.
2. Không tạo mojibake như: `Ã`, `Â`, `Ä`, `Æ`, `�`, `á»`, `áº`, `Â·`.
3. Không dùng teencode như: `ko`, `k`, `dc`, `đc`, `mk`, `mn`, `ae`, `vs`, `j`, `z`, `hok`, `khum`.
4. Dùng tiếng Việt chuẩn, trang trọng.
5. Nếu có `ENCODING_RULES.md`, `CODEX_RULES_PROMPT.md`, `AGENTS.md`, `PROJECT_CONTEXT.md` thì phải đọc trước khi sửa.
6. Khi sửa file, mọi chữ tiếng Việt mới hoặc chữ tiếng Việt nằm trong phạm vi sửa phải dùng UTF-8 trực tiếp, không dùng HTML entity như `&#...;`. Đặc biệt không đặt HTML entity trong `{{ ... }}` của Blade.

Nhiệm vụ phase này:

- `<việc 1>`
- `<việc 2>`
- `<việc 3>`

Giới hạn phạm vi:

- Không đổi stack.
- Không thêm React/Vue/Tailwind/Bootstrap nếu dự án không dùng.
- Không push/deploy.
- Không xoá nghiệp vụ cũ.
- Không sửa ngoài phạm vi nếu không cần.

Sau khi sửa xong, hãy chạy kiểm tra phù hợp:

```bash
php scripts/check-vietnamese-encoding.php
git diff --check
git status --short
```

Nếu là Laravel/PHP, kiểm tra thêm:

```bash
php -l <các file PHP đã sửa>
php artisan route:list
php artisan view:clear
```

Báo cáo cuối cùng cần có:

- Danh sách file đã sửa.
- Nội dung chính đã thay đổi.
- Lệnh kiểm tra đã chạy và kết quả.
- Lỗi còn lại nếu có.

---

## Mẫu ngắn để dán nhanh

Đọc `AGENTS.md`, `CODEX_RULES_PROMPT.md`, `ENCODING_RULES.md`, `PROJECT_CONTEXT.md` trước khi sửa. Giữ toàn bộ file UTF-8. Không mojibake, không HTML entity cho tiếng Việt, không teencode. Chữ tiếng Việt trong source phải là tiếng Việt trực tiếp, ví dụ `Ngày`, `Rút tiền`, `Đã duyệt`, không được là `Ng&#224;y`, `R&#250;t ti&#7873;n`, `&#272;&#227;`. Không push/deploy. Sửa đúng phạm vi. Sau khi sửa chạy `php scripts/check-vietnamese-encoding.php` và báo cáo file đã sửa + lệnh đã chạy.
