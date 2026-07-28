# Update system

Public release builds embed their own `owner/repository` build metadata. The
Update Center queries GitHub Releases, rejects source archives, and accepts a
Windows asset only with GitHub's SHA-256 digest or a matching entry in the
project-provided `SHA256SUMS.txt` asset.

After explicit user approval, a verified setup EXE is recorded atomically as a
pending update. A separate PowerShell helper waits for the app to close, backs
up the install directory, runs the installer, executes the new executable's
`--runtime-health-check`, then starts the normal UI. A failed install or health
check restores the backup and starts the prior executable. Startup also repairs
the narrow power-loss case where the install directory is missing but the
helper backup remains. Source runs do not self-update.

For a public repository no token is needed. A private repository can use an
optional GitHub token in Settings → Updates → Technical details. The token is
stored with Windows DPAPI when available and is never included in the update
URL, logs, release artifacts or exported settings.
