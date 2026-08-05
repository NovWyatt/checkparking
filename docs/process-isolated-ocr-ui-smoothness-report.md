# Báo cáo tách tiến trình OCR để giao diện mượt hơn

## 1. Mục tiêu và phạm vi

Mục tiêu duy nhất của thay đổi này là loại bỏ các nhịp khựng Tkinter trong lúc PP-OCRv6 Small chạy inference, đồng thời giữ nguyên detector, model mặc định, formatter, chính sách một biển mỗi ảnh và output OCR. Không sửa source lõi PaddleOCR, không thêm chức năng người dùng và chưa phát hành phiên bản mới.

Dataset acceptance gồm 72 ảnh JPG thực tế, toàn bộ 1920×2560, tổng 35.213.547 byte. Ảnh chỉ được đọc. Tên ảnh, pixel, crop và output chứa dữ liệu thật không được đưa vào Git hoặc package.

Môi trường đo:

- CPU: Intel Core i5-12500H, 12 core/16 logical processor.
- GPU có trên máy: Intel Iris Xe và NVIDIA GeForce RTX 3050 Laptop; benchmark dùng CPU.
- Python source: 3.11.9 x64.
- PaddleOCR 3.7.0, PaddlePaddle 3.3.1, PaddleX 3.7.2, NumPy 2.3.5.
- Model giữ nguyên: `PP-OCRv6_small_det` + `PP-OCRv6_small_rec`.
- Windows power plan khi kiểm tra: Balanced.

## 2. Nguyên nhân đã xác nhận

Pipeline cũ chạy Paddle inference trong worker thread nhưng vẫn ở cùng process với Tkinter:

```text
Tk process → worker thread → Paddle native inference
```

Paddle native inference chiếm CPU/GIL theo từng nhịp dài. Worker thread không gọi Tk trực tiếp, nhưng main event loop vẫn không được lập lịch đều. Đây là nguyên nhân đã đo được, không phải suy đoán từ preview, Treeview, formatter hoặc số image worker.

Actual packaged baseline trên 72 ảnh:

- 119,293 giây, gần số tham chiếu v1.9.2 là 117,310 giây.
- heartbeat p95 1.166,177 ms; max 2.100,601 ms.
- 110 block >100 ms, 85 block >250 ms, 82 block >500 ms.
- screenshot cuối xác nhận batch thực sự hoàn tất.

## 3. Benchmark ba kiến trúc

Harness dùng cùng dataset, FAST, local-only, không Tesseract/AI/Telegram, một biển mỗi ảnh và cùng digest output. Heartbeat Tk chạy mỗi 50 ms.

| Metric | A — worker thread | B — process + queue | C — ProcessPool, 1 worker |
|---|---:|---:|---:|
| Tổng ảnh | 72 | 72 | 72 |
| Tổng thời gian | 163,548 s | 153,616 s | 135,363 s |
| Ảnh/phút | 26,41 | 28,12 | 31,91 |
| UI heartbeat p95 | 1.802,07 ms | 15,39 ms | 16,09 ms |
| UI heartbeat p99 | 2.767,08 ms | 19,96 ms | 23,53 ms |
| UI max stall | 3.392,61 ms | 23,45 ms | 30,69 ms |
| Block >100 / >250 / >500 ms | 152 / 89 / 85 | 0 / 0 / 0 | 0 / 0 / 0 |
| Peak process-tree RSS | 529,5 MB | 876,4 MB | 874,7 MB |
| Paddle init | 4,308 s | 3,641 s | 3,386 s |
| Paddle init count | 1 | 1 | 1 |
| Primary / review | 70 / 2 | 70 / 2 | 70 / 2 |
| Output digest | `fb76d528…ebd2b` | giống A | giống A |

Thời gian tuyệt đối của ba lượt đơn có dao động do power/thermal và thứ tự chạy; không dùng chênh lệch C nhanh hơn B trong một lượt để kết luận ProcessPool intrinsically nhanh hơn. Kết luận ổn định là B/C đều loại stall, giữ output và không tăng số inference. B được chọn vì protocol queue trực tiếp cho phép kiểm soát startup, cancel, crash/restart và shutdown rõ ràng hơn ProcessPool.

## 4. Kiến trúc được giữ

```text
Tkinter process
  → bounded multiprocessing Queue (tối đa 4)
  → một OCR process cố định
  → một PaddleOCR instance sống xuyên suốt các batch trong phiên app
  → result Queue
  → event Queue hiện có của Tkinter
```

Task chỉ truyền dữ liệu nhỏ:

- request ID;
- đường dẫn ảnh và thư mục crop;
- FAST/BALANCED/THOROUGH;
- loại biển và số biển dự kiến;
- blur/confidence threshold.

Không serialize frame 1920×2560. Child tự đọc ảnh từ path một lần. Benchmark path-backed giữ throughput trong acceptance nên shared memory không cần thiết; thêm shared memory lúc này chỉ tăng lifecycle/cleanup risk.

Result trả về gồm `ImageResult`, OCR text chính, confidence, bbox/candidate, timing và error. Main UI không import `paddleocr` khi import `check_vehicle_ocr.app`, và không chạy Paddle native inference.

## 5. Lifecycle và an toàn process

- Windows luôn dùng `spawn`.
- `freeze_support()` có ở entrypoint source và package entrypoint.
- Process khởi động lười ở batch Paddle đầu tiên và được tái sử dụng; model init đúng một lần trong phiên bình thường.
- Queue request/result đều bounded.
- Stop đặt cờ cancel, không submit task mới; inference đang chạy được phép hoàn tất và kết quả đã xong được giữ.
- Crash trả lỗi rõ về parent; batch không làm Tk crash. Client có thể khởi động process mới cho task/batch sau.
- App close gửi `shutdown`, chờ join có timeout; `terminate` chỉ là fallback cuối.
- Các lượt source/package UI thật đều xác nhận không còn parent/child process sau đóng app.

## 6. Accuracy và pipeline invariant

So sánh thread và subprocess trên cùng 72 ảnh:

- primary: 70;
- review: 2;
- unreadable: 2;
- detector calls: 72;
- crop OCR calls: 78;
- full-scene OCR calls: 0;
- Tesseract calls: 0;
- AI calls: 0;
- candidate trước/sau lọc: 74/70;
- digest output giống hệt.

Không có candidate explosion, không đổi formatter và không đổi PP-OCRv6 Small.

## 7. Actual UI source

So sánh apples-to-apples bằng UI automation ngoài process, chọn thư mục thật qua dialog và gửi heartbeat Win32:

| Metric | Packaged thread baseline | Source subprocess |
|---|---:|---:|
| FAST 72 ảnh | 119,293 s | 124,000 s |
| Chênh throughput | — | +3,95% |
| Ảnh/phút | 36,21 | 34,84 |
| Heartbeat median | 74,37 ms | 0,51 ms |
| Heartbeat p95 | 1.166,18 ms | 4,34 ms |
| Heartbeat p99 | 1.856,30 ms | 9,94 ms |
| Max stall | 2.100,60 ms | 15,45 ms |
| Block >100 / >250 / >500 ms | 110 / 85 / 82 | 0 / 0 / 0 |
| Peak process-tree RSS | 1.343,2 MB | 977,9 MB |

So với mốc 117,310 giây, source subprocess chậm 5,70%, vẫn dưới acceptance 10%. Screenshot source cuối xác nhận “Quét xong”.

Khi máy đã nóng sau nhiều lượt liên tục, cặp 10 ảnh source/package cho kết quả gần như bằng nhau: 35,053 s và 35,099 s, chênh 0,13%. Điều này loại giả thuyết frozen multiprocessing tự gây regression throughput.

## 8. File source và test thay đổi

- `check_vehicle_ocr/services/ocr_process.py`: protocol, child entrypoint và lifecycle client.
- `check_vehicle_ocr/app.py`: local/hybrid Paddle đi qua process; stop/close lifecycle.
- `check_vehicle_ocr/ocr_models.py`: đọc model selection mà không import Paddle vào UI.
- `check_vehicle_ocr/paddle_ocr_engine.py`: dùng model-selection helper chung.
- `main.py`, `check_vehicle_ocr/__main__.py`: Windows `freeze_support()`.
- `tests/ocr_process_worker_test.py`: startup/shutdown, init một lần, ordering, cancel, crash/restart, no orphan.
- `tests/ocr_process_app_integration_test.py`: app dùng path task/process và giữ output order/format.
- `tests/ocr_process_import_boundary_test.py`: UI import không nạp Paddle/PaddleOCR; entrypoint có freeze guard.
- `tests/ocr_process_heartbeat_test.py`: Tk heartbeat tiếp tục drain khi child đang xử lý.
- `tests/hybrid_pipeline_test.py`: hybrid local OCR cũng đi qua process, AI chỉ nhận kết quả thực sự cần review.
- `tests/performance_stability_test.py`, `tests/worker_manager_test.py`: cập nhật regression guard cho kiến trúc process và stop in-flight.

Harness A/B/C, JSON thô, screenshot benchmark và dataset chỉ nằm trong `audit-output` bị Git ignore; không đưa vào release package.

## 9. Lệnh kiểm tra đã chạy

- `python -s -B -m compileall -q check_vehicle_ocr tests tools main.py`: pass.
- 34/34 script không cần tham số (`32` file `*_test.py`, `performance_benchmark.py` và `performance_regression_profile.py`): pass trong `APPDATA` tạm; không dùng cấu hình thật.
- Test integration mới lặp 10/10: pass.
- PyInstaller analysis/EXE/COLLECT: pass sau khi đóng một EXE cũ do script inspect ban đầu giữ handle.
- Packaged `--runtime-health-check`: exit 0.
- Packaged `--self-test-paddle`: exit 0, log `PaddleOCR self-test OK`.
- Packaged UI control assertion: pass.
- Source actual UI 72 ảnh: pass, không orphan.
- Source/package actual UI 10 ảnh: output lifecycle pass, thời gian gần như bằng nhau.
- Inno Setup build và installer smoke cô lập: silent install, health check, packaged UI assertion và uninstall đều exit 0; file EXE đã cài có cùng SHA-256 với EXE nguồn và không còn sau uninstall.
- `git diff --check`: exit 0; chỉ có cảnh báo Git sẽ chuẩn hóa LF/CRLF theo cấu hình hiện hữu.
- Kiểm tra nghiêm ngặt 14 file text thay đổi: đều decode UTF-8, không có marker mojibake/HTML entity và không có trailing whitespace.

## 10. Trạng thái packaged 72 và installer

Lượt packaged cuối được chạy từ EXE PyInstaller đã build lại sau thay đổi cuối cùng:

| Metric | v1.9.2 thread baseline | Subprocess packaged cuối |
|---|---:|---:|
| FAST 72 ảnh | 119,293 s | 126,847 s |
| Ảnh/phút | 36,21 | 34,06 |
| Heartbeat median | 74,37 ms | 0,51 ms |
| Heartbeat p95 | 1.166,18 ms | 8,83 ms |
| Heartbeat p99 | 1.856,30 ms | 11,44 ms |
| Max stall | 2.100,60 ms | 17,31 ms |
| Block >100 / >250 / >500 ms | 110 / 85 / 82 | 0 / 0 / 0 |
| Peak process-tree RSS | 1.343,2 MB | 1.002,7 MB |

Packaged cuối chậm hơn 6,33% so với baseline cùng harness và 8,13% so với mốc tham chiếu 117,310 giây, nên vẫn nằm trong giới hạn 10%. Run hoàn tất 72/72 và danh sách process còn sống sau đóng app rỗng.

EXE cuối:

- File version và product version: `1.9.2.0`.
- SHA-256: `F366F2F96B2FE8EA5F45291AF34D6044DFF5EF2ED64F2FB8E75F1FEA4CEC33FD`.

Installer cô lập được build từ đúng EXE này. Silent install, health check, UI smoke và uninstall đều pass; không cần quyền Administrator. Chưa commit, push, tag hoặc tạo release mới theo đúng phạm vi milestone.

## 11. Giới hạn

- Dataset không có ground truth được công bố, nên không tuyên bố accuracy production; chỉ báo cáo output-equivalence, primary/review và call counts.
- Không gọi API/Telegram thật.
- Không benchmark GPU.
- Không đổi model, detector hoặc OCR algorithm.
