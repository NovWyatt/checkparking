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
| Tesseract | Apache-2.0 | Not bundled by default; optional operator-selected fallback. |

OCR models and optional ONNX license-plate models may have separate source,
model, and redistribution terms. The project does not publish a model package
until its source, checksum and license are recorded in a controlled manifest.
