from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Optional

from app.models import AppConfig


def _default_token() -> str:
    return secrets.token_urlsafe(24)


class ConfigStore:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load_or_create(self, env_token: Optional[str] = None) -> AppConfig:
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            return AppConfig.model_validate(data)

        token = env_token or _default_token()
        config = AppConfig(admin_token=token)
        self.save(config)

        if not env_token:
            print(f"[mt5-local-copier] Generated admin token: {token}")

        return config

    def save(self, config: AppConfig) -> None:
        payload = config.model_dump(mode="json")
        tmp_path = self.config_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(self.config_path)
