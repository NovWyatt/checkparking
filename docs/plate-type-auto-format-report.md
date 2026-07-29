# Báo cáo định dạng biển số theo loại batch

## Mục tiêu

Thêm lựa chọn loại biển số cho từng batch ảnh và chỉ tự thêm dấu gạch với ba mẫu đã được phê duyệt. Mọi biển không khớp được giữ nguyên để người vận hành kiểm tra; không có thay thế ký tự mơ hồ hay suy đoán loại xe.

## Chọn loại biển

Trang **Quét ảnh**, ngay trong Bước 1, có trường **Loại biển số trong thư mục** với ba lựa chọn:

- **Xe máy**: định dạng `59X1-12345` hoặc `59MN-12345`.
- **Ô tô**: định dạng `59X-12345`.
- **Không tự định dạng**: mặc định an toàn; giữ nguyên kết quả OCR.

Mô tả ngắn và tooltip đều nhắc rằng chỉ biển đúng mẫu mới được thêm dấu gạch. Lựa chọn gần nhất được lưu ở `last_plate_type`, nhưng lựa chọn hiện tại luôn hiển thị trước khi quét.

Khi bắt đầu quét, ứng dụng chốt `batch_id`, loại biển, thời điểm bắt đầu và tổng số ảnh vào từng `ImageResult`. Thay đổi combobox sau đó không làm đổi kết quả cũ. Nút **Áp dụng lại định dạng cho kết quả hiện tại** chỉ xuất hiện khi lựa chọn mới khác batch đã quét; thao tác này chỉ dùng text hiện có, không gọi PaddleOCR.

## Rule được áp dụng

Module thuần `check_vehicle_ocr/plate_formatting.py` tập trung toàn bộ logic:

| Loại | Chuỗi làm sạch phải khớp chính xác | Kết quả |
| --- | --- | --- |
| Xe máy, một chữ + một số | `^(\d{2})([A-Z])(\d)(\d{4,5})$` | `59X1-12345` |
| Xe máy, hai chữ | `^(\d{2})([A-Z]{2})(\d{4,5})$` | `59MN-12345` |
| Ô tô | `^(\d{2})([A-Z])(\d{4,5})$` | `59X-12345` |

`clean_plate_for_formatting()` chuyển sang chữ hoa, bỏ khoảng trắng, dấu gạch, chấm, gạch dưới và xuống dòng, rồi chỉ giữ `A-Z`/`0-9`. Hàm không đổi `O/I/B/S/G` sang số. Gợi ý OCR hiện hữu vẫn chỉ là thông tin hỗ trợ review.

## Biển đặc biệt và OCR gốc

Mỗi `PlateCandidate` hiện giữ riêng `raw_text`, `cleaned_text`, `formatted_text`, `export_text`, `selected_plate_type`, `detected_format`, `format_status`, `format_reason`, `needs_review` và `manual_correction`.

Ví dụ `49MD112345` khi batch là xe máy được giữ nguyên làm `export_text`, có `UNMATCHED`, `SPECIAL_OR_UNKNOWN`, lý do dễ hiểu và `needs_review=True`. Chuỗi `59-110-MN-123` được xử lý tương tự. Không có regex rộng hoặc di chuyển dấu gạch cho các trường hợp này.

Các provider trực tuyến cũng ghi `raw_text` là chính chuỗi biển mà provider trả về, không còn lưu JSON kỹ thuật vào trường OCR gốc. PaddleOCR giữ candidate thắng cuộc làm OCR gốc thay vì cả nhóm text cảnh.

## Sửa tay và màn hình kết quả

Sửa tay được lưu nguyên văn trong `manual_correction`. Nếu khớp mẫu batch, Excel dùng bản có dấu gạch và trạng thái là `MANUAL`/“Đã sửa tay”. Nếu không khớp, nội dung sửa tay được giữ nguyên và vẫn vào nhóm biển đặc biệt để người dùng quyết định review.

Bảng Kết quả hiển thị: Tên ảnh, Loại biển, OCR gốc, Biển số xuất, Trạng thái và Cần kiểm tra. Bộ lọc gồm Tất cả, Đã định dạng, Biển đặc biệt, Cần kiểm tra và Có lỗi. Detail panel hiển thị OCR nguyên bản, chuỗi sạch, biển đã định dạng, giá trị xuất Excel, loại biển, lý do, gợi ý mơ hồ và ô sửa tay. Trạng thái “Biển đặc biệt” dùng tag cảnh báo đọc được ở cả giao diện sáng và tối.

## Excel

`Bien_so_doc_duoc` có cột chính **Biển số xuất Excel** cùng các cột mới: Loại biển đã chọn, OCR nguyên bản, Chuỗi đã làm sạch, Biển số đã định dạng, Trạng thái định dạng, Mẫu nhận diện, Lý do cần kiểm tra và Đã sửa thủ công. Các sheet review cũng mang thông tin định dạng tương ứng.

Sheet mới `Bien_so_dac_biet` chỉ nhận candidate `UNMATCHED` hoặc `SPECIAL_OR_UNKNOWN`, kể cả khi export chỉ các biển đã duyệt. Atomic save, compact/full export, background export và bảo vệ Formula Injection vẫn giữ nguyên.

## File tạo hoặc sửa

- Tạo: `check_vehicle_ocr/plate_formatting.py`, `check_vehicle_ocr/ui/components/tooltip.py`, `tests/plate_formatting_test.py`.
- Sửa: `check_vehicle_ocr/models.py`, `check_vehicle_ocr/config.py`, `check_vehicle_ocr/app.py`, `check_vehicle_ocr/excel_export.py`, `check_vehicle_ocr/paddle_ocr_engine.py`, `check_vehicle_ocr/gemini_vision.py`, `check_vehicle_ocr/gpt_vision.py`, `check_vehicle_ocr/plate_recognizer.py`.
- Sửa UI/harness: `check_vehicle_ocr/ui/pages/scan_page.py`, `check_vehicle_ocr/ui/pages/results_page.py`, `tools/capture_ui_review.py`, `tests/ui_simplification_test.py`.

## Kiểm chứng

Đã chạy với `.venv\Scripts\python.exe -s -B` và `PYTHONNOUSERSITE=1`:

- `compileall` cho `check_vehicle_ocr`, `tests`, `tools`.
- Toàn bộ 19 test script hiện có (`*_test.py`) và `tests/plate_formatting_test.py`: pass.
- `tests/smoke_test.py`: pass, bao gồm Formula Injection và Excel compact/full.
- UI smoke, UI simplification, light/dark screenshot harness và control-state harness: pass.
- `tests/performance_benchmark.py --single-run`: pass. Lần đo synthetic cuối: UI init 0,394 s; cold Paddle 1,456 s; ảnh đầu 0,837 s; ảnh warm 0,784 s; batch 3 ảnh 2,390 s; Excel compact/full 0,097/0,216 s.
- Microbenchmark formatter: 100.000 lần gọi trong 0,370 s, khoảng 3,70 µs/lần; không phải bottleneck thực tế so với OCR/Excel.
- Build PyInstaller thành công: `release\CheckVehicleOCR\CheckVehicleOCR.exe` (1.7.2). Harness executable chạy bằng APPDATA/TEMP cô lập và tạo screenshot Light/Dark. Một lần build ban đầu gặp WinError 32 do tiến trình PyInstaller bị dừng trước đó còn giữ file build; tiến trình đó đã được xác định, dừng riêng, rồi các build sau đều thành công.

Screenshot cuối:

- `docs/ui-review/light-scan.png`, `docs/ui-review/dark-scan.png`.
- `docs/ui-review/light-results.png`, `docs/ui-review/dark-results.png`.
- `docs/ui-review/control-states-light.png`, `docs/ui-review/control-states-dark.png`.
- `docs/ui-review/scan-combobox-light.png`, `docs/ui-review/scan-combobox-dark.png`.
- `docs/ui-review/release/packaged-light-scan.png`, `docs/ui-review/release/packaged-dark-scan.png` và trạng thái Settings đóng gói tương ứng.

## Hạn chế còn lại

Milestone này chỉ hỗ trợ đúng ba mẫu đã nêu. Biển quân sự, ngoại giao, biển đặc thù hoặc mẫu mới phải được bổ sung bằng rule và test riêng; không được nới regex hiện tại. Không có dữ liệu ảnh thật trong repository để công bố độ chính xác OCR. Không có API, Telegram hoặc Internet nào được gọi trong kiểm thử milestone này.
