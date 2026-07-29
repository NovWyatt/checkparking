# Phát hành component Tesseract dự phòng

Component Windows x64 v1.9.0 là Tesseract **5.5.3**, build Release từ source
tag chính thức `5.5.3` tại commit
`db0ec62f81b0737fbbe184d8fea40af5738f8eef`. Workflow
`.github/workflows/build-tesseract-component.yml` dùng MSYS2 UCRT64, CMake,
Ninja và dependency đã liệt kê/pin trong `tools/tesseract-build-lock.json`.
Không tải installer Windows bên thứ ba.

`tessdata_fast` được pin tag `4.1.0`, commit
`65727574dfcd264acbb0c3e07860e4e9e9b22185`; package chỉ chứa `eng` và `osd`.
Archive phải có `tesseract/bin/tesseract.exe`, DLL runtime cần thiết,
`tesseract/tessdata`, license/notices, `component-manifest.json`, `SBOM.json`
và `SHA256SUMS.txt`.

Trước khi upload, workflow và kiểm tra local bắt buộc xác minh tag/commit,
`tesseract --version`, `--list-langs`, OCR fixture, archive SHA-256 và hash/kích
thước từng file runtime. Manifest ngoài archive
`tesseract-component-manifest.json` là nguồn archive SHA-256: manifest bên
trong không tự hash được archive đang chứa nó. Ứng dụng chỉ chấp nhận HTTPS
asset của GitHub Release `NovWyatt/checkparking`, giới hạn dung lượng/số file,
chống Zip Slip và staging nguyên tử trước khi kích hoạt/rollback.
