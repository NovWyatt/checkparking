# Check Vehicle OCR — Linear-inspired desktop design

## Mục tiêu và phạm vi

Thiết kế giữ nguyên Tkinter, luồng nhập ảnh/thư mục, review và Excel. Giao diện ưu tiên trạng thái batch, một hành động chính, lỗi inline/toast và thao tác bàn phím. Không sử dụng asset, logo hoặc màu nhận diện của Linear.

## Token

| Token | Light | Dark | Dùng cho |
|---|---|---|---|
| background | #F7F8FA | #15161A | nền app |
| surface | #FFFFFF | #1D1E24 | panel |
| surface-selected | #E9ECF5 | #272A35 | navigation/row chọn |
| border | #DEE1E8 | #30323D | phân vùng |
| text-primary | #1B1D24 | #F1F3F8 | nội dung chính |
| text-secondary | #656B78 | #A9AFBC | metadata |
| accent | #5865F2 | #8892FF | hành động chính/focus |
| success/warning/danger/info | #208A5B/#B7791F/#C43D4B/#3273DC | semantic | trạng thái có text đi kèm |

Spacing: 4, 8, 12, 16, 24, 32, 48 px. Radius control 8 px, panel 12 px, modal 14 px. Font: Segoe UI Variable/Segoe UI; title 22 px, section 15 px, body 13 px, table 12 px.

## Kiến trúc UI và state

- `AppState`: session ảnh/kết quả, filter, batch progress, notification và page hiện tại.
- Worker chỉ đưa event immutable vào queue. Tkinter widget/`StringVar` chỉ cập nhật từ `_drain_events` trên UI thread.
- Sidebar cố định gồm Quét ảnh, Phiên hiện tại, Cần kiểm tra, Xuất Excel, AI Providers, Telegram, Cập nhật và Cài đặt.
- Header hiển thị tên page, engine/model, online/offline/model status và một action chính theo page.
- Content dùng input/progress/result/detail panels; setting nâng cao collapsible.

## Luồng chính

1. Empty state giải thích cách chọn ảnh/folder, Ctrl+O/Ctrl+Shift+O.
2. Scan page có input, mode FAST/BALANCED/THOROUGH, worker split và Start (Ctrl+Enter).
3. Running state giữ progress, completed/total, current image, elapsed, ETA, images/minute, active workers, review/error count. UI update tối đa 200 ms.
4. Result table hỗ trợ search/filter/sort/keyboard; detail panel phải hiện raw, cleaned, normalized, suggestions, flags, confidence và correction.
5. Export dùng snapshot nền; Excel page hiển thị compact/full option và trạng thái export.

## Accessibility và keyboard

- Focus ring accent, hit target tối thiểu 32 px, text trạng thái kèm màu.
- Ctrl+O chọn ảnh; Ctrl+Shift+O folder; Ctrl+Enter start; Space pause/resume; Esc stop/đóng modal; Ctrl+F search; Ctrl+E export; Ctrl+, settings; F5 refresh provider/status.
- UI scale theo DPI Windows, không khóa font nhỏ, tránh popup trừ lỗi blocking/xác nhận destructive.

## Service page contracts

- Provider: API key masked, base URL, model manual/dynamic, refresh/test có status/timestamp/cache.
- Telegram: token/chat ID, test, start/progress/complete/error, interval và mask plate. Mọi lỗi Telegram chỉ thành notification/log.
- Update: manifest URL là cấu hình trống mặc định; parse/checksum/download temp/rollback plan. Không tự cài và không hardcode release URL.

## Acceptance

Startup, light/dark, 1366x768 logical layout, keyboard, empty/loading/error/success states và source UTF-8 phải được test. Screenshot review chỉ thực hiện khi có khả năng chạy desktop automation; không có asset ngoài được thêm.

## Trạng thái triển khai milestone UI

- `check_vehicle_ocr/ui/` là presentation layer: shell/sidebar/header, theme semantic token và các page quét, phiên, review, export, provider, Telegram, cập nhật, cài đặt.
- `check_vehicle_ocr/app.py` giữ vai trò composition root/controller; worker và service không được phép gọi widget Tkinter trực tiếp.
- PaddleOCR dùng một inference worker cho shared predictor; decode/EXIF ảnh có thể chạy song song ở image pool. API provider dùng pool riêng.
- Tiến trình batch được snapshot qua event queue và render tối đa theo chu kỳ UI, không render toàn bảng ở worker thread.
- Screenshot thật (nếu Windows `PrintWindow` khả dụng) được tạo bằng `tools/capture_ui_review.py` tại `docs/ui-review/`; script cô lập `APPDATA` và không gọi OCR/network.
