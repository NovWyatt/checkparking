# Báo cáo milestone UI, service integration và concurrency

## Mục tiêu

Milestone này tích hợp service layer vào ứng dụng Tkinter, tách phần presentation khỏi `app.py`, sửa giới hạn luồng thực tế và giữ nguyên luồng nhập ảnh/thư mục, OCR, review và xuất Excel. Không build installer, không gọi API/Telegram thật trong test, không tải model/ảnh từ Internet, không dùng Git.

## Nguyên nhân cấu hình nhiều luồng trước đây vẫn chạy một

Trong `check_vehicle_ocr/app.py` trước milestone, `_start_processing()` dùng một biến `worker_count_var` cho mọi việc rồi ép `workers = 1` với `PaddleOCR Local` và `Gemini Vision`. `_worker_process()` chỉ có một `ThreadPoolExecutor`, nên không thể phân biệt decode ảnh, inference local và request API. Đây là nguyên nhân xác nhận được từ source, không phải lỗi của control giao diện.

## Kiến trúc sau thay đổi

`WorkerSettings` trong `check_vehicle_ocr/services/worker_manager.py` tách:

- `image_workers`: decode/EXIF và kiểm tra file ảnh.
- `local_ocr_workers`: inference local. Riêng `PaddleOCR Local` luôn bị guard về **1** vì app tái sử dụng một shared predictor và chưa benchmark engine pool độc lập.
- `api_workers`: request của Gemini, Plate Recognizer, GPT Vision hoặc OpenAI Compatible.
- `queue_capacity`: giới hạn payload đang chờ giữa hai stage.

`WorkerManager.run_pipeline()` chạy stage chuẩn bị và stage inference bằng pool riêng, giữ index/output theo ảnh đầu vào, không gọi `future.result()` tuần tự sau mỗi lần submit, và cô lập lỗi từng ảnh thành `ImageResult(status="ERROR")`. Khi dừng, các task chưa bắt đầu bị hủy; kết quả hoàn thành vẫn được giữ.

`BatchProgress` trong `check_vehicle_ocr/services/progress_service.py` giữ batch id, trạng thái, queue/active/completed, success/review/failed/cancelled, file hiện tại, elapsed, rate, ETA, worker cấu hình/đang chạy. Worker gửi snapshot immutable qua `event_queue`; `_drain_events()` trên UI thread mới cập nhật Tkinter.

### Concurrency được kiểm chứng

`tests/worker_manager_test.py` dùng barrier/event fake, không tải model:

| Kiểm tra | Kết quả |
|---|---:|
| Image workers = 1 | Concurrent tối đa 1 |
| Image workers = 2 | Concurrent tối đa 2 |
| Image workers = 4 | Concurrent tối đa 4 |
| PaddleOCR Local, yêu cầu local OCR = 4 | Concurrent inference tối đa 1 |
| OpenAI Compatible, API workers = 3 | Concurrent request tối đa 3 |

Đây là kiểm chứng giới hạn scheduler, không phải benchmark hiệu năng API/Paddle production.

## UI đã tích hợp

`check_vehicle_ocr/ui/` hiện chứa shell, token theme, UI state, shared form controls và page riêng:

- Quét ảnh: chọn ảnh/thư mục, recursive, FAST/BALANCED/THOROUGH, cấu hình pool tách rời, progress và stop.
- Phiên hiện tại: metric, tìm kiếm, sort bảng, multi-select native Treeview và điều hướng review.
- Cần kiểm tra: ảnh gốc, preview crop biển số khi crop có sẵn, raw OCR, kết quả chọn, confidence/source, gợi ý mơ hồ, sửa tay, duyệt và mở ảnh.
- Xuất Excel: đường dẫn, compact/full, export all/reviewed và trạng thái snapshot nền.
- AI Providers: OpenAI-compatible Base URL, API key masked, model editable/cache, refresh/test connection nền, timeout và API concurrency.
- Telegram: enable, token/chat ID, lựa chọn lifecycle, progress step, minimum interval, mask setting và gửi tin thử.
- Cập nhật: manifest URL, check/download verified state; không tự cài.
- Cài đặt: dark mode, secret persistence và xóa key có xác nhận.

Sidebar/header dùng semantic token trong `check_vehicle_ocr/ui/theme.py`. `app.py` vẫn là composition root/controller; page không thực hiện OCR hay gọi Tkinter từ worker. Shortcut có Ctrl+O, Ctrl+Shift+O, Ctrl+Enter, Ctrl+F, Ctrl+E, Ctrl+,, F5 và Esc.

## AI Provider

`GptVisionEngine` nhận `base_url` tùy chọn và truyền nó vào OpenAI client thật. Khi chọn engine **OpenAI Compatible**, batch lấy Base URL/model/API key/timeout từ provider custom và `WorkerManager` dùng `api_workers`. Base URL chỉ hợp lệ khi provider được bật và có Base URL, nếu không engine trả lỗi inline thay vì ngầm gọi endpoint mặc định.

`OpenAICompatibleProvider` dùng Base URL đã chuẩn hóa cho `GET /models`, merge model remote với manual model, giữ model cũ nếu không còn trong danh sách, và redacts API key khỏi thông báo lỗi. Test mock xác nhận custom Base URL, model manual, response map thành `ImageResult`, lỗi HTTP 401 không chứa secret và giới hạn API worker.

Lưu ý: engine custom hiện dùng OpenAI **Responses API**, vì vậy một server “OpenAI-compatible” chỉ hỗ trợ Chat Completions có thể liệt kê model nhưng chưa chắc chạy được inference. Đây là giới hạn tương thích cần kiểm tra bằng test connection/integration thực tế khi có server hợp lệ.

## Telegram

`AsyncTelegramNotifier` có queue bounded và thread riêng, timeout 8 giây, retry giới hạn một lần. Lifecycle thực tế trong app:

- bắt đầu batch;
- mốc progress theo `progress_percent_step` (mặc định 10% và không gửi trùng);
- hoàn tất;
- dừng/cancel hoặc lỗi batch.

Lỗi Telegram chỉ cập nhật `telegram_status_var` qua UI queue, không làm OCR batch thất bại. Token không được ghi vào log/status đầy đủ và được lưu qua cơ chế protected setting hiện có khi Windows DPAPI khả dụng. Test dùng fake notifier, không gửi Telegram thật.

## Updater

Trang Cập nhật cho phép nhập manifest URL. `fetch_manifest()` và `download_verified()` chạy worker nền, parser/checksum đã có test local/mock. UI phân biệt rõ:

1. Kiểm tra manifest.
2. Tải package và xác minh SHA-256.
3. Cài đặt: **chưa triển khai**.

Sau bước 2 UI chỉ ghi “Đã tải và xác minh … sẵn sàng cài đặt thủ công”; không chạy executable, không thay file app và không tự rollback. Không có URL release giả hoặc server release hardcode.

## Benchmark ảnh synthetic

Lệnh `python -B tests\performance_benchmark.py` chạy 3 process độc lập, mỗi process dùng một ảnh biển số synthetic 900×520 và 3 ảnh cho batch. Số liệu median thực tế:

| Hạng mục | Lần 1 | Lần 2 | Lần 3 | Median |
|---|---:|---:|---:|---:|
| Paddle cold init | 1.462 s | 1.544 s | 1.488 s | 1.488 s |
| Ảnh đầu tiên | 0.841 s | 0.889 s | 0.921 s | 0.889 s |
| Ảnh warm | 0.787 s | 0.762 s | 0.779 s | 0.779 s |
| Batch 3 ảnh | 2.489 s | 2.365 s | 2.348 s | 2.365 s |
| Excel compact | 0.104 s | 0.099 s | 0.105 s | 0.104 s |
| Excel full | 0.205 s | 0.196 s | 0.218 s | 0.205 s |

Thông tin bổ sung median: import app 2.693 s; khởi tạo UI 0.449 s; Paddle engine 1 lần/process; scene OCR 5, ROI fallback 0, tổng 5 OCR calls; compact 11,510 bytes, full 39,937 bytes. Đây là ảnh synthetic có một biển số, không đại diện tốc độ/accuracy production hoặc ảnh camera thật.

## Screenshot review

`tools/capture_ui_review.py` dùng Windows `PrintWindow` để chụp đúng HWND Tkinter (không dùng desktop crop dễ bắt nhầm cửa sổ), cô lập `APPDATA`, không gọi OCR/network. Screenshot đã tạo:

- `docs/ui-review/scan-empty.png`
- `docs/ui-review/scan-running.png`
- `docs/ui-review/scan-complete.png`
- `docs/ui-review/result-review.png`
- `docs/ui-review/providers.png`
- `docs/ui-review/telegram.png`
- `docs/ui-review/updates.png`
- `docs/ui-review/settings.png`

Đã kiểm tra trực quan `scan-running.png`, `result-review.png` và `providers.png`. `tests/ui_smoke_test.py` kiểm tra startup, toàn bộ page router, enable/disable nút quét, progress state, theme toggle và Tk scaling 125%/150% không ném exception. Đây là smoke/layout check, chưa phải usability test với người vận hành.

## Test và kiểm tra đã chạy

Tất cả pass (10 script test + parse + screenshot harness):

```text
python -B -m compileall -q check_vehicle_ocr tests tools
python -B tests\worker_manager_test.py
python -B tests\progress_state_test.py
python -B tests\provider_integration_test.py
python -B tests\telegram_integration_test.py
python -B tests\updater_ui_state_test.py
python -B tests\ui_smoke_test.py
python -B tests\services_test.py
python -B tests\performance_stability_test.py
python -B tests\smoke_test.py
python -B tests\performance_benchmark.py
python -B tools\capture_ui_review.py
```

`smoke_test.py` và `performance_stability_test.py` bao gồm Excel compact/full, reopen workbook bằng openpyxl, atomic save/locked Excel cleanup, formula injection, normalization, early exit và engine reuse. Warning còn lại: PaddlePaddle cảnh báo không có `ccache`; không làm test fail.

## File tạo/sửa trong milestone

- Sửa: `check_vehicle_ocr/app.py`, `config.py`, `gpt_vision.py`, `processor.py`, `providers.py`, `telegram_notify.py`, `services/progress_service.py`, `services/worker_manager.py`, `tests/performance_benchmark.py`, `tests/services_test.py`, `DESIGN-linear.app.md`.
- Tạo UI: `check_vehicle_ocr/ui/` (shell, theme, state, components và eight page modules).
- Tạo test: `worker_manager_test.py`, `progress_state_test.py`, `provider_integration_test.py`, `telegram_integration_test.py`, `updater_ui_state_test.py`, `ui_smoke_test.py`.
- Tạo tool/output: `tools/capture_ui_review.py`, `docs/ui-review/*.png`, báo cáo này.

Không cài, gỡ hoặc nâng dependency. Không sửa PaddleOCR source/model, không build, không dùng camera, không gọi API ngoài, không commit/push.

## Những phần chưa hoàn thành hoặc còn giới hạn

- Không có pause thật nên UI không hiển thị Pause; Stop là dừng sau task hiện tại.
- “Kéo ảnh vào đây” hiện là empty/drop-zone visual; chọn ảnh/thư mục bằng nút đã hoạt động. Native drag-and-drop chưa thêm vì Tkinter chuẩn không có DnD ổn định mà không thêm tkdnd.
- Chưa có engine pool PaddleOCR; inference local Paddle vẫn chủ động tuần tự để tránh rủi ro predictor không thread-safe. Preprocess ảnh đã song song.
- Chưa kiểm tra Telegram/provider/update endpoint thật; mọi test là fake/local mock.
- Updater không cài executable, không rollback binary; chỉ check/download/verify.
- Chưa thêm database, camera, tracking, xe vào/ra, quyền người dùng, backup hay benchmark ảnh camera production.
- Không có “Taste Skill” trong catalog skill khả dụng của môi trường này. UI được áp dụng trực tiếp theo `DESIGN-linear.app.md`; không tuyên bố đã dùng Taste Skill.
- Hai file recovery có sẵn từ trước (`recovered_app_decompyle3.py`, `recovered_app_uncompyle6.py`) vẫn chứa comment đường dẫn cũ `E:\Check_vehicle`; không sửa/xóa vì ngoài phạm vi runtime và chưa xác định có cần giữ làm artifact tham khảo hay không.

## Kết luận

Milestone integration/UI đã hoàn thành ở mức source + deterministic test/smoke. App không được tuyên bố production-ready. Bước phù hợp tiếp theo là kiểm tra với một tập ảnh camera nội bộ đã gán nhãn, sau đó benchmark engine pool PaddleOCR một cách đo RAM/thời gian trước khi cân nhắc tăng local inference concurrency.
