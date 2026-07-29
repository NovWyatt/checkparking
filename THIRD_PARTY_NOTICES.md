# Third-party notices

Check Vehicle OCR is distributed under the MIT license for this repository's
own code. Third-party components keep their own licenses and notices.

| Component | Typical license/source | Distribution note |
|---|---|---|
| PaddleOCR / PaddlePaddle | Apache-2.0; PaddlePaddle project | Included only through Python runtime dependencies. |
| OpenCV | Apache-2.0 | Python wheel dependency. |
| openpyxl | MIT | Python wheel dependency. |
| OpenAI Python SDK | Apache-2.0 | Optional online-provider dependency. |
| ONNX Runtime | MIT | Optional detector dependency. |
| PyInstaller | GPL-2.0-or-later with bootloader exception | Used to create release executable. |
| Inno Setup | See Inno Setup license | Used by release workflow to create installer. |
| Tesseract 5.5.3 | Apache-2.0; source tag `5.5.3` from tesseract-ocr/tesseract | Optional project-built Windows x64 component; its ZIP contains source/license notices and per-file hashes. |
| tessdata_fast 4.1.0 (`eng`, `osd`) | Apache-2.0; tesseract-ocr/tessdata_fast | Bundled only in the optional Tesseract component, pinned to commit `65727574dfcd264acbb0c3e07860e4e9e9b22185`. |

PP-OCRv5/PP-OCRv6 model files and optional ONNX license-plate models may have
separate source, model and redistribution terms. The release records source,
SHA-256 and compatibility in a controlled manifest; this notice is not legal
advice.
