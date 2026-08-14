# Báo cáo detector miễn phí và quyền phân phối

## Mục tiêu

Đảm bảo bản tải từ GitHub có thể dùng miễn phí, offline và không phụ thuộc vào weights detector có quyền phân phối chưa được xác minh.

## Kết quả audit

| Thành phần | Kết luận | Quyết định |
| --- | --- | --- |
| PP-OCRv6 Small/Tiny | Apache-2.0, hash đã pin trong `models/manifest.json` | Giữ, đóng gói bằng Git LFS. |
| YOLOv9 `open-image-models` | Code MIT nhưng maintainer xác nhận weights dùng fork YOLOv9 GPL-3.0 và không đưa ra ý kiến pháp lý dứt khoát về distribution | Không bundle, không tải runtime. |
| OpenCV Zoo YuNet | Apache-2.0 ngay trong thư mục model; source commit và hash LFS công bố | Bundle mặc định. |

YuNet model có tên `license_plate_detection_lpd_yunet_2023mar.onnx`, SHA-256 `6d4978a7b6d25514d5e24811b82bfb511d166bdd8ca3b03aa63c1623d4d039c7`, source commit `b4971d625240509dae6119e19201fe30919a285f`. Git LFS pointer tại commit này công bố chính SHA-256 và kích thước `4.146.213` byte. License và attribution được giữ tại `models/opencv_yunet/`.

## Thay đổi

- `check_vehicle_ocr/opencv_yunet_detector.py`: detector OpenCV DNN cục bộ, không có network path.
- `check_vehicle_ocr/plate_detector.py`: giữ API nội bộ tương thích nhưng chuyển sang YuNet.
- `models/opencv_yunet/`: model Apache-2.0, `LICENSE`, `NOTICE.md` và manifest hash/nguồn.
- `processor.py`: rescue crop mở rộng có giới hạn và xác minh Small có điều kiện cho biển nghiêng mạnh.
- `CheckVehicleOCR.spec`, dependency, workflow và notice: bỏ bundle/cache/import của detector cũ; bundle model YuNet và thêm test release/CI.

## Benchmark có nhãn

Manifest nhãn đối chiếu thủ công chỉ nằm ở `audit-output/` local, không đưa ảnh/tên ảnh vào Git hoặc release. Trên 16 JPG 1920×2560, FAST với YuNet Apache-2.0 đạt 16/16 exact match, 100% ký tự và 47,68 ảnh/phút.

YuNet upstream lưu ý model được huấn luyện với biển Trung Quốc. Vì vậy benchmark này là bằng chứng trên bộ ảnh đã có, không phải tuyên bố accuracy tổng quát cho mọi biển Việt Nam.

## Kiểm tra bắt buộc

- Hash model YuNet khớp hash LFS upstream.
- Test YuNet mở model offline qua OpenCV DNN và kiểm tra attribution/license/rotation marker.
- Regression FAST kiểm tra crop mở rộng, Tiny-to-Small verification và ưu tiên candidate verified khi biển nghiêng.
- Release CI build từ Git LFS, test model bundle, build installer/portable, kiểm hash asset và upload GitHub Release.

## Kiểm tra đã chạy trước phát hành

```powershell
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests tools main.py
.\.venv\Scripts\python.exe -B tests\opencv_yunet_detector_test.py
.\.venv\Scripts\python.exe -B tests\performance_timing_instrumentation_test.py
.\.venv\Scripts\python.exe -B tests\smoke_test.py
.\.venv\Scripts\python.exe -B tests\false_positive_regression_test.py
.\.venv\Scripts\python.exe -B tests\performance_stability_test.py
.\.venv\Scripts\python.exe -B tests\release_system_test.py
.\.venv\Scripts\python.exe -B tests\release_v180_test.py
.\.venv\Scripts\python.exe -B tests\v190_runtime_version_test.py
.\.venv\Scripts\python.exe -B tests\ocr_process_worker_test.py
.\.venv\Scripts\python.exe -B tests\ocr_process_app_integration_test.py
.\.venv\Scripts\python.exe -B tests\ocr_process_import_boundary_test.py
.\.venv\Scripts\python.exe -B tests\ocr_process_heartbeat_test.py
git diff --check
```

Các lệnh trên đều pass. Paddle chỉ in warning môi trường về `ccache`; không làm test thất bại.

## Rủi ro còn lại

- Không có mô hình detector miễn phí nào bảo đảm accuracy trên mọi góc chụp/loại biển; người dùng vẫn cần review các ảnh khó.
- Lần đầu FAST gặp crop nghiêng hoặc lỗi cấu trúc sẽ khởi tạo thêm Small predictor và dùng thêm RAM cho đến khi batch kết thúc.
- Báo cáo này không phải tư vấn pháp lý; nó ghi lại license/nguồn/hash công khai đã kiểm tra.
