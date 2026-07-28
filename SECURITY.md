# Security policy

Report suspected vulnerabilities privately to the repository owner. Do not
include API keys, Telegram bot tokens, user images, plate numbers or settings
exports in public issues.

Release assets are accepted by the app only after SHA-256 verification. GitHub
tokens, provider keys and Telegram tokens must be stored using the Windows
protected storage path when available; they must never be committed to GitHub
Actions logs or release artifacts.
