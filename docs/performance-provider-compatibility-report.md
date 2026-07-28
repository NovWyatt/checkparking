# Báo cáo performance regression và provider compatibility

## Phạm vi

Milestone này không thêm database/camera/tracking hay thay model. Công việc tập trung vào profile hồi quy sau UI, lazy-load, giảm overhead progress, benchmark an toàn Paddle engine pool, compatibility OpenAI Responses/Chat Completions, updater local và tool benchmark ảnh local.

## Nguyên nhân hồi quy đã xác nhận

`cProfile` trước tối ưu cho thấy startup eager tạo tất cả tám page: 22,492 calls/0.443s, trong đó `ApplicationShell._build_pages()` và widget `ttk`/`_tkinter.tkapp.call` chiếm 0.367s cumulative. `BatchProgress.snapshot()` gọi `dataclasses.asdict`, gây recursive deepcopy: 0.089s cho 1,000 snapshot.

Không có bằng chứng UI/progress là nguyên nhân chính của OCR chậm: call tree `process_image` cho synthetic cho thấy `paddle.base.libpaddle.run` chiếm 1.866s/1.935s. Excel compact chủ yếu ở `Workbook.save`/zip/file I/O (0.130s/0.162s). Chi tiết call tree và so sánh baseline ở [PERFORMANCE_REGRESSION_ANALYSIS.md](PERFORMANCE_REGRESSION_ANALYSIS.md).

## Tối ưu đã áp dụng

- Shell chỉ tạo Scan page khi startup; bảy page còn lại tạo khi điều hướng lần đầu và cache lại.
- Provider, Telegram, Updater không tạo network client/worker lúc startup.
- Snapshot progress không còn dùng `asdict/deepcopy`; chỉ copy list/dict cần thiết.
- Event `progress` lúc bắt đầu task bị throttle 150ms; event kết quả mỗi ảnh vẫn có snapshot chính xác. UI render đã throttle 120ms và chỉ upsert row thay đổi.
- Không bỏ atomic Excel save, formula injection guard, engine reuse, review hoặc warning để làm số benchmark đẹp hơn.

## Benchmark trước/sau

| Hạng mục | Baseline trước UI | Sau UI trước tối ưu | Hiện tại | Ghi chú |
|---|---:|---:|---:|---|
| Import app median | 2.549s | 2.693s | 2.553s | Import dependency vẫn là chi phí lớn. |
| UI init median | 0.073s | 0.449s | 0.418s | Lazy-load cải thiện khoảng 6.9% so với UI eager. |
| Paddle cold init | 1.350s | 1.488s | 1.475s | Dao động cache/runtime. |
| First image | 0.685s | 0.889s | 0.892s | Tương đương UI eager trong nhiễu giữa các process; chưa về baseline. |
| Warm image | 0.640s | 0.779s | 0.813s | Native Paddle chi phối. |
| Batch 3 ảnh | 1.877s | 2.365s | 2.401s | Chưa về baseline; chịu ảnh hưởng runtime/cache. |
| Excel compact | 0.081s | 0.104s | 0.096s | I/O/zip chi phối. |
| Excel full | 0.156s | 0.205s | 0.199s | I/O/thumbnail chi phối. |

Benchmark hiện tại chạy 3 process bằng `python -B tests\performance_benchmark.py`. Đây vẫn là synthetic benchmark, không phải accuracy hay throughput production.

## UI startup và lazy page

Profile hiện tại: shell + Scan page 0.441s, chỉ có `['scan']` trong cache lúc startup. Page tạo ở lần điều hướng đầu: Session 11.6ms, Review 11.5ms, Export 3.6ms, Providers 8.1ms, Telegram 6.9ms, Updates 4.1ms, Settings 3.0ms. UI smoke xác nhận cache, router, theme và scale 125%/150% không lỗi.

## PaddleOCR local engine pool

Lệnh thực tế:

```powershell
python -B tests\paddle_engine_pool_benchmark.py --output audit-output\paddle-engine-pool-benchmark.json
```

Mỗi scenario shared/two-engine chạy process độc lập để cold init không bị scenario trước làm ấm. Batch 30 bị bỏ qua vì RAM khả dụng trước test là 5,055MB, dưới ngưỡng an toàn 6GB.

| Batch 10 synthetic | Shared 1 engine | 2 engine độc lập | 2 process |
|---|---:|---:|---:|
| Cold init | 1.554s | 1.982s | 1.808s (max child) |
| Batch | 7.966s | 7.777s | 9.600s |
| Ảnh/phút | 75.32 | 77.15 | 62.50 |
| Peak working set | 355.7MB | 410.5MB | 819.7MB (tổng child peak) |
| Lỗi | 0 | 0 | 0 |
| Kết quả so baseline | baseline | giống | giống |

Hai engine chỉ nhanh hơn khoảng 2.4% trong một lượt, trong khi tăng RAM khoảng 15.4%; hai process chậm hơn và dùng RAM lớn. Kết luận: **giữ `PaddleOCR Local` một inference worker mặc định**. Không thêm experimental pool, không cho nhập local OCR worker vô hiệu: UI khóa giá trị 1 và giải thích lý do; image preprocessing vẫn chạy song song.

## OpenAI-compatible API mode

Provider custom hiện lưu `api_mode`: `auto`, `responses`, `chat_completions`, cùng capability cache mode thành công gần nhất.

- `responses`: giữ payload Responses API hiện có và JSON schema fallback không schema.
- `chat_completions`: gửi `messages` với `image_url` data URL, parse content JSON về interface `ImageResult`/`PlateCandidate` hiện có.
- `auto`: ưu tiên cache, nếu endpoint hiện tại trả 404/405 unsupported thì thử endpoint còn lại đúng một controlled fallback. Không fallback khi 401/403; không retry endpoint/model vô hạn khi cả hai endpoint unsupported.

`tests/provider_api_mode_test.py` mock xác nhận: responses-only, chat-only, cached mode server hỗ trợ cả hai, `/models` thành công nhưng inference endpoint unsupported, 401 không fallback, manual model, data URL và secret redaction. 401/403, 404/405, 429 và timeout có reason tiếng Việt phù hợp ở `ImageResult`.

## Telegram

`Gửi tin thử` chỉ chạy sau thao tác chủ động, dùng `AsyncTelegramNotifier` worker nền, timeout ngắn, retry giới hạn và status inline; token không ghi log. Không có Telegram thật trong test tự động. Checklist vận hành thủ công ở [TELEGRAM_MANUAL_CHECKLIST.md](TELEGRAM_MANUAL_CHECKLIST.md).

## Updater local end-to-end

`tests/updater_local_e2e_test.py` chạy HTTP server `127.0.0.1` local và kiểm tra manifest hợp lệ, version mới/bằng/cũ, checksum đúng/sai, download interrupted, cleanup temp và package cũ không bị ghi đè. `download_verified()` stream vào temp cùng thư mục, hash khi tải và chọn tên checksum suffix nếu package version cũ khác checksum đã tồn tại.

App vẫn chỉ check/download/verify; không chạy installer hoặc tự thay executable.

## Benchmark ảnh local/ảnh thật

Đã tạo `tools\benchmark_dataset.py` và [REAL_IMAGE_BENCHMARK.md](REAL_IMAGE_BENCHMARK.md). Tool hỗ trợ manifest relative `image`/`expected_plate`, FAST/BALANCED/THOROUGH, exact match, character accuracy, unreadable, review, false positive, time và ảnh/phút.

Chưa có folder ảnh thật/manifest được cung cấp trong milestone này. Tool chỉ được kiểm thử parser/metric bằng fixture local; **không có số liệu accuracy thực tế được tuyên bố**.

## Test và kiểm chứng

Pass trong lần kiểm tra cuối: 13 script test xác định, một syntax check và bốn lệnh benchmark/profile/screenshot. Hai harness console (`paddle_engine_pool_benchmark.py`, `capture_ui_review.py`) đã được chỉnh để chỉ in ASCII khi host PowerShell dùng code page cp1252; JSON lưu trên đĩa và giao diện vẫn dùng UTF-8. Nhờ vậy harness không còn báo lỗi giả sau khi công việc thực tế đã hoàn tất.

```text
python -B -m compileall -q check_vehicle_ocr tests tools
python -B tests\smoke_test.py
python -B tests\performance_stability_test.py
python -B tests\services_test.py
python -B tests\worker_manager_test.py
python -B tests\progress_state_test.py
python -B tests\provider_integration_test.py
python -B tests\provider_api_mode_test.py
python -B tests\telegram_integration_test.py
python -B tests\updater_ui_state_test.py
python -B tests\updater_local_e2e_test.py
python -B tests\dataset_benchmark_test.py
python -B tests\ui_smoke_test.py
python -B tests\performance_benchmark.py
python -B tests\performance_regression_profile.py --output audit-output\performance-regression-profile.json
python -B tests\paddle_engine_pool_benchmark.py --output audit-output\paddle-engine-pool-benchmark.json
python -B tools\capture_ui_review.py
```

Warning còn lại: PaddlePaddle báo không có `ccache`; không làm test fail. Không gọi API/Telegram thật, không sửa PaddleOCR source/model, không thêm dependency, database, camera, Git, commit hoặc push.

## Tệp tạo và sửa trong milestone

- Sửa: `check_vehicle_ocr/ui/shell.py`, `check_vehicle_ocr/app.py`, `check_vehicle_ocr/services/progress_service.py` để lazy-load page, giữ page cache và giảm overhead snapshot/event.
- Sửa: `check_vehicle_ocr/gpt_vision.py`, `check_vehicle_ocr/providers.py`, `check_vehicle_ocr/ui/pages/providers_page.py` để hỗ trợ `auto`, `responses` và `chat_completions` với controlled fallback.
- Sửa: `check_vehicle_ocr/updater.py` để tải stream vào file tạm, kiểm SHA-256 và không ghi đè package cũ.
- Tạo: `check_vehicle_ocr/dataset_benchmark.py`, `tools/benchmark_dataset.py`, `tests/performance_regression_profile.py`, `tests/paddle_engine_pool_benchmark.py`, `tests/provider_api_mode_test.py`, `tests/updater_local_e2e_test.py`, `tests/dataset_benchmark_test.py`.
- Sửa: `tools/capture_ui_review.py` để capture 1366×768 và kết thúc an toàn trên console Windows legacy.
- Tạo/cập nhật tài liệu và artefact: `docs/PERFORMANCE_REGRESSION_ANALYSIS.md`, `docs/REAL_IMAGE_BENCHMARK.md`, `docs/TELEGRAM_MANUAL_CHECKLIST.md`, thư mục `docs/ui-review/`, `audit-output/performance-regression-profile.json`, `audit-output/paddle-engine-pool-benchmark.json` và báo cáo này.

Không cài, gỡ hoặc nâng dependency trong milestone này.

## Phần chưa kiểm chứng thực tế

- Telegram với token/Chat ID thật: cần checklist thủ công.
- Provider custom với server thật: cần kiểm tra capability, Responses/Chat behavior và quota thật.
- Updater với package release thật/installer: intentionally chưa triển khai install.
- Batch 30 engine pool: bỏ qua vì RAM khả dụng không đủ theo guard an toàn.
- Accuracy/speed ảnh camera thật: chờ folder ảnh local có manifest.
