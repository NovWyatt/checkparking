# Telegram setup

Enter a Bot token and Chat ID only in Cài đặt → Thông báo. The application
stores the token through protected settings when available and never writes it
to logs. Use **Gửi tin thử** only when an operator deliberately wants a real
delivery. Automated tests mock all Telegram traffic.

Batch notifications are queued with timeout, bounded retry and a minimum
interval. Start, progress, completion, error and cancellation can be enabled
independently; a Telegram failure never fails OCR.
