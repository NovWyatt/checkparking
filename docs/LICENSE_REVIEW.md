# License review notes

The repository code is MIT. This is not legal advice. `THIRD_PARTY_NOTICES.md`
records the components reviewed from their published package/project licenses.
For v1.9.0, the optional Tesseract 5.5.3 component is built from the official
source tag and carries Apache-2.0/license notices; `tessdata_fast` `eng` and
`osd` are pinned to tag 4.1.0/commit
`65727574dfcd264acbb0c3e07860e4e9e9b22185`. Model/component release manifests
record source, hash, version and compatibility. Re-check redistribution terms
whenever a model, traineddata or binary changes.

## Detector license review — v1.9.6

The previous optional YOLOv9 detector from `ankandrew/open-image-models` is
not bundled or downloaded by current source/releases. Its repository code is
MIT, but the maintainer states that the released weights were trained from a
YOLOv9 GPL-3.0 fork and does not provide a definitive redistribution opinion.

The bundled replacement is OpenCV Zoo's
`license_plate_detection_lpd_yunet_2023mar.onnx`, licensed Apache-2.0 in its
own upstream model directory. Its upstream commit, SHA-256, attribution and a
copy of the Apache-2.0 license are preserved in `models/opencv_yunet/`.
