# Báo cáo sửa ánh xạ preset ưu tiên tốc độ

## Mục tiêu

Khắc phục tình trạng chọn **Ưu tiên tốc độ** nhưng ứng dụng vẫn dùng model PP-OCRv6 Small. Preset này cần dùng PP-OCRv6 Tiny để giảm thời gian OCR trên ảnh rõ, trong khi chế độ Cân bằng vẫn giữ PP-OCRv6 Small.

## Nguyên nhân đã xác nhận

- Trước bản sửa, `current_model_selection()` chỉ chọn PP-OCRv6 Tiny khi preset là `LOW_MEMORY`; `FAST` vẫn rơi về PP-OCRv6 Small.
- PaddleOCR cục bộ dùng một predictor tuần tự; tăng số worker ảnh không làm model OCR chạy song song.

## Thay đổi

- Ánh xạ `FAST` và `LOW_MEMORY` sang PP-OCRv6 Tiny.
- Giữ `AUTO`/Cân bằng dùng PP-OCRv6 Small.
- Cập nhật gợi ý giao diện để nêu rõ đánh đổi tốc độ/độ ổn định.
- Thêm test hồi quy xác nhận preset `FAST` thực sự chọn Tiny trong thư mục cấu hình tạm.

## File thay đổi

- `check_vehicle_ocr/ocr_models.py`
- `check_vehicle_ocr/app.py`
- `check_vehicle_ocr/processor.py`
- `check_vehicle_ocr/version.py`
- `tests/performance_preset_model_test.py`
- `tests/performance_timing_instrumentation_test.py`
- `CHANGELOG.md`
- `docs/release-notes-v1.9.4.md`
- `docs/fix-fast-preset-model-selection-report.md`

## Benchmark ảnh thật

Đã quét 16 ảnh JPG 1920×2560 trong `C:\Users\Wyatt\Desktop\test-img`. Hai lượt chạy dùng cùng chế độ pipeline `balanced`, cùng ngưỡng và cùng detector ONNX đã có sẵn trong máy; cấu hình `APPDATA` được tách riêng. Khác biệt duy nhất là preset/model OCR.

| Preset | Model log xác nhận | Thời gian | Tốc độ | Có kết quả | Cần review |
| --- | --- | ---: | ---: | ---: | ---: |
| Ưu tiên tốc độ (`FAST`) | `PP-OCRv6_tiny_det` + `PP-OCRv6_tiny_rec` | 158,993 giây | 6,038 ảnh/phút | 14/16 | 2/16 |
| Cân bằng (`AUTO`) | `PP-OCRv6_small_det` + `PP-OCRv6_small_rec` | 417,213 giây | 2,301 ảnh/phút | 15/16 | 1/16 |

Tiny hoàn thành nhanh hơn **2,62 lần** trên máy và bộ ảnh này, nhưng có ít hơn một ảnh đọc được so với Small. Thư mục ảnh không có manifest/nhãn biển số chuẩn, nên benchmark không xác nhận được exact-match hoặc độ chính xác ký tự; chỉ phản ánh tốc độ và số ảnh có kết quả của pipeline.

## Sửa lỗi Fast không nhận được biển số

Cấu hình sử dụng thực tế là `FAST` kết hợp chế độ quét `Nhanh`. Nguyên nhân là nhánh `Nhanh` cấm hoàn toàn lượt OCR toàn ảnh dự phòng khi mọi crop detector bị từ chối. Điều này giúp lượt cũ nhanh nhưng chỉ đọc được 1/16 ảnh.

Đã thay đổi để `Nhanh` chỉ thực hiện **một** lượt OCR toàn ảnh dự phòng khi không có crop nào đạt điều kiện. Nếu detector crop đã đọc được biển thì Fast vẫn dừng sớm như trước.

| Fast + Tiny | Thời gian | Tốc độ | Có kết quả | Cần review |
| --- | ---: | ---: | ---: | ---: |
| Trước sửa fallback | 96,669 giây | 9,931 ảnh/phút | 1/16 | 15/16 |
| Sau sửa fallback | 144,914 giây | 6,625 ảnh/phút | 14/16 | 2/16 |

Kết quả sau sửa lần đầu là `audit-output/test-img-fast-tiny-rescue.json`. Có thêm 48,245 giây cho 16 ảnh, đổi lại nhận thêm 13 ảnh có kết quả.

## Hoàn thiện rescue cho ảnh biển rõ

Hai ảnh còn lại đều có biển rõ nhưng detector chọn nhầm vùng bùn xe, timestamp hoặc chỉ một hàng ký tự. Đã thêm tối đa hai crop cứu hộ tại vùng trung tâm xe, chỉ chạy sau khi detector crop và fallback toàn ảnh đều không cho biển hợp lệ. OCR trên các vùng này dùng giới hạn detector `960/max` để tách riêng hai hàng biển, tránh lẫn chữ thương hiệu xe hoặc watermark.

| Điều kiện chạy FAST + Tiny | Thời gian | Tốc độ | Có kết quả | Cần review |
| --- | ---: | ---: | ---: | ---: |
| Detector ONNX sẵn sàng trong cache | 16,819 giây | 57,077 ảnh/phút | 16/16 | 0/16 |
| Tắt detector ONNX để kiểm chứng fallback | 141,988 giây | 6,761 ảnh/phút | 16/16 | 0/16 |

Kết quả chi tiết là `audit-output/test-img-fast-tiny-center-rescue-warm.json` và `audit-output/test-img-fast-tiny-center-double-rescue-no-onnx.json`. Tốc độ detector ONNX chỉ có giá trị sau khi model đã sẵn sàng; lượt đầu có thể chậm hơn nếu máy cần chuẩn bị cache model.

Kết quả JSON chi tiết (không theo dõi bởi Git) nằm ở:

- `audit-output/test-img-balanced-tiny-isolated.json`
- `audit-output/test-img-balanced-small-isolated.json`

## Lệnh đã chạy

```powershell
$env:APPDATA = '<profile-tạm-FAST>'
.\.venv\Scripts\python.exe -c "from check_vehicle_ocr.config import save_settings; save_settings({'performance_preset': 'FAST'})"
.\.venv\Scripts\python.exe tools\benchmark_dataset.py --folder C:\Users\Wyatt\Desktop\test-img --mode balanced --output audit-output\test-img-balanced-tiny-isolated.json

$env:APPDATA = '<profile-tạm-AUTO>'
.\.venv\Scripts\python.exe -c "from check_vehicle_ocr.config import save_settings; save_settings({'performance_preset': 'AUTO'})"
.\.venv\Scripts\python.exe tools\benchmark_dataset.py --folder C:\Users\Wyatt\Desktop\test-img --mode balanced --output audit-output\test-img-balanced-small-isolated.json

.\.venv\Scripts\python.exe -B tests\performance_preset_model_test.py
.\.venv\Scripts\python.exe -B tests\performance_timing_instrumentation_test.py
.\.venv\Scripts\python.exe -B tests\smoke_test.py
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests
git diff --check

.\.venv\Scripts\python.exe tools\benchmark_dataset.py --folder C:\Users\Wyatt\Desktop\test-img --mode fast --output audit-output\test-img-fast-tiny-rescue.json
.\.venv\Scripts\python.exe tools\benchmark_dataset.py --folder C:\Users\Wyatt\Desktop\test-img --mode fast --output audit-output\test-img-fast-tiny-center-rescue-warm.json
$env:CHECK_VEHICLE_DISABLE_ONNX_DETECTOR = '1'
.\.venv\Scripts\python.exe tools\benchmark_dataset.py --folder C:\Users\Wyatt\Desktop\test-img --mode fast --output audit-output\test-img-fast-tiny-center-double-rescue-no-onnx.json

.\build_exe.ps1 -SkipInstall
.\release\CheckVehicleOCR\CheckVehicleOCR.exe --runtime-health-check
.\release\CheckVehicleOCR\CheckVehicleOCR.exe --self-test-paddle
```

## Kết quả kiểm tra

- `performance_preset_model_test.py`: pass.
- `performance_timing_instrumentation_test.py`: pass.
- `smoke_test.py`: pass, khởi tạo và dùng PP-OCRv6 Tiny từ bundle dự án.
- `compileall`: pass.
- `git diff --check`: pass.
- PaddlePaddle chỉ in warning môi trường về thiếu `ccache`; không làm kiểm tra thất bại.
- Benchmark FAST + Tiny cuối cùng: 16/16 ảnh có kết quả trong cả môi trường detector ONNX sẵn sàng và môi trường đã tắt detector.

## Chưa kiểm tra và lưu ý

- Chưa xác nhận độ chính xác tuyệt đối vì không có nhãn chuẩn cho 16 ảnh.
- Tiny có thể kém bền hơn với ảnh mờ, nghiêng hoặc biển số nhỏ; dùng Cân bằng khi ưu tiên nhận dạng.
- Đã build EXE thử nghiệm v1.9.4 tại `release/CheckVehicleOCR/CheckVehicleOCR.exe` bằng `./build_exe.ps1 -SkipInstall`. Bản EXE local có detector ONNX 7,41 MiB từ cache đã kiểm tra.
- Đã chạy `--runtime-health-check` và `--self-test-paddle` trên EXE với profile tạm; cả hai trả mã 0, self-test ghi `PaddleOCR self-test OK`.
- Sau sửa fallback, EXE đã được build lại và hai kiểm tra trên tiếp tục trả mã 0.
- Weights detector ONNX không được commit source vì chưa có manifest nguồn và điều khoản phân phối weights đã xác minh; source vẫn dùng fallback cục bộ đạt 16/16 khi detector không có.
- Installer không được build trong công việc này.
