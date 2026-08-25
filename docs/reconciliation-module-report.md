# Báo cáo mô-đun đối chiếu Excel

## Mục tiêu

Thêm mô-đun đối chiếu cho quy trình biển số đã OCR và duyệt: dò báo phí trước, sau đó chỉ dò phần mềm cho các biển chưa khớp báo phí. Người dùng có thể bỏ qua phần mềm khi chỉ cần đối chiếu báo phí.

## File thay đổi

- `check_vehicle_ocr/reconciliation.py`: đọc cột biển số từ Excel, tạo file mẫu, đối chiếu chính xác hoặc gần đúng và xuất báo cáo không làm thay đổi file nguồn.
- `check_vehicle_ocr/ui/pages/reconciliation_page.py`: trang Đối chiếu với chọn file, tải mẫu báo phí/phần mềm, bật tắt đối chiếu phần mềm và chọn 3 hoặc 4 ký tự cuối.
- `check_vehicle_ocr/ui/shell.py`, `check_vehicle_ocr/ui/pages/__init__.py`, `check_vehicle_ocr/app.py`: thêm điều hướng, chạy đối chiếu ở worker nền, trạng thái hoàn tất/lỗi và lưu tùy chọn không nhạy cảm.
- `tests/reconciliation_test.py`: kiểm tra file mẫu, khớp chính xác, khớp gần, biển trùng, không có ở cả hai nguồn, chế độ chỉ báo phí và file báo cáo.
- `tests/ui_smoke_test.py`, `tests/ui_simplification_test.py`, `tools/capture_ui_review.py`: kiểm tra trang mới và chụp UI ở light/dark mode.

## Quy tắc đối chiếu

- Luôn chuẩn hóa bằng cách viết hoa và bỏ khoảng trắng, dấu gạch, dấu chấm. Giá trị gốc vẫn được giữ trong báo cáo.
- Khớp chính xác báo phí được xử lý trước. Những biển đã khớp hoàn toàn hoặc khớp gần báo phí không được dò sang phần mềm.
- Khớp gần chỉ được chấp nhận khi có một ứng viên duy nhất, sai tối đa một ký tự và còn trùng số vị trí ký tự cuối theo lựa chọn 3 hoặc 4 ký tự, trừ tối đa một ký tự.
- Thiếu/dư ký tự, nhiều ứng viên hoặc khác biệt không đủ điều kiện được đưa vào sheet `Cần_xác_nhận`.
- Báo cáo tách `Khớp_báo_phí`, `Khớp_gần_báo_phí`, `Phần_mềm_không_báo_phí`, `Không_có_cả_hai`, `Trùng_lặp`, `Dư_báo_phí` và `Dư_phần_mềm` khi có chọn phần mềm.

## Kiểm tra đã chạy

```powershell
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests
.\.venv\Scripts\python.exe -B tests\reconciliation_test.py
.\.venv\Scripts\python.exe -B tests\ui_smoke_test.py
.\.venv\Scripts\python.exe -B tests\ui_simplification_test.py
.\.venv\Scripts\python.exe -B tests\theme_contrast_test.py
.\.venv\Scripts\python.exe -B tools\capture_ui_review.py
git diff --check
```

Các lệnh trên đều pass trong môi trường local.

## Chưa kiểm tra

- Chưa có file báo phí hoặc phần mềm thực tế của người dùng để xác nhận chính xác tên cột, sheet, biển trùng và các trường hợp ngoại lệ nghiệp vụ.
- Chưa phát hành hoặc đóng gói EXE. Người dùng chưa yêu cầu commit, push hay phát hành bản mới.
