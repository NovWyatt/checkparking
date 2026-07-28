# Tesseract optional fallback

Tesseract is optional and does not block PaddleOCR. Operators can select an
existing executable, a portable directory, or a local ZIP that matches a
configured project-controlled manifest. The application does not download an
arbitrary Tesseract installer. Versioned portable staging preserves the old
path for rollback.
