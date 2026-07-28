# Changelog

## 1.7.2 — Telegram first-notification rate-limit fix

- Fixed an edge case on freshly booted machines where the first Telegram
  notification could be treated as if it had already been rate-limited.

## 1.7.1 — Packaged GitHub Releases default

- Fresh packaged profiles now use the repository embedded in build metadata as
  their GitHub Releases source by default.
- An explicit operator choice to turn updates off is preserved.

## 1.7.0 — First managed-release version

- Added a single release version source and build metadata.
- Added isolated development/build dependency files, reproducible Windows asset scripts, and GitHub workflows.
- Added GitHub Release checksum fallback, pending verified-installer update helper, and release documentation.
- Kept PaddleOCR runtime staging separate from the main runtime.

This is the first version governed by this repository's release process; it is
not a claim about earlier historical release numbering.
