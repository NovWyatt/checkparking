# Codex Vietnamese Rules Kit

Bộ file này dùng để copy vào mỗi dự án trước khi giao việc cho Codex hoặc các coding agent khác.
Mục tiêu chính:

- Bắt Codex đọc đúng bối cảnh dự án.
- Giữ tiếng Việt trong source code là UTF-8 trực tiếp, không mojibake, không HTML entity cho chữ tiếng Việt.
- Giảm lỗi sửa UI tiếng Việt bị biến thành `Ng&#224;y`, `R&#250;t ti&#7873;n`, `&#272;&#227;`, hoặc các chuỗi lỗi như `Ã`, `Â`, `á»`, `áº`.
- Có prompt template dùng lại theo từng phase.
- Có script kiểm tra nhanh trước khi commit.

## Cách dùng nhanh

1. Copy toàn bộ các file trong thư mục này vào root dự án.
2. Trước khi đưa prompt cho Codex, nhắc Codex đọc các file:
   - `AGENTS.md`
   - `CODEX_RULES_PROMPT.md`
   - `ENCODING_RULES.md`
   - `PROJECT_CONTEXT_TEMPLATE.md` nếu dự án có điền thông tin riêng
3. Khi viết prompt mới, dùng mẫu trong `CODEX_TASK_TEMPLATE.md`.
4. Sau khi Codex sửa xong, chạy:

```bash
php scripts/check-vietnamese-encoding.php
```

Hoặc trên Windows:

```bat
scripts\check-vietnamese-encoding.bat
```

## File quan trọng

- `AGENTS.md`: file hướng dẫn ngắn để coding agent đọc trước.
- `CODEX_RULES_PROMPT.md`: luật tổng hợp cho Codex.
- `ENCODING_RULES.md`: luật riêng về tiếng Việt/encoding.
- `PROJECT_CONTEXT_TEMPLATE.md`: mẫu ghi bối cảnh từng dự án.
- `CODEX_TASK_TEMPLATE.md`: mẫu prompt mỗi lần giao việc.
- `.editorconfig`: ép UTF-8, newline ổn định.
- `.gitattributes`: giúp Git giữ text encoding/EOL ổn định.
- `scripts/check-vietnamese-encoding.php`: kiểm tra BOM, UTF-8, mojibake, HTML entity tiếng Việt.

## Khuyến nghị

Với mỗi repo, nên điền lại `PROJECT_CONTEXT_TEMPLATE.md` rồi đổi tên thành `PROJECT_CONTEXT.md`.
Khi gửi prompt cho Codex, luôn copy block “Yêu cầu cực kỳ quan trọng về tiếng Việt/encoding” từ `ENCODING_RULES.md` hoặc `CODEX_TASK_TEMPLATE.md`.
