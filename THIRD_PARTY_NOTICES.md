# Third-party notices

Check Vehicle OCR is distributed under the MIT license for this repository's
own code. Third-party components keep their own licenses and notices.

| Component | Typical license/source | Distribution note |
|---|---|---|
| PaddleOCR / PaddlePaddle | Apache-2.0; PaddlePaddle project | Included only through Python runtime dependencies. |
| OpenCV | Apache-2.0 | Python wheel dependency. |
| openpyxl | MIT | Python wheel dependency. |
| OpenAI Python SDK | Apache-2.0 | Optional online-provider dependency. |
| OpenCV Zoo YuNet license-plate detector | Apache-2.0; OpenCV Zoo `license_plate_detection_yunet`, WATRIX/Dong Xu | Bundled Apache-2.0 ONNX model; source commit, attribution and SHA-256 are in `models/opencv_yunet/`. |
| PyInstaller | GPL-2.0-or-later with bootloader exception | Used to create release executable. |
| Inno Setup | See Inno Setup license | Used by release workflow to create installer. |
| Tesseract 5.5.3 | Apache-2.0; source tag `5.5.3` from tesseract-ocr/tesseract | Optional project-built Windows x64 component; its ZIP contains source/license notices and per-file hashes. |
| tessdata_fast 4.1.0 (`eng`, `osd`) | Apache-2.0; tesseract-ocr/tessdata_fast | Bundled only in the optional Tesseract component, pinned to commit `65727574dfcd264acbb0c3e07860e4e9e9b22185`. |

PP-OCRv5/PP-OCRv6 model files retain their Apache-2.0 model terms recorded in
`models/manifest.json`. The detector model is separately attributed under
`models/opencv_yunet/`. This notice is not legal advice.
