# Báo cáo cải thiện thao tác Đối chiếu và Kết quả

## Mục tiêu

Làm rõ nút chọn file Báo phí/Phần mềm và giúp người dùng luôn đọc, nhập, sửa biển số bằng tay trong màn hình Kết quả một cách dễ dàng.

## Thay đổi

- Tách nút `Chọn file` và `Tải mẫu` thành hai vị trí riêng ở dòng Báo phí và Phần mềm. Người dùng có thể vừa chọn file đã có, vừa tải mẫu khi cần.
- Tăng vùng Kết quả bên phải và chiều cao danh sách biển số.
- Mỗi biển số có một ô nhập lớn toàn chiều ngang, font rõ hơn, có nhãn `Sửa hoặc nhập biển số`, cùng nút Xóa và trạng thái đã kiểm tra.
- Hỗ trợ `Ctrl+A` trong ô nhập để thay toàn bộ biển số nhanh.

## File thay đổi

- `check_vehicle_ocr/ui/pages/reconciliation_page.py`
- `check_vehicle_ocr/ui/pages/results_page.py`
- `check_vehicle_ocr/ui/theme.py`
- `check_vehicle_ocr/app.py`
- `tests/ui_simplification_test.py`

## Kiểm tra đã chạy

```powershell
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests tools main.py
.\.venv\Scripts\python.exe -B tests\ui_simplification_test.py
.\.venv\Scripts\python.exe -B tests\ui_smoke_test.py
.\.venv\Scripts\python.exe -B tests\reconciliation_test.py
.\.venv\Scripts\python.exe -B tests\theme_contrast_test.py
.\.venv\Scripts\python.exe -B tools\capture_ui_review.py
```

Tất cả lệnh trên đều pass. Đã xem trực tiếp ảnh light/dark của màn hình Đối chiếu và Kết quả.

## Phạm vi giữ nguyên

- Không thay đổi pipeline OCR, logic đối chiếu, định dạng biển số hoặc cấu trúc file Excel.
- Được phát hành trong v1.9.8 sau khi hoàn tất cổng kiểm tra phát hành.
