# Benchmark ảnh thật/local

Tool `tools\benchmark_dataset.py` chỉ dùng ảnh trên máy. Không tự tải ảnh, không gọi API và không tạo số liệu nếu chưa có dữ liệu thực.

## Manifest tùy chọn

Đặt `manifest.json` cạnh folder ảnh, dùng đường dẫn tương đối:

```json
[
  {
    "image": "images/xe_001.jpg",
    "expected_plate": "51H12345"
  }
]
```

## Chạy

```powershell
python -B tools\benchmark_dataset.py `
  --folder .\dataset `
  --manifest .\dataset\manifest.json `
  --mode balanced `
  --output .\audit-output\real-image-balanced.json
```

Lặp lại `--mode fast`, `balanced`, `thorough` trên cùng manifest để so sánh công bằng. Tool ghi tổng ảnh, exact match, character accuracy, không đọc được, cần review, false positive, thời gian và ảnh/phút.

Nếu không có manifest, tool vẫn chạy folder local nhưng không thể tính exact match/character accuracy/false positive có nhãn. Chưa có folder ảnh thật được cung cấp trong milestone này, nên chưa chạy tool và không có kết luận accuracy thực tế.
