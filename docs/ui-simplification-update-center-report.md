# Báo cáo đơn giản hóa giao diện và Update Center

## Mục tiêu

Milestone này chuyển giao diện từ các trang kỹ thuật rời rạc sang luồng dành cho người vận hành: chọn ảnh, quét, xem/chỉnh kết quả và cấu hình khi cần. Không thay PaddleOCR, model, database, camera hoặc cơ chế xuất Excel hiện có.

## Sidebar và luồng đã gộp

Sidebar hiện chỉ có ba mục:

| Mục mới | Nội dung đã gộp | Cách giữ tương thích |
|---|---|---|
| Quét ảnh | Chọn dữ liệu, cách nhận diện, hiệu năng, tiến trình | Vẫn dùng pipeline/worker manager cũ ở phía dưới. |
| Kết quả | Phiên hiện tại, Cần kiểm tra, review chi tiết, xuất Excel | Route `session`, `review`, `export` được map nội bộ về `results`. |
| Cài đặt | Chung, AI trực tuyến, Telegram, Cập nhật, Nâng cao | Route `providers`, `telegram`, `updates` được map nội bộ về `settings`. |

Nhờ routing alias, shortcut và controller cũ không bị gãy, nhưng người vận hành không còn phải quyết định giữa nhiều trang tương tự nhau.

## Thuật ngữ và cấu hình quét

- `Engine` trên màn hình chính được thay bằng **Cách nhận diện**: Cục bộ — Khuyên dùng; Cục bộ + AI kiểm tra ảnh khó; AI trực tuyến.
- `PaddleOCR Local`/`Local OCR` không còn là lựa chọn chính gây nhầm lẫn. Giao diện chính dùng **OCR cục bộ — PaddleOCR**; Tesseract nằm ở Cài đặt → Nâng cao với tên **OCR dự phòng — Tesseract**.
- `FAST`/`BALANCED`/`THOROUGH` được hiển thị thành Nhanh, Cân bằng — Khuyên dùng và Kỹ, có mô tả ngắn.
- Các ô worker/queue được thay bằng preset Hiệu năng: Tự động — Khuyên dùng, Tiết kiệm RAM, Ưu tiên tốc độ. Giá trị kỹ thuật chỉ hiện trong phần nâng cao.
- `PaddleOCR Local` và mode kết hợp vẫn luôn dùng **một inference worker**. Image preprocessing và API concurrency vẫn được WorkerManager quản lý độc lập.

Nếu AI chưa được cấu hình mà người dùng chọn hai mode có AI, trang Quét hiển thị cảnh báo inline và nút mở Cài đặt → AI trực tuyến. Batch không khởi chạy trong trạng thái thiếu cấu hình.

## Kết quả, review và Excel

Trang Kết quả có filter Tất cả/Cần kiểm tra/Có lỗi, tìm kiếm, quét batch mới và một hành động Xuất Excel. Detail panel giữ ảnh, crop, OCR thô, kết quả chọn, gợi ý, confidence, cảnh báo và chỉnh thủ công. Tùy chọn chỉ xuất biển số đã xác nhận vẫn còn nhưng không tạo thêm trang Export.

Excel tiếp tục dùng snapshot nền, atomic save, Formula Injection guard và compact/full option hiện có. Không thay đổi định dạng báo cáo.

## Tesseract dự phòng

- Không hiển thị trong luồng quét mặc định.
- Chỉ được gọi cho fallback Gemini khi checkbox nâng cao được bật rõ ràng; test xác nhận mặc định không khởi tạo Tesseract.
- Update Center kiểm tra nền trạng thái cài đặt, phiên bản, đường dẫn và `tessdata` nếu có.
- Thiếu Tesseract chỉ là trạng thái thông tin, không chặn PaddleOCR.
- Không có auto-download hoặc auto-install Tesseract.

## Contrast và theme

Token semantic đã được chỉnh và có test tự động tối thiểu 4.5:1 cho text/status/disabled trên nền dùng thực tế.

| Cặp token | Trước | Sau |
|---|---:|---:|
| Light `text-muted` / `surface` | 3,16:1 | 6,16:1 |
| Light `text-secondary` / `surface` | 5,35:1 | 7,51:1 |
| Light `on-accent` / `accent` | 4,61:1 | 5,67:1 |
| Dark `text-muted` / `surface` | 3,92:1 | 8,88:1 |

Màu trạng thái vẫn luôn đi cùng text; không dùng màu đơn lẻ làm tín hiệu.

## Update Center

### 1. Ứng dụng Check Vehicle OCR

Giữ manifest URL trống mặc định, check/download chạy nền, download vào file tạm và kiểm SHA-256 trước khi giữ package. App không tự chạy installer hoặc thay executable.

### 2. PaddleOCR

Hiển thị version PaddleOCR/PaddlePaddle đang cài, trạng thái tương thích thận trọng, nguồn release và release notes link sau khi check. Nút check dùng PyPI chính thức khi người dùng chủ động bấm; test mock không gọi Internet.

Không có nút cập nhật trực tiếp môi trường đang chạy. Update Center hiện tạo **kế hoạch staging** gồm venv riêng, cài version/tag cụ thể, smoke test, synthetic benchmark, dataset benchmark nếu có, và rollback. Chưa thực thi tự động chuỗi `venv/pip/install/activate` vì chưa có version PaddlePaddle tương thích đã xác minh và cơ chế chuyển environment/rollback executable đáng tin cậy.

### 3. Model PaddleOCR

Card tách detection và recognition model, trạng thái active, source cache cục bộ, version/date nếu local cache cung cấp, và nói rõ khi chưa có manifest checksum. `stage_model_archive()` chỉ nhận model archive có SHA-256, giải nén vào thư mục version mới và không ghi đè model cũ. Chưa có nguồn manifest model được cấu hình hoặc UI activate/rollback; do đó không có model nào được tải/thay trong milestone này.

### 4. Tesseract dự phòng

Card chỉ đọc trạng thái/version/path/tessdata và giải thích đây là lựa chọn không bắt buộc. Không có nút cập nhật binary.

## Screenshot review

Screenshot thật tại `docs/ui-review/`, chụp ở 1366×768:

- `light-scan.png`, `dark-scan.png`
- `light-results.png`, `dark-results.png`
- `settings-ai.png`, `settings-updates.png`
- `advanced-collapsed.png`, `advanced-expanded.png`

Đã kiểm tra trực quan: text chính, secondary, warning/status và control trong Light/Dark đều rõ; primary action hiển thị trong viewport ở trạng thái scan tiêu chuẩn và khi mở phần nâng cao.

## Hiệu năng kiểm chứng

`python -B tests\performance_benchmark.py` (ảnh synthetic/cache model local) sau đơn giản hóa UI cho median:

| Hạng mục | Median |
|---|---:|
| Import app | 2,256s |
| UI init | 0,333s |
| Paddle cold init | 1,434s |
| First image | 0,861s |
| Warm image | 0,773s |
| Batch 3 ảnh | 2,334s |
| Excel compact | 0,093s |
| Excel full | 0,221s |

UI init giảm từ 0,418s ở lần đo trước milestone này xuống 0,333s trong lần đo hiện tại. Số liệu synthetic không phải accuracy hoặc throughput production.

Engine-pool benchmark batch 10 tiếp tục cho thấy two-engine nhanh hơn khoảng 5,6% (79,44 so với 75,23 ảnh/phút) nhưng tăng RAM khoảng 15,1%; two-process chậm hơn và dùng khoảng 741MB. RAM khả dụng trước test chỉ 2,840MB nên không chạy batch 30. Giữ một PaddleOCR inference worker là quyết định an toàn.

## File tạo/sửa

- Sửa UI: `check_vehicle_ocr/ui/shell.py`, `ui/theme.py`, `ui/pages/scan_page.py`, `ui/pages/settings_page.py`, `ui/pages/__init__.py`.
- Tạo UI: `check_vehicle_ocr/ui/pages/results_page.py`.
- Sửa controller/compatibility: `check_vehicle_ocr/app.py`, `check_vehicle_ocr/config.py`, `check_vehicle_ocr/services/worker_manager.py`.
- Tạo Update Center service: `check_vehicle_ocr/update_center.py`.
- Cập nhật design/screenshot harness: `DESIGN-linear.app.md`, `tools/capture_ui_review.py`.
- Tạo test: `tests/ui_simplification_test.py`, `tests/theme_contrast_test.py`, `tests/update_center_test.py`, `tests/tesseract_optional_test.py`; cập nhật `tests/ui_smoke_test.py`, `tests/worker_manager_test.py`.

## Kiểm tra đã chạy

Đã pass `compileall` và 17 script test: smoke, performance stability, services, worker manager, progress, provider integration/API mode, Telegram, updater UI/local E2E, dataset, UI smoke, UI simplification, contrast, Update Center và Tesseract optional.

Đã chạy thêm `performance_benchmark.py`, `performance_regression_profile.py`, `paddle_engine_pool_benchmark.py` và screenshot harness. Automated test không gọi API, Telegram, GitHub hoặc PyPI thật; các test update dùng mock/local fixture.

Warning môi trường còn lại: PaddlePaddle báo thiếu `ccache`, không làm test fail. Không cài/gỡ/nâng dependency, không gọi updater thật, không tải model/package, không dùng camera, không dùng Git, không commit hoặc push.

## Phần chưa hoàn thành chủ động

- Chưa thực thi staging venv/pip/smoke/benchmark thật cho một release PaddleOCR/PaddlePaddle xác định.
- Chưa có manifest/release source model đáng tin cậy nên chưa expose download/activate/rollback model trong UI.
- Chưa kiểm tra API/Telegram bằng secret hoặc account thật.
- Chưa benchmark ảnh camera/ảnh thật vì không có dataset local có manifest.
