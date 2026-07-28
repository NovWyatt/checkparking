# Báo cáo kiểm chứng hiệu năng và ổn định

## 1. Những phần đã kiểm chứng

- PaddleOCR được tạo trong worker và một instance được tái sử dụng trong batch.
- BALANCED dừng sau scene hợp lệ; scene rỗng/thấp tin cậy mới chạy ROI fallback.
- Excel export dùng snapshot, worker queue và khóa nút export khi đang chạy.
- Compact export không tạo thumbnail; full export vẫn mở lại được.
- Excel save dùng file tạm cùng thư mục rồi `os.replace`; file cũ giữ nguyên khi mock locked/save error.
- Formula Injection, normalization ambiguity và ONNX offline fallback có test.

## 2. Benchmark

Xem số liệu ba lượt thực tế tại `docs/PERFORMANCE_CURRENT.md`. Median: cold init 1.350s; first image 0.685s; warm image 0.640s; batch 3 ảnh 1.877s; compact 0.081s; full 0.156s.

## 3. OCR và engine

Benchmark synthetic ghi 1 Paddle init/process và 5 scene OCR, 0 ROI/fallback. Test fake xác nhận batch hai ảnh gọi factory engine đúng một lần, engine fail không thay đổi kết quả cũ, và lần chạy sau vẫn có thể tạo engine mới.

## 4. Normalization

`raw_text` không bị ghi đè. `cleaned_text` chỉ uppercase/bỏ ký tự phân cách; `normalized_text` giữ cleaned text hiện tại. Các thay thế O/0, I/1, B/8, S/5, G/6 là `suggested_texts` tối đa 5 kèm `ambiguity_flags` và `needs_review`, không phải OCR chắc chắn. Manual correction được giữ làm text người dùng nhập.

## 5. Excel và model offline

Locked file trả lỗi tiếng Việt yêu cầu đóng Microsoft Excel; file cũ và snapshot RAM không bị xóa. File tạm được cleanup khi lỗi. Khi ONNX detector không khởi tạo, processor thêm warning và tiếp tục OCR fallback. `CHECK_VEHICLE_DISABLE_ONNX_DETECTOR=1` dùng cho test/benchmark offline; detector có lock và cờ attempted nên chỉ resolve/load một lần mỗi process.

## 6. Files tạo/sửa

- `AGENTS.md`
- `check_vehicle_ocr/app.py`
- `check_vehicle_ocr/models.py`
- `check_vehicle_ocr/ocr.py`
- `check_vehicle_ocr/processor.py`
- `check_vehicle_ocr/excel_export.py`
- `tests/smoke_test.py`
- `tests/performance_benchmark.py`
- `tests/performance_stability_test.py`
- `docs/PERFORMANCE_CURRENT.md`
- `docs/performance-stability-improvements-report.md`

## 7. Lệnh và kết quả

- `python -B` + `ast.parse`: 18 file pass.
- `python -B tests\\smoke_test.py`: pass.
- `python -B tests\\performance_stability_test.py`: pass.
- `python -B tests\\performance_benchmark.py`: 3 lượt pass.
- Khởi tạo/đóng Tkinter: pass.

Tổng: 5 nhóm kiểm chứng pass sau lần chạy smoke cuối; không có test fail còn lại. Warning còn lại: Paddle báo thiếu `ccache`; không chặn OCR. Không chạy build, installer, camera, API ngoài, tải Internet, Git, database, tracking hay nghiệp vụ xe vào/ra. Ứng dụng chưa được tuyên bố production-ready.
