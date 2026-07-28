# Hướng dẫn cho Check Vehicle OCR

## Stack và phạm vi

- Ứng dụng desktop Python 3 dùng Tkinter, OpenCV, PaddleOCR và openpyxl.
- Điểm vào source là `main.py`; UI ở `check_vehicle_ocr/app.py`.
- Giữ nguyên luồng nhập file/thư mục ảnh, review thủ công và xuất Excel.
- Không sửa PaddleOCR lõi hoặc thay model/dependency nếu chưa được yêu cầu rõ ràng.

## Cách làm việc

- Ưu tiên sửa nhỏ, tập trung vào hiệu năng OCR, UI thread và tính an toàn dữ liệu Excel.
- Văn bản tiếng Việt trong source phải là UTF-8 trực tiếp, không HTML entity hoặc Unicode escape.
- Không commit, push, build installer hoặc chạy script build nếu chưa được yêu cầu.
- Không chạy thao tác Git phá hủy, migration/reset hoặc xóa output.

## Kiểm tra

- Dùng `python -B tests\\smoke_test.py` cho thay đổi pipeline/export khi môi trường đã có dependency.
- Dùng parse cú pháp Python trước khi kết thúc nếu test đầy đủ không khả dụng.
- Ghi rõ lệnh nào đã chạy và warning/lỗi thực tế.
