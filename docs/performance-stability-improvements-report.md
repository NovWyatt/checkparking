# Báo cáo cải thiện hiệu năng và độ ổn định

## Mục tiêu

Cải thiện trải nghiệm xử lý ảnh hàng loạt mà không thay đổi chức năng nhập ảnh/thư mục, review biển số và xuất Excel.

## Files changed

- `check_vehicle_ocr/app.py`
- `check_vehicle_ocr/processor.py`
- `check_vehicle_ocr/excel_export.py`
- `tests/smoke_test.py`
- `AGENTS.md`

## Main changes

- Khởi tạo engine (bao gồm PaddleOCR) chuyển từ UI thread sang worker xử lý. Engine được tạo một lần cho batch và tái sử dụng cho từng ảnh.
- UI nhận trạng thái engine sẵn sàng/lỗi qua event queue, giữ giao diện phản hồi trong thời gian nạp model.
- Chế độ PaddleOCR không phải `Quét kỹ` chỉ OCR lượt vùng lớn đầu tiên. ROI dự phòng chỉ chạy nếu lượt đầu chưa đọc được biển hợp lệ; `Quét kỹ` giữ nguyên quét toàn bộ vùng lớn.
- Xuất Excel chạy ở worker nền từ snapshot kết quả; người dùng có thể chọn không nhúng thumbnail để xuất nhanh hơn và tạo file nhỏ hơn.
- Dữ liệu Excel bắt đầu bằng `=`, `+`, `-` hoặc `@` được prefix apostrophe để Excel lưu như text thay vì công thức.
- Smoke test bổ sung kiểm tra tránh OCR ROI lặp, export compact không nhúng ảnh và Formula Injection.

## Commands run

- `python -B` với `ast.parse` cho toàn bộ 16 file Python.
- `python -B tests\\smoke_test.py` với `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`.

## Test results

- Smoke test: pass (`smoke_test OK`).
- PaddleOCR đọc model từ cache local và nhận biển tổng hợp theo test có sẵn.
- Warning không chặn test: Paddle báo không có `ccache`.

## Not tested

- Không benchmark ảnh thật hoặc camera/RTSP.
- Không gọi Gemini, OpenAI hoặc Plate Recognizer API.
- Không build `.exe`/installer.
- Không đo thời gian xuất ở quy mô hàng nghìn ảnh; tối ưu được kiểm tra bằng luồng code và smoke test.

## Remaining risks and next steps

- OCR thực tế vẫn phụ thuộc chất lượng ảnh/model; cần benchmark dữ liệu được cấp quyền.
- Export nền không thể hủy giữa chừng; có thể bổ sung progress/cancel nếu cần.
- Nên tiếp tục với persistence/database trước khi mở rộng sang nghiệp vụ bãi xe.
