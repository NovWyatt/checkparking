# Check Vehicle OCR v1.9.10

## Crop biển số luôn có cách hiển thị phù hợp

Trong màn **Kết quả**, vùng **Crop biển số** ưu tiên ảnh crop mà OCR đã tạo. Nếu file crop không còn nhưng detector vẫn có vùng biển hợp lệ, ứng dụng cắt trực tiếp vùng đó từ ảnh gốc để hiển thị.

Khi bạn chọn **Mở Excel đã xuất**, ứng dụng cũng khôi phục đường dẫn crop được lưu trong sheet `Bien_so_doc_duoc`. Crop chỉ được hiện khi file đó vẫn tồn tại trên máy, tránh lấy nhầm ảnh hoặc hiển thị dữ liệu cũ. Nếu file crop của một Excel cũ đã mất, Excel không lưu tọa độ vùng biển nên ảnh gốc một mình không đủ để dựng lại crop chính xác.

## Giữ an toàn dữ liệu

Excel nguồn vẫn luôn được mở ở chế độ chỉ đọc. Bbox toàn ảnh do AI hoặc nhập tay không bao giờ được dùng như crop biển số, nên khung bằng chứng không hiển thị toàn bộ ảnh như một biển số giả.
