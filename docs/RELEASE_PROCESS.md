# Release process

1. Set the semantic version in `check_vehicle_ocr/version.py` and update `CHANGELOG.md`.
2. Run the quality gate with `.venv\Scripts\python.exe`, including `tests\release_system_test.py`, package smoke and the relevant benchmark.
3. Commit the release changes, tag `v<version>`, and push the tag.
4. GitHub Actions builds Windows assets and publishes the GitHub Release.
5. Verify the release contains setup EXE, portable ZIP, manifest and `SHA256SUMS.txt`.
6. Use a packaged app to check, download and verify the release before offering it to operators.

The release workflow intentionally skips model warm-up. A release uses a
first-run PaddleOCR model bootstrap unless a license-reviewed model is bundled;
it must not silently ship an unverified model. The repository model manifest is
bundled as metadata only and does not enable model downloads without a verified
project source.
