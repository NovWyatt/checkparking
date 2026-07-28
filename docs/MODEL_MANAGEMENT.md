# Model management

`models/manifest.json` is the project-controlled model schema. The current
entries are `local-unverified`; automatic model download is disabled until a
release source, license and SHA-256 are verified.

When such a manifest is configured, the application downloads its ZIP to a
versioned staging directory below the user profile, verifies SHA-256, validates
both detection and recognition folders, and launches an isolated PaddleOCR
synthetic smoke test using those exact folders. Only a successful acceptance
record enables **Dùng model đã thử ở lần mở sau**. The active-model registry is
written atomically and keeps the previous selection for **Quay lại model
trước**. If a selected model later fails engine initialization, local OCR rolls
back to the prior model/cache once instead of blocking the batch.

There is currently no project-controlled model release source. The UI therefore
correctly shows “Chưa cấu hình nguồn model đã xác minh” and does not offer an
unverified automatic download.
