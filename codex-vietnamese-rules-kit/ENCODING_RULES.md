# ENCODING_RULES.md

## Yêu cầu cực kỳ quan trọng về tiếng Việt/encoding

1. Tất cả file phải là UTF-8.
2. Không tạo mojibake như: `Ã`, `Â`, `Ä`, `Æ`, `�`, `á»`, `áº`, `Â·`.
3. Không dùng teencode như: `ko`, `k`, `dc`, `đc`, `mk`, `mn`, `ae`, `vs`, `j`, `z`, `hok`, `khum`.
4. Dùng tiếng Việt chuẩn, trang trọng.
5. Nếu có `ENCODING_RULES.md`, `CODEX_RULES_PROMPT.md`, `AGENTS.md`, `PROJECT_CONTEXT.md` thì phải đọc trước khi sửa.
6. Khi sửa file, mọi chữ tiếng Việt mới hoặc chữ tiếng Việt nằm trong phạm vi sửa phải dùng UTF-8 trực tiếp, không dùng HTML entity như `&#...;`. Đặc biệt không đặt HTML entity trong `{{ ... }}` của Blade.

## Mục tiêu

Source code phải đọc được bằng tiếng Việt nguyên bản, không chỉ hiển thị đúng ngoài giao diện.
Người mở file code phải thấy đúng chữ:

```text
Ngày
Rút tiền
Đã duyệt
Thông báo
Không có dữ liệu
```

Không được thấy:

```text
Ng&#224;y
R&#250;t ti&#7873;n
&#272;&#227; duy&#7879;t
ThÃ´ng bÃ¡o
KhÃ´ng cÃ³ dá»¯ liá»‡u
```

## Các dạng lỗi bị cấm

### 1. HTML entity cho chữ tiếng Việt

Sai:

```blade
<button>R&#250;t ti&#7873;n</button>
<p>Ng&#224;y t&#7841;o</p>
<span>&#272;&#227; duy&#7879;t</span>
```

Đúng:

```blade
<button>Rút tiền</button>
<p>Ngày tạo</p>
<span>Đã duyệt</span>
```

### 2. Entity trong Blade echo

Sai:

```blade
{{ 'Ng&#224;y' }}
{{ __('R&#250;t ti&#7873;n') }}
```

Đúng:

```blade
{{ 'Ngày' }}
{{ __('Rút tiền') }}
```

### 3. Mojibake

Sai:

```text
ThÃ´ng bÃ¡o
ÄÃ£ lá»ưu
Táº¡o má»›i
```

Đúng:

```text
Thông báo
Đã lưu
Tạo mới
```

### 4. Teencode

Sai:

```text
ko có dữ liệu
đc duyệt
mn kiểm tra lại
```

Đúng:

```text
Không có dữ liệu
Được duyệt
Mọi người kiểm tra lại
```

## Quy tắc khi sửa file

- Nếu trong phạm vi sửa có chữ tiếng Việt đang bị lỗi, phải sửa về tiếng Việt chuẩn.
- Nếu thêm text mới, phải viết tiếng Việt trực tiếp.
- Không dùng công cụ chuyển tiếng Việt thành HTML entity.
- Không escape chữ tiếng Việt trong file dịch, Blade, JS, JSON nếu không có lý do kỹ thuật bắt buộc.
- Không đổi toàn bộ file lớn nếu chỉ cần sửa vài dòng; nhưng dòng đã sửa phải đúng UTF-8.

## Laravel/Blade

Đúng:

```blade
<h1>Quản lý hồ sơ</h1>
<button type="submit">Lưu thay đổi</button>
<input placeholder="Nhập tên cư dân">
```

Đúng với translation helper:

```blade
{{ __('Quản lý hồ sơ') }}
```

Sai:

```blade
{{ __('Qu&#7843;n l&#253; h&#7891; s&#417;') }}
```

## PHP language file

Đúng:

```php
return [
    'created_successfully' => 'Tạo mới thành công.',
    'updated_successfully' => 'Cập nhật thành công.',
    'deleted_successfully' => 'Đã xoá dữ liệu.',
];
```

Sai:

```php
return [
    'created_successfully' => 'T&#7841;o m&#7899;i th&#224;nh c&#244;ng.',
];
```

## JavaScript

Đúng:

```js
const confirmMessage = 'Bạn có chắc chắn muốn xoá mục này không?';
```

Sai:

```js
const confirmMessage = 'B&#7841;n c&#243; ch&#7855;c ch&#7855;n mu&#7889;n xo&#225; m&#7909;c n&#224;y kh&#244;ng?';
```

## JSON

Đúng:

```json
{
  "emptyText": "Không có dữ liệu"
}
```

Không dùng dạng entity cho tiếng Việt trong JSON.

## Kiểm tra sau khi sửa

Chạy:

```bash
php scripts/check-vietnamese-encoding.php
```

Nếu script báo lỗi, phải sửa trước khi báo hoàn thành.
