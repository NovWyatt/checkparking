# PaddleOCR runtime staging

Candidate PaddleOCR versions are installed only under
`.runtime\staging\paddleocr-<version>\venv`. The main `.venv` is not changed.
The candidate must pass import, synthetic OCR, normalization, Excel and
benchmark checks before its atomic registry entry can be activated for the next
launch. Rollback swaps the registry back to the previous accepted runtime.

Do not activate a candidate merely because it is newer. Failed staging remains
inspectable but is ignored by Git and is never bundled in releases.
