from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppUiState:
    current_page: str = "scan"
    notification: str = ""
    notification_level: str = "info"
    batch_snapshot: dict[str, object] = field(default_factory=dict)

    def notify(self, message: str, level: str = "info") -> None:
        self.notification = message
        self.notification_level = level
