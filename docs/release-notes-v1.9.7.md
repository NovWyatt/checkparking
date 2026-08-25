# Check Vehicle OCR v1.9.7

## Đối chiếu biển số từ Excel

- Thêm mục **Đối chiếu** trong thanh điều hướng.
- Chọn file Excel OCR đã kiểm tra, file báo phí và tùy chọn file phần mềm. Có thể chỉ đối chiếu báo phí.
- Bấm **Tải mẫu báo phí** hoặc **Tải mẫu phần mềm**, sau đó dán danh sách vào cột `Biển số` của sheet `Danh_sach`.
- File báo cáo tách kết quả thành các sheet dễ kiểm tra: khớp báo phí, khớp gần báo phí, có phần mềm nhưng không báo phí, không có ở cả hai nguồn, cần xác nhận, trùng lặp và dữ liệu dư.

## Quy tắc khớp gần an toàn

Ứng dụng luôn ưu tiên khớp chính xác. Khớp gần chỉ được nhận khi khác tối đa một ký tự, đủ 3 hoặc 4 ký tự cuối theo lựa chọn và chỉ có một ứng viên duy nhất. Các trường hợp sai/thiếu/dư số hoặc có nhiều ứng viên được đưa vào `Cần_xác_nhận`, không tự kết luận.

## Giao diện

Giao diện Quét, Kết quả, Cài đặt và Đối chiếu được làm mới theo hệ màu sáng/tối thống nhất. Luồng OCR, duyệt thủ công và xuất Excel vẫn được giữ nguyên.

## Lưu ý

Tính năng đã được kiểm tra bằng dữ liệu Excel tổng hợp. Hãy kiểm tra các sheet `Cần_xác_nhận` và `Trùng_lặp` trước khi dùng báo cáo cho nghiệp vụ thực tế.
