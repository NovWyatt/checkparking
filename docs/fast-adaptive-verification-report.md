# Báo cáo nâng cấp Fast Adaptive Verify

## Mục tiêu

Cải thiện độ chính xác của chế độ **Nhanh** mà không biến toàn bộ batch thành PP-OCRv6 Small. Giữ nguyên luồng nhập ảnh/thư mục, review thủ công, xuất Excel, detector ONNX và các fallback hiện có.

## Nguyên nhân đã xác nhận

Trong bộ ảnh được cung cấp, Tiny đọc biển `76-G1 255.09` thành `76-G1T 255.03`. Crop detector chứa logo ở mép biển và ảnh nghiêng. Cùng crop đó, PP-OCRv6 Small trả về đúng `76-G1 255.09`.

## Thay đổi

- `check_vehicle_ocr/plate_formatting.py`: thêm hàm kiểm tra thuần túy xem OCR có khớp một cấu trúc biển Việt Nam chuẩn hay không; hàm không tự thay ký tự mơ hồ hoặc ép định dạng.
- `check_vehicle_ocr/paddle_ocr_engine.py`: thêm PP-OCRv6 Small xác minh lười, tách predictor với Tiny và chỉ khởi tạo khi Tiny đã cho kết quả bất thường.
- `check_vehicle_ocr/processor.py`: FAST gọi xác minh tối đa một lần cho một crop detector chỉ khi mọi candidate hợp lệ của crop đó đều không có cấu trúc chuẩn. Candidate Small được chấm điểm theo quy tắc cũ; candidate Tiny vẫn được giữ để review/debug nếu không được chọn.
- `tests/performance_timing_instrumentation_test.py`: khóa trường hợp Tiny đọc sai `76G1T25503`, Small trả lại `76G125509`, và số lượt xác minh là một.

## Benchmark có nhãn

Manifest nhãn được đối chiếu thủ công chỉ nằm trong `audit-output/` local, không đưa ảnh, tên ảnh hoặc manifest vào Git/release. Cùng máy, cùng folder 16 JPG 1920×2560, FAST, ONNX cache sẵn sàng:

| Phiên bản pipeline | Exact match | Độ chính xác ký tự | Sai kết quả | Tốc độ |
| --- | ---: | ---: | ---: | ---: |
| Tiny trước xác minh | 15/16 (93,75%) | 98,13% | 1 | 75,12 ảnh/phút |
| Tiny + Fast Adaptive Verify | 16/16 (100%) | 100% | 0 | 65,55 ảnh/phút |

Độ chậm khoảng 12,7% chỉ xảy ra vì batch này có một crop cần khởi tạo/call Small. Các crop hợp lệ vẫn không tạo predictor Small hay thêm OCR call.

## Lệnh kiểm tra

```powershell
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests tools main.py
.\.venv\Scripts\python.exe -B tests\plate_formatting_test.py
.\.venv\Scripts\python.exe -B tests\v190_candidate_scoring_test.py
.\.venv\Scripts\python.exe -B tests\performance_timing_instrumentation_test.py
.\.venv\Scripts\python.exe -B tools\benchmark_dataset.py --folder C:\Users\Wyatt\Desktop\test-img --manifest audit-output\test-img-manual-manifest.json --mode fast --output audit-output\test-img-fast-adaptive-verify-labelled.json
git diff --check
```

## Kết quả kiểm tra

- `compileall`: pass.
- `plate_formatting_test.py`: pass.
- `v190_candidate_scoring_test.py`: pass.
- `performance_timing_instrumentation_test.py`: pass.
- Benchmark có nhãn: 16/16 exact match, 100% ký tự, không có ảnh không đọc được hoặc cần review.
- PaddlePaddle chỉ in warning môi trường về `ccache`; không làm kiểm tra thất bại.

## Chưa kiểm tra và rủi ro còn lại

- Nhãn là đối chiếu thủ công nội bộ của 16 ảnh, cần thêm dữ liệu đa dạng và nhãn độc lập trước khi công bố độ chính xác tổng quát.
- Chưa đo memory peak của batch có khởi tạo verifier Small; lần xác minh đầu tiên sẽ dùng thêm RAM trong process OCR cho đến khi batch kết thúc.
- Chưa benchmark detector ONNX bị tắt, biển đặc biệt, xe ô tô, ảnh mờ hoặc GPU trong bản 1.9.5.
