# Báo cáo hoàn thiện release, cập nhật và runtime

## 1. Phạm vi và Git

- Repository làm việc: `C:\Users\Wyatt\Desktop\checkvhc-main`.
- Remote: `origin https://github.com/NovWyatt/checkparking.git`.
- Repository public, nhánh mặc định `main`; lúc bắt đầu chưa có tag hoặc GitHub Release.
- GitHub CLI chưa được cài trên máy. Quyền push/release sẽ được xác minh bằng Git và GitHub API sau khi commit/tag.
- Không đọc, sửa hoặc build hai thư mục ngoài phạm vi đã bị cấm.

## 2. Phiên bản và dependency

- Nguồn version duy nhất: `check_vehicle_ocr/version.py`, phát hành đầu tiên theo quy trình mới là **1.7.0**.
- Đây là quyết định quản trị version mới, không khẳng định lịch sử các version cũ.
- Build metadata sinh ngay trước PyInstaller gồm build date, commit SHA và `owner/repository`; tệp sinh này bị ignore.
- `.venv\Scripts\python.exe -s` với `PYTHONNOUSERSITE=1` đã import thành công PaddleOCR 3.5.0, PaddlePaddle 3.3.1 và PaddleX 3.5.2; không dùng user site.
- `requirements.txt`, `requirements-dev.txt`, `requirements-build.txt` và `pyproject.toml` đã được chuẩn hóa. Inno Setup 6.7.3 được cài từ winget để tạo installer.

## 3. Build Windows và assets

- PyInstaller tạo `release\CheckVehicleOCR\CheckVehicleOCR.exe`.
- Inno Setup tạo `CheckVehicleOCR-1.7.0-windows-x64-setup.exe`.
- `build_release_assets.ps1` tạo portable ZIP, installer, manifest và `SHA256SUMS.txt`; asset local được giữ ngoài Git.
- SHA-256 của lần build cuối:
  - setup: `a015a7c994520cbbf19b0f4c811e8d5a1c6d3c109410179250d937bfbad83bce`
  - portable ZIP: `46388aea3631544dba9dde3f93738183779025aed578dea4503982b33b5de751`
- Bản build local dùng metadata của commit trước khi commit release; chỉ dùng để smoke. GitHub Actions sẽ rebuild assets từ đúng commit/tag trước khi upload release.

## 4. GitHub Actions và GitHub Releases

- `.github/workflows/ci.yml` tạo `.venv` cô lập, compile và chạy bộ test deterministic không dùng API/Telegram thật.
- `.github/workflows/release.yml` chạy khi push tag `v*`, build Windows, kiểm tra release-system, tạo setup/portable/manifest/SHA256 và upload bằng `softprops/action-gh-release`.
- Update Center dùng GitHub Releases của metadata build làm nguồn mặc định. Nó chuẩn hóa `owner/repository`, bỏ source archive, chọn asset Windows của dự án và yêu cầu SHA-256 từ GitHub digest hoặc `SHA256SUMS.txt`.
- Repository public không cần token. Repository private hỗ trợ token tùy chọn trong Chi tiết kỹ thuật; token được DPAPI bảo vệ khi có Windows và không được log, export hoặc đưa vào URL.

## 5. App updater, cài đặt và rollback

- Download chỉ lưu package sau khi SHA-256 khớp; không ghi đè package đã tải trước đó.
- Nút **Cài khi đóng app** chỉ có ở executable đã đóng gói. Nó ghi pending state atomically rồi gọi helper PowerShell riêng.
- Helper chờ process GUI kết thúc, backup thư mục cài đặt, chạy installer đã xác minh, chạy `--runtime-health-check`, rồi mới mở UI mới.
- Installer/health fail sẽ phục hồi backup và chạy executable cũ. Startup có recovery cho trường hợp mất điện khi backup còn nhưng thư mục cài đặt chưa tồn tại.
- `tests/release_system_test.py` kiểm tra pending/helper/recovery bằng fixture. Installer smoke thật đã cài vào một thư mục duy nhất dưới `audit-output`, chạy health check, rồi gỡ bằng `unins000.exe` thành công.
- Auto-install không được chạy âm thầm và source runtime từ `python main.py` luôn từ chối tự thay executable.

## 6. PaddleOCR runtime staging

- Runtime thử nghiệm nằm ở `.runtime\staging\paddleocr-<version>\venv`, không thay `.venv` chính.
- Staging thật PaddleOCR 3.6.0 với PaddlePaddle 3.3.1 đã qua import, OCR synthetic, normalization, Excel smoke và benchmark; sau đó đã activate/health-check/rollback về base runtime thành công.
- Staging không tự activate chỉ vì version mới hơn. Runtime lỗi luôn fallback sang runtime base.
- Benchmark pool mới: shared một engine đạt **77.42 ảnh/phút**, hai engine độc lập **76.65 ảnh/phút** và dùng 404.63 MB so với 348.09 MB; hai process 65.84 ảnh/phút và 735.46 MB. Batch 30 không chạy vì RAM khả dụng 1,835 MB dưới guard 6 GB. Kết luận giữ một inference worker PaddleOCR local.

## 7. Model OCR

- `models/manifest.json` có schema do project kiểm soát, nhưng hiện là `local-unverified`: chưa có URL/checksum giả và auto-download bị tắt.
- `ModelRuntimeManager` stage model versioned ở profile người dùng, xác minh cấu trúc detection/recognition, chạy OCR synthetic bằng đúng hai thư mục model, rồi mới cho activate.
- Registry active/previous được ghi atomically; có activate, rollback và fallback cache/model cũ nếu model selected không init được.
- Chưa có model release được kiểm soát kèm license và SHA-256 nên chưa kiểm chứng staging model thật. UI hiển thị trạng thái trung tính thay vì giả vờ có cập nhật.

## 8. Tesseract, Telegram và AI provider

- Tesseract là fallback tùy chọn: chọn `tesseract.exe`, thư mục portable, ZIP local có manifest/checksum, hoặc package verified nếu project cấu hình manifest. Không tải installer ngẫu nhiên.
- Telegram chỉ gửi khi người vận hành bấm test hoặc chạy batch đã bật thông báo. Queue, timeout, retry, masking và thông báo lỗi không lộ token đã được test bằng mock; không gửi Telegram thật.
- Custom OpenAI-compatible provider giữ Base URL, manual model, Responses/Chat Completions/Auto, cache capability, timeout, retry/429 và redaction. Test dùng mock, không gọi API có phí.

## 9. UI và screenshot

- Bốn card Update Center giữ action ngắn: Ứng dụng, PaddleOCR, Model OCR và Tesseract.
- Screenshot source/control states đã tạo lại tại `docs/ui-review/`.
- Screenshot từ executable thật, dùng `PrintWindow` theo HWND để không lẫn cửa sổ khác, tại `docs/ui-review/release/`:
  - `packaged-light-scan.png`, `packaged-dark-scan.png`
  - `packaged-light-updates.png`, `packaged-dark-updates.png`
- Các ảnh Light/Dark cho thấy text readonly/disabled, combobox và Update Center vẫn đọc được.

## 10. Benchmark và kiểm thử

Đã chạy thành công bằng `.venv\Scripts\python.exe -s -B` với `PYTHONNOUSERSITE=1`:

- `compileall` cho source, tests, tools và `main.py`.
- 18 script test: dataset, stability, progress, provider API/integration, release system, services, smoke, Telegram, Tesseract, contrast, UI, updater local/UI và worker manager.
- `tests/performance_regression_profile.py`.
- `tests/performance_benchmark.py`: median import 2.472s, UI init 0.390s, cold init 1.489s, first image 0.862s, warm image 0.777s, batch 3 ảnh 2.401s, Excel compact 0.093s, full 0.193s.
- `tests/paddle_engine_pool_benchmark.py`.
- Packaged `--runtime-health-check`, packaged `--self-test-paddle`, screenshot harness và installer smoke/gỡ installer.
- YAML workflow parse bằng Python thành công.

Paddle có cảnh báo không có `ccache` và Windows in một dòng `Could not find files for the given pattern(s)`; cả hai không làm fail test, build hay smoke.

## 11. License, tài liệu và file chính

- Thêm `LICENSE` (MIT cho code project), `THIRD_PARTY_NOTICES.md`, `SECURITY.md`, `CHANGELOG.md` và `docs/LICENSE_REVIEW.md`. Đây không phải ý kiến pháp lý.
- Không bundle Tesseract/model bên thứ ba không có nguồn, checksum và điều khoản phân phối rõ ràng.
- Tài liệu mới/cập nhật gồm build, release, updater, Paddle runtime staging, model, Tesseract, Telegram, AI provider và dataset template.
- File implementation trọng tâm: `updater.py`, `runtime_manager.py`, `model_registry.py`, `paddle_ocr_engine.py`, `app.py`, `config.py`, scripts build/release, installer và workflows.

## 12. Những phần chưa thể khẳng định hoàn thành

- Chưa có GitHub Release thật tại thời điểm viết phần báo cáo này; trạng thái push/tag/workflow/release sẽ được bổ sung sau khi Git remote xác nhận quyền.
- Chưa có nguồn model OCR production đã ký/checksum nên staging model thật chưa chạy.
- Không kiểm thử Telegram, custom provider hay update download với credential/dịch vụ thật.
- Build workflow có thể bị giới hạn bởi thời gian/tài nguyên runner GitHub do PaddleOCR; release chỉ được xác nhận sau khi workflow của tag kết thúc.
