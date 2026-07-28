# Báo cáo sửa Update Center và khả năng đọc control

## Mục tiêu

Khắc phục nguồn cập nhật test còn sót lại, hành vi nút cập nhật, màu của control Tkinter và đơn giản hóa Update Center mà không thay đổi PaddleOCR/PaddlePaddle đang hoạt động.

## Nguồn `file:///mock`

Code hiện tại chỉ còn nhắc đến `file:///mock` và `file:///mock-manifest.json` trong:

- `check_vehicle_ocr/config.py`: danh sách sentinel lịch sử `_TEST_UPDATE_SENTINELS`.
- `tests/update_actions_control_test.py`: regression test.

Ghi chú trong `config.py` cho thấy các sentinel này từng được dùng bởi UI test/screenshot test sớm. Báo cáo này không đọc profile APPDATA thật của người vận hành, vì vậy không khẳng định được thời điểm cụ thể URL đó đã được ghi vào profile thật.

Đã áp dụng ba lớp bảo vệ:

1. Migration v14 xóa đúng hai sentinel và đổi `source_mode=manifest` thành `disabled` chỉ trong trường hợp sentinel bị xóa.
2. `CheckVehicleApp._has_configured_update_source()` từ chối sentinel ở runtime, nên không tạo request hay hiển thị WinError.
3. `_save_settings()` không thể ghi lại sentinel. URL local hợp lệ khác, ví dụ `file:///D:/operator/release.json`, vẫn được giữ nguyên.

Khi chưa có nguồn hợp lệ, UI hiển thị: **“Chưa cấu hình nguồn cập nhật ứng dụng.”**. Exception kỹ thuật được rút gọn trước khi lên UI; log chỉ lưu type lỗi.

`tools/capture_ui_review.py` và `tools/capture_control_states.py` nay cô lập `APPDATA`, `TEMP` và `TMP` trước khi tạo app, rồi phục hồi môi trường sau khi xong. Regression test xác nhận UI/harness không sửa settings production.

## Control và tương phản

Nguyên nhân text disabled khó đọc đã xác nhận là `_theme_colors()` trong `check_vehicle_ocr/app.py` ghi đè semantic token `disabled_text` bằng `text_muted`. Bản vá giữ lại `disabled_text` riêng của Light/Dark token.

`check_vehicle_ocr/ui/theme.py` bổ sung style `Operator.TCombobox` với các map riêng cho normal, readonly, disabled và focus; bao gồm `foreground`, `background`, `fieldbackground`, `selectforeground`, `selectbackground`, `arrowcolor` và `bordercolor`. Pop-down Listbox được đặt màu ngay trước khi mở.

- Hiệu năng dùng `readonly`, không dùng `disabled`, nên luôn chọn được **Tự động**, **Tiết kiệm RAM**, **Ưu tiên tốc độ**.
- Local PaddleOCR inference giữ một worker bằng logic nội bộ; phần Nâng cao hiển thị status pill “1 worker cố định để ổn định” thay vì Spinbox bị khóa.
- Combobox ở Result và form dùng style explicit; style mặc định vẫn được cấu hình để các control cũ không mất tương phản.
- `CheckVehicleApp.destroy()` và `_save_settings()` xử lý callback Tk còn chờ, tránh warning Tcl khi đổi theme rồi đóng ngay.

Đã tạo và kiểm tra trực quan ảnh widget thật:

- `docs/ui-review/control-states-light.png`
- `docs/ui-review/control-states-dark.png`
- `docs/ui-review/scan-combobox-light.png`
- `docs/ui-review/scan-combobox-dark.png`

Các ảnh thể hiện combobox đóng/mở, normal, readonly, disabled, focus và item selected. `light-scan.png` cũng được cập nhật; Scan page sẽ xếp dọc hai bước cấu hình khi logical width dưới 980 px để giảm cắt text ở Windows scaling cao.

## Update Center

Tab Cập nhật chỉ giữ header **Cập nhật** với nút **Kiểm tra tất cả** và bốn card:

1. Ứng dụng Check Vehicle OCR.
2. PaddleOCR.
3. Model OCR.
4. Tesseract dự phòng.

Mỗi card chỉ có một hành động chính thay đổi theo trạng thái, cùng link **Chi tiết**. URL, manifest, checksum, release notes và cấu hình staging nằm trong vùng **Chi tiết kỹ thuật** đóng mặc định.

### Ứng dụng

- Hỗ trợ GitHub Releases (`owner/repository` hoặc GitHub repo URL) và manifest tùy chỉnh.
- GitHub release chỉ chọn asset Windows do project phát hành có digest SHA-256; source archive GitHub không bao giờ được coi là installer.
- Action lần lượt là **Thiết lập nguồn** → **Kiểm tra** → **Tải bản cập nhật** → **Cài khi đóng app**.
- Download chạy nền vào file tạm, xác minh SHA-256 rồi mới đặt tên versioned; file cũ không bị ghi đè.
- “Cài khi đóng app” hiện chỉ hướng dẫn cài thủ công sau khi app đóng. Nó không chạy installer và không tuyên bố cập nhật đã hoàn tất.

### PaddleOCR

- Kiểm tra release từ PyPI configured source ở nền.
- Chỉ stage version cụ thể trong `.runtime/staging/paddleocr-<version>/venv`; không sửa interpreter/runtime đang chạy.
- Staging plan tạo venv, cài package pinned, import check, OCR synthetic, normalization, Excel smoke và benchmark synthetic.
- Runtime registry ghi atomic; `main.py` ưu tiên staged runtime đã accept và fallback runtime cũ nếu child không khởi động. Test fake-runner đã xác nhận pass/fail, activation và rollback registry.
- Người dùng có thể nhập version thử nghiệm cụ thể trong Chi tiết kỹ thuật. Không dùng branch `main`.

### Model OCR

Card chính chỉ tóm tắt detection/recognition model active. Dialog Quản lý model chỉ stage model khi manifest có SHA-256; không ghi đè model cũ. Kích hoạt/rollback model staged chưa được bật vì pipeline hiện chưa có acceptance smoke/benchmark và registry model versioned đủ an toàn. Do đó app không giả vờ đã “cập nhật model”.

### Tesseract

Tesseract là fallback tùy chọn. Dialog cho phép chọn `tesseract.exe`, thư mục portable (`tesseract.exe`, `bin/tesseract.exe` hoặc `portable/tesseract.exe`), hoặc ZIP local đã kiểm checksum theo manifest dự án. Nếu có manifest verified, tải/extract vào thư mục versioned `.runtime/tesseract-staging` mà không ghi đè bản cũ. Lần chọn mới giữ đường dẫn trước để **Quay lại bản trước**. Không có auto-download installer ngẫu nhiên hoặc auto-install từ GitHub.

## Benchmark và quyết định engine pool

Benchmark synthetic cuối (`tests/performance_benchmark.py`, median ba lượt):

| Hạng mục | Baseline trong `PERFORMANCE_CURRENT.md` | Hiện tại |
|---|---:|---:|
| Paddle cold init | 1,350s | 1,495s |
| Ảnh đầu | 0,685s | 0,774s |
| Ảnh warm | 0,640s | 0,719s |
| Batch 3 ảnh | 1,877s | 2,172s |
| Excel compact | 0,081s | 0,093s |
| Excel full | 0,156s | 0,180s |
| Import app | 2,549s | 2,848s |
| Khởi tạo UI | 0,073s | 0,418s |

Ảnh benchmark là synthetic 900×520, một biển rõ, model đã cache; không đại diện accuracy/throughput production. OCR benchmark hiện khởi tạo engine một lần/process và dùng 5 scene call, 0 ROI/fallback cho first/warm/batch.

`cProfile` ghi trong `audit-output/performance-regression-profile-final.json` cho thấy startup UI chủ yếu ở `_build_ui`/`ApplicationShell._build_sidebar` và 296 Tk calls (~0,34s). Các page khác vẫn lazy; lúc startup chỉ có Scan page. Regression UI/performance so với tài liệu baseline vẫn còn và không bị che giấu trong milestone này.

Engine-pool benchmark batch 10 (`audit-output/paddle-engine-pool-benchmark-final.json`):

| Cách chạy | Ảnh/phút | RAM peak | Kết quả |
|---|---:|---:|---|
| Một engine shared | 84,03 | 357,65 MB | Baseline |
| Hai engine độc lập | 86,33 | 463,95 MB | Giống baseline |
| Hai process | 61,56 | 713,01 MB | Giống baseline |

Hai engine chỉ nhanh khoảng 2,7% nhưng tăng RAM khoảng 29,7%; hai process chậm hơn và gần gấp đôi RAM. RAM khả dụng trước benchmark ~2,53 GB nên batch 30 được bỏ qua. Kết luận: giữ local inference = 1 là lựa chọn an toàn mặc định.

## Tệp thay đổi/chụp mới

- `check_vehicle_ocr/app.py`
- `check_vehicle_ocr/config.py`
- `check_vehicle_ocr/ui/theme.py`
- `check_vehicle_ocr/ui/components/forms.py`
- `check_vehicle_ocr/ui/pages/scan_page.py`
- `check_vehicle_ocr/ui/pages/settings_page.py`
- `check_vehicle_ocr/ui/pages/results_page.py`
- `check_vehicle_ocr/update_center.py`
- `requirements.txt`
- `tests/services_test.py`
- `tests/update_actions_control_test.py`
- `tests/updater_ui_state_test.py`
- `tools/capture_control_states.py`
- `tools/capture_ui_review.py`
- `docs/ui-review/*.png` (ảnh review thật cập nhật)
- `audit-output/performance-regression-profile-final.json`
- `audit-output/paddle-engine-pool-benchmark-final.json`

## Dependency

`requirements.txt` nay khai báo `packaging>=23.2`, dependency cần cho `paddlex` import. Lệnh `python -m pip install "packaging>=23.2"` chạy thành công nhưng không tải/nâng gì: `packaging 26.2` đã có trong user site. PaddleOCR/PaddlePaddle không bị cài lại hoặc nâng cấp.

## Kiểm tra đã chạy

- `python -B -m compileall -q check_vehicle_ocr tests tools main.py` — pass.
- 17 script test chức năng/UI/service — pass: dataset, stability, progress, provider API/integration, services, smoke, Telegram, Tesseract optional, theme, UI, Update Center, updater local/UI, worker manager.
- `python -B tests/performance_regression_profile.py --output audit-output/performance-regression-profile-final.json` — pass.
- `python -B tests/performance_benchmark.py` — pass, ba lượt.
- `python -B tests/paddle_engine_pool_benchmark.py --output audit-output/paddle-engine-pool-benchmark-final.json` — pass; batch 30 được bỏ qua theo guard RAM.
- `python -B tools/capture_control_states.py` và `python -B tools/capture_ui_review.py` — pass.

Một lần chạy suite ban đầu đặt `CHECK_VEHICLE_DISABLE_ONNX_DETECTOR=1` cho tất cả test nên `smoke_test.py` fail đúng tại assertion adapter ONNX. Chạy lại không có biến benchmark đó đã pass; đây không phải lỗi source.

## Phần chưa hoàn thành/rủi ro

- Chưa có GitHub repository, custom manifest, model manifest hoặc Tesseract package manifest production do người dùng cấu hình. Các luồng network thật vì thế chưa được kiểm chứng với release của dự án.
- Cài đặt application vẫn là thao tác thủ công sau download verified; không có auto-replace executable.
- Model staged chưa activate/rollback do chưa có acceptance flow model versioned đủ an toàn.
- UI startup và synthetic OCR/Excel hiện chậm hơn `PERFORMANCE_CURRENT.md`; cần một milestone performance riêng, không nên kết luận production-ready.
- Không thử Telegram thật, update server thật hoặc dataset ảnh thật.

Không dùng Git, không commit, không push. Không đọc hoặc sửa `C:\Users\Wyatt\Desktop\checkvhc` hay `C:\Users\Wyatt\Desktop\PaddleOCR`.
