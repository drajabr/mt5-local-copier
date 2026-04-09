from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from app.models import AppConfig


class CopierEngine:
    def __init__(self) -> None:
        self._worker_status: Dict[str, str] = {}

    def apply(self, config: AppConfig) -> Dict[str, int]:
        source_workers = len([s for s in config.sources if s.settings.enabled])
        destination_workers = len([d for d in config.destinations if d.settings.enabled])

        self._worker_status.clear()
        for source in config.sources:
            self._worker_status[f"source:{source.id}"] = "running" if source.settings.enabled else "disabled"
        for destination in config.destinations:
            self._worker_status[f"destination:{destination.id}"] = "running" if destination.settings.enabled else "disabled"

        config.runtime.active_workers = source_workers + destination_workers
        config.runtime.last_applied_at = datetime.now(timezone.utc).isoformat()

        return {
            "sources": source_workers,
            "destinations": destination_workers,
            "total": source_workers + destination_workers,
        }

    def status(self) -> Dict[str, str]:
        return self._worker_status
