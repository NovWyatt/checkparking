# Báo cáo cải thiện xem ảnh và đối chiếu

## Mục tiêu

Tăng khả năng xem ảnh gốc tại Kết quả và cố định quy tắc nghiệp vụ: OCR đã duyệt là nguồn dữ liệu gốc, báo phí/phần mềm là các danh sách cần đối chiếu có thể sai, thiếu hoặc dư một ký tự.

## File thay đổi

- `check_vehicle_ocr/ui/pages/results_page.py`: tăng vùng ảnh, chia phần chi tiết thành hai vùng kéo được và vẫn giữ ô sửa biển số.
- `check_vehicle_ocr/app.py`: ảnh gốc tự co theo vùng xem sau khi người dùng kéo thanh chia; crop biển số có kích thước phù hợp vùng phụ.
- `check_vehicle_ocr/reconciliation.py`: canh chỉnh chuỗi ở phần đuôi khi so khớp gần để nhận đúng một lỗi thêm/bớt ký tự.
- `check_vehicle_ocr/ui/pages/reconciliation_page.py`: mô tả rõ OCR là danh sách gốc, báo phí dò trước và phần mềm dò sau.
- `tests/reconciliation_test.py`, `tests/ui_simplification_test.py`: kiểm tra sai một ký tự, thiếu một ký tự, dư một ký tự và bố cục vùng xem ảnh.
- `README.md`, `CHANGELOG.md`, `docs/release-notes-v1.9.9.md`: cập nhật hướng dẫn và ghi chú phát hành.

## Quy tắc đối chiếu

- Khớp hoàn toàn sau khi chuẩn hóa luôn được ưu tiên.
- OCR đã duyệt không bị thay thế bởi báo phí hoặc phần mềm.
- Khớp gần cần duy nhất một ứng viên và khoảng cách chỉnh sửa đúng một ký tự.
- Phần đuôi 3 hoặc 4 ký tự được so theo canh chỉnh chuỗi, nhờ đó thiếu/dư một ký tự không làm lệch toàn bộ vị trí cuối.
- Có từ hai ứng viên gần đúng hoặc sai khác lớn hơn một ký tự được đưa vào `Cần_xác_nhận`.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -B -m compileall -q check_vehicle_ocr tests tools main.py
.\.venv\Scripts\python.exe -B tests\reconciliation_test.py
.\.venv\Scripts\python.exe -B tests\ui_simplification_test.py
.\.venv\Scripts\python.exe -B tests\ui_smoke_test.py
.\.venv\Scripts\python.exe -B tests\theme_contrast_test.py
.\.venv\Scripts\python.exe -B tools\capture_ui_review.py
git diff --check
```

Các kiểm tra trên phải hoàn tất trước khi phát hành. Bộ test đối chiếu bao gồm báo phí thiếu một ký tự và phần mềm dư một ký tự.

## Giới hạn còn lại

- Quy tắc tự chấp nhận vẫn bị giới hạn đúng một lỗi và một ứng viên. Các trường hợp phức tạp cần được kiểm tra thủ công trong `Cần_xác_nhận`.
- Chưa có danh sách báo phí/phần mềm thực tế được cung cấp trong đợt thay đổi này để hiệu chỉnh thêm theo cách nhập liệu của từng hệ thống.
