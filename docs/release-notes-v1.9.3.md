# Check Vehicle OCR v1.9.3

## Giao diện mượt hơn khi quét

- Công cụ nhận diện nay chạy tách biệt khỏi giao diện, giúp giảm rõ rệt hiện tượng đứng hoặc khựng khi xử lý ảnh.
- Giữ nguyên PP-OCRv6 Small, detector và các quy tắc nhận dạng biển số đang dùng.
- Kết quả nhận diện không thay đổi trong benchmark regression nội bộ: số biển chính, số ảnh cần review và digest output đều giữ nguyên.
- Bổ sung khả năng phục hồi có giới hạn khi công cụ nhận diện gặp lỗi; nếu không thể tiếp tục, ứng dụng dừng an toàn và giữ các kết quả đã hoàn thành.
- Throughput có thể giảm nhẹ để đổi lấy giao diện phản hồi ổn định hơn trong suốt batch.

Benchmark nội bộ không phải tuyên bố accuracy trên dữ liệu production. Bản phát hành không gửi ảnh hoặc khóa dịch vụ ra ngoài khi dùng OCR cục bộ.
