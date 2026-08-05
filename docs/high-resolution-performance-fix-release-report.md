# Báo cáo phát hành bản vá hiệu năng ảnh độ phân giải cao

## 1. Mục tiêu và phạm vi

Bản vá khôi phục tốc độ FAST/Cân bằng trên ảnh điện thoại độ phân giải cao mà vẫn giữ PP-OCRv6 Small, detector-first, one-plate-per-image, bộ lọc nhiễu, formatter, Excel safety, updater và các provider hiện có. Source lõi PaddleOCR không bị sửa.

Dataset acceptance là 72 ảnh cục bộ được cấp quyền, tổng 35.213.547 byte, toàn bộ 1920×2560. Dataset chỉ được đọc; ảnh, tên file, crop và trace chi tiết không được đưa vào Git hoặc release.

## 2. Patch được đưa vào main

Patch hiệu năng gốc ở worktree được commit thành `da7048a`, sau đó cherry-pick an toàn vào `main` thành `dbb7c0f`.

- `check_vehicle_ocr/image_io.py`: timing decode/EXIF tùy chọn.
- `check_vehicle_ocr/processor.py`: FAST/Cân bằng dùng ảnh làm việc có cạnh dài tối đa 1280; giữ kích thước gốc và ánh xạ bbox về tọa độ gốc; timing stage tùy chọn.
- `tests/performance_timing_instrumentation_test.py`: regression guard không phụ thuộc tốc độ máy.

THOROUGH không dùng giới hạn 1280. PP-OCRv6 Small tiếp tục là model mặc định.

Các profiler, JSON timing, crop, screenshot benchmark thô và báo cáo audit có tên ảnh thật chỉ được giữ ngoài Git. Dataset, cache, thư mục tạm và binary profiling không nằm trong commit/release.

## 3. Regression guard

Test mới khóa các invariant sau:

- FAST/Cân bằng luôn có cạnh dài ảnh làm việc không quá 1280.
- `ImageResult.width/height` vẫn là 1920×2560 trong fixture độ phân giải cao.
- bbox `(100, 200, 300, 100)` trên ảnh làm việc 960×1280 được trả về `(200, 400, 600, 200)` trên ảnh gốc.
- Crop detector thành công chỉ tạo một OCR call và không chạy full-scene.
- Raw OCR `59X112345` không đổi; output vẫn là `59X1-12345`.
- THOROUGH giữ nguyên kích thước/bbox đầu vào.

Guard đã được kiểm tra red/green: fail trên `origin/main` trước patch và pass sau patch.

## 4. Benchmark thực tế

### Số liệu điều tra đã kiểm chứng trước tích hợp

| Biến thể | Thời gian / 72 ảnh |
|---|---:|
| OLD executable | 271,422 s |
| NEW BEFORE FIX | 133,188 s |
| NEW AFTER FIX SOURCE | 122,957 s |
| NEW AFTER FIX PACKAGED | 122,617 s |
| BALANCED trước → sau | 189,032 s → 132,290 s |

### Chạy lại từ project main

| Metric | FAST source | BALANCED source | FAST packaged final |
|---|---:|---:|---:|
| Tổng ảnh | 72 | 72 | 72 |
| Tổng thời gian | 120,056 s | 129,513 s | 117,310 s |
| Ảnh/phút | 35,98 | 33,36 | 36,83 |
| Primary đọc được | 70 | 70 | UI hoàn tất 72/72 |
| Cần review | 3 | 3 | 3 |
| Không đọc được | 2 | 2 | Lỗi 0 trên UI |
| Detector calls | 72 | 72 | không expose qua EXE UI |
| Crop OCR calls | 78 | 78 | không expose qua EXE UI |
| Paddle predict calls | 82 | 85 | không expose qua EXE UI |
| Full-scene calls | 0 | 3 | không có dấu hiệu fallback bất thường |
| Candidate trước/sau lọc | 74/70 | 75/71 | không có candidate explosion trên UI |
| Tesseract / AI calls | 0 / 0 | 0 / 0 | 0 / 0 |
| Peak RSS | 536,5 MB | 564,3 MB | 1.349,9 MB cho toàn cây process đóng gói |

Dao động lần chạy cuối tốt hơn số tham chiếu 122–125 giây và không vượt ngưỡng +15%. FAST không chạy full-scene; BALANCED chỉ chạy ba fallback cho ảnh khó. Primary/review không regression so với lần đã kiểm chứng trong worktree.

## 5. UI responsiveness

Source hiện giới hạn progress event khoảng 6,7 lần/giây, upsert từng Treeview row, chỉ rebuild bảng ở đầu/cuối batch và không tự render preview cho mọi ảnh. UI smoke, scroll tests, packaged control assertion và screenshot harness đều pass.

Probe `WM_NULL` cho cửa sổ idle có p95 0,36 ms, không timeout. Khi PP-OCRv6 Small chạy CPU, p95 có thể chạm khoảng 1.012 ms và có các probe timeout 1 giây. Giảm worker decode từ 4 xuống 1 không cải thiện p95 hoặc throughput khi vẫn ép đúng Small; do đó bottleneck UI không phải preview/Treeview/progress queue mà là khoảng inference CPU/GIL của Paddle.

Patch này không đổi OCR sang Tiny, không tách inference sang process và không giảm throughput chỉ để làm animation mượt. Không thêm tùy chọn “Ưu tiên giao diện mượt khi quét” vì live preview không phải nguyên nhân. Process-isolated inference là hướng cần benchmark riêng sau này.

## 6. Version và build hygiene

- App/UI/runtime: `1.9.2`.
- EXE `FileVersion` và `ProductVersion`: `1.9.2.0`.
- Installer `ProductVersion`: `1.9.2`.
- Runtime: PaddleOCR 3.7.0, PaddlePaddle 3.3.1, PaddleX 3.7.2.
- Model: `PP-OCRv6_small_det` + `PP-OCRv6_small_rec`.
- Runtime manifest commit: `e6cb7529907af22a7eb7e7ffdd564510b39d65d1`.

PyInstaller và model-component builder chỉ bundle file runtime model (`config.json` nếu có, `inference.json`, `inference.pdiparams`, `inference.yml`). Portable/model ZIP cuối không chứa `.cache`, `.gitattributes`, README model, audit output hoặc dữ liệu người dùng.

## 7. Validation đã chạy

- `python -B -m compileall -q check_vehicle_ocr tests tools main.py`: pass.
- 28/28 test script không tham số: pass sau commit cuối.
- `tests/performance_benchmark.py`, performance profile và engine-pool benchmark synthetic: pass.
- FAST/BALANCED real-folder source từ main: pass.
- PyInstaller build, runtime health, Paddle self-test và packaged UI assertion: pass.
- UI smoke, theme/scroll tests, source screenshot harness và packaged screenshot harness: pass.
- FAST real-folder bằng EXE final: 117,310 s; UI hiển thị hoàn tất 72/72, review 3, lỗi 0.
- Tesseract component local: hash/version/OCR smoke pass.
- Inno Setup: build pass; smoke dùng AppId cô lập có install/health/uninstall exit 0 và không thay đổi bản cài v1.9.1 hiện hữu.
- Portable, installer, model component, update manifest và 10 dòng SHA256SUMS: pass.
- Updater đọc GitHub Release thật, chọn `CheckVehicleOCR-Setup-1.9.2.exe`, có SHA-256 và xác nhận v1.9.1 thấy v1.9.2 là bản mới.
- GitHub Actions run `31011009043`: `success`.
- Model/Tesseract component tải lại từ release public: hash pass; model có đúng 6 file runtime; Tesseract OCR smoke trả 5.5.3.

Synthetic benchmark cuối có median: import 2,580 s; UI init 0,083 s; Paddle cold init 1,794 s; ảnh đầu 3,628 s; ảnh warm 3,648 s; batch ba ảnh 10,869 s. Đây không phải accuracy production.

## 8. Release

- Commit/tag: `e6cb7529907af22a7eb7e7ffdd564510b39d65d1` / `v1.9.2`.
- Release public: <https://github.com/NovWyatt/checkparking/releases/tag/v1.9.2>.
- Workflow publish lúc 2026-08-05 20:49 (UTC+7), không phải draft hoặc prerelease.

SHA-256 public chính:

- Installer: `43c330f6bd9b6daa599433c795a06849461790319ca4ddda9d046cb085790717`.
- Portable: `a65e1009c9f80abd1aced227a973c0a26a970d2d37f9631dabd41648fced987b`.
- Tesseract component: `4d476ad25538d937faf17bd85e4426c58f3a5ce1dc08eae755591d49faee92e0`.
- PP-OCRv6 Small component: `cde97025a2d8f27875e66b01408711fa0c446684de60266c456cd82578ae7f75`.

Release có 11 asset public: installer, portable ZIP, Tesseract component/manifest/build lock, PP-OCRv6 Small component/model manifest, runtime versions, update manifest, versioned manifest và `SHA256SUMS.txt`.

## 9. File tạo/sửa trong milestone tích hợp

- Performance: `check_vehicle_ocr/image_io.py`, `check_vehicle_ocr/processor.py`, `tests/performance_timing_instrumentation_test.py`.
- Version/release: `check_vehicle_ocr/version.py`, `CHANGELOG.md`, `README.md`, `docs/release-notes-v1.9.2.md`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, các version/release tests và packaged UI assertion.
- Build hygiene: `CheckVehicleOCR.spec`, `build_exe.ps1`, `tools/write_build_metadata.py`, `tools/build_model_component.py`, `tests/release_system_test.py`.
- Báo cáo: `docs/high-resolution-performance-fix-release-report.md`.

## 10. Phần chưa benchmark hoặc còn hạn chế

- Không benchmark lại THOROUGH trên toàn bộ 72 ảnh; regression test xác nhận behavior resize không đổi.
- Không gọi API/Telegram thật và không benchmark hybrid provider latency.
- Không benchmark GPU.
- Không có ground-truth production để công bố accuracy; chỉ báo cáo primary/review/unreadable trên dataset nội bộ được cấp quyền.
- Không tải lại installer/portable public hàng trăm MB để re-hash tại máy này; GitHub workflow, asset metadata và SHA256SUMS public đã pass. Hai component model/Tesseract đã được tải lại và kiểm hash/smoke thực tế.
- UI còn có nhịp stall trong inference PP-OCRv6 Small; cần milestone process-isolation riêng nếu muốn loại bỏ mà không giảm throughput/model quality.
