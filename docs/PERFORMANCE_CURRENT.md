# Hiệu năng hiện tại

Benchmark chạy ngày hiện tại bằng `python -B tests\\performance_benchmark.py` trên Windows/Python 3.11, model PaddleOCR đã có trong cache local. Mỗi lượt chạy ở process riêng, không dùng API hay Internet, và dùng ảnh synthetic 900x520 có một biển số rõ.

| Hạng mục | Lần 1 | Lần 2 | Lần 3 | Median |
|---|---:|---:|---:|---:|
| Paddle cold init | 1.350s | 1.401s | 1.287s | 1.350s |
| First image | 0.678s | 0.685s | 0.743s | 0.685s |
| Warm image | 0.628s | 0.640s | 0.662s | 0.640s |
| Batch (3 ảnh) | 1.877s | 1.872s | 1.883s | 1.877s |
| Excel compact | 0.081s | 0.073s | 0.082s | 0.081s |
| Excel full | 0.147s | 0.156s | 0.157s | 0.156s |

- Engine PaddleOCR khởi tạo: 1 lần mỗi process benchmark.
- Tổng OCR call: 5 scene, 0 ROI/fallback (first, warm và batch 3 ảnh).
- Workbook compact median 11,511 bytes; full median 39,935 bytes, lớn hơn khoảng 3.47 lần.
- Import app median 2.549s; khởi tạo UI median 0.073s.

Giới hạn: đây là ảnh synthetic rõ, model đã có cache local, không đại diện ảnh tối, nghiêng, nhiều xe, disk chậm hoặc camera thật. Số liệu không phải accuracy/throughput production.
