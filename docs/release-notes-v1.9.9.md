# Check Vehicle OCR v1.9.9

## Ảnh gốc rõ hơn trong Kết quả

Màn **Kết quả** có vùng xem ảnh lớn hơn. Thanh kéo ngang giữa ảnh và thông tin biển số cho phép ưu tiên xem ảnh hoặc ưu tiên sửa dữ liệu trong từng thời điểm. Ảnh tự co vừa vùng xem, không còn bị giới hạn ở kích thước thumbnail nhỏ cố định.

## Đối chiếu theo đúng dữ liệu gốc OCR

Excel OCR đã được kiểm tra là nguồn gốc. Ứng dụng luôn dò báo phí trước, sau đó chỉ dò phần mềm cho biển chưa khớp báo phí.

Khớp gần chỉ tự chấp nhận khi có đúng một ứng viên và sai tối đa một ký tự. Quy tắc này bao gồm sai chữ/số, thiếu một ký tự hoặc dư một ký tự trong báo phí/phần mềm. Khi thiếu hoặc dư ký tự làm lệch vị trí, ứng dụng canh chỉnh phần đuôi 3 hoặc 4 ký tự trước khi kết luận. Nhiều ứng viên hoặc khác biệt lớn hơn một ký tự vẫn nằm trong sheet `Cần_xác_nhận` để tránh ghép sai biển.
