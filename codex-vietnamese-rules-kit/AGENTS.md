# AGENTS.md

## Quy tắc bắt buộc trước khi sửa code

Trước khi sửa bất kỳ file nào, hãy đọc các file sau nếu tồn tại:

1. `CODEX_RULES_PROMPT.md`
2. `ENCODING_RULES.md`
3. `PROJECT_CONTEXT.md`
4. `PROJECT_CONTEXT_TEMPLATE.md`
5. `README.md`

## Ngôn ngữ và encoding

- Tất cả file phải là UTF-8, ưu tiên UTF-8 không BOM.
- Mọi chữ tiếng Việt trong code, Blade, HTML, CSS, JS, PHP, Markdown phải viết trực tiếp bằng tiếng Việt chuẩn.
- Không dùng HTML entity để thay chữ tiếng Việt.
- Không tạo mojibake.
- Không dùng teencode.

Sai:

```blade
Ng&#224;y
R&#250;t ti&#7873;n
&#272;&#227; duy&#7879;t
```

Đúng:

```blade
Ngày
Rút tiền
Đã duyệt
```

## Quy trình sửa code

- Ưu tiên sửa nhỏ, rõ, đúng phạm vi yêu cầu.
- Không đổi stack công nghệ nếu chưa được yêu cầu.
- Không xoá nghiệp vụ đang chạy nếu chưa có lệnh rõ ràng.
- Không đổi tên route, model, migration, bảng, cột nếu không cần thiết.
- Không push/deploy nếu người dùng chưa yêu cầu.
- Sau khi sửa, tự kiểm tra lỗi cú pháp và encoding nếu có thể.

## Khi sửa giao diện tiếng Việt

- Label, button, heading, placeholder, empty state, alert, validation message phải dùng tiếng Việt chuẩn.
- Không để lẫn tên cột DB tiếng Anh trên giao diện người dùng cuối nếu có thể dịch được.
- Không dùng từ viết tắt kiểu: ko, k, dc, đc, mk, mn, ae, vs, j, z, hok, khum.
