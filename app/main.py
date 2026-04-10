from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config_store import ConfigStore
from app.copier_engine import CopierEngine
from app.models import (
    AppConfig,
    ChannelConfig,
    DestinationConfig,
    DestinationRiskPolicy,
    DestinationSettings,
    SourceConfig,
    SourceSettings,
)
from app.mt5_manager import Mt5Manager
from app.symbol_mapper import build_initial_mapping, merge_with_user_overrides


CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "/data/config/config.json"))
LOG_PATH = Path(os.getenv("LOG_PATH", "/data/logs/copier.log"))
MT5_ROOT = Path(os.getenv("MT5_ROOT", "/data/mt5"))
INSTALLER_SCRIPT = Path(os.getenv("INSTALLER_SCRIPT", "/app/scripts/install_mt5.sh"))

store = ConfigStore(CONFIG_PATH)
config_existed_before_start = CONFIG_PATH.exists()
config = store.load_or_create(env_token=os.getenv("ADMIN_TOKEN"))
if not os.getenv("ADMIN_TOKEN") and config_existed_before_start:
    print(
        "[mt5-local-copier] ADMIN_TOKEN not set; using persisted token from "
        f"{CONFIG_PATH}. Token is generated and printed only when config is created first time."
    )
manager = Mt5Manager(MT5_ROOT, INSTALLER_SCRIPT, LOG_PATH)
engine = CopierEngine()

try:
    manager.ensure_installation()
except Exception as exc:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"Startup warning: MT5 installation bootstrap failed: {exc}\n")

app = FastAPI(title="MT5 Local Copier MVP")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()


class ChannelCreate(BaseModel):
    name: str


class SourceCreate(BaseModel):
    name: str
    channel: str
    login: str = ""
    server: str = ""
    symbols: List[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD", "XAUUSD"])


class DestinationCreate(BaseModel):
    name: str
    channel_subscriptions: List[str] = Field(default_factory=list)
    login: str = ""
    server: str = ""
    symbols: List[str] = Field(default_factory=lambda: ["EURUSD.r", "GBPUSD.r", "GOLD"])


class ConfigApplyPayload(BaseModel):
    config: AppConfig


def require_admin_auth(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    expected_username = "admin"
    username_ok = secrets.compare_digest(credentials.username, expected_username)
    password_ok = secrets.compare_digest(credentials.password, config.admin_token)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="MT5 Local Copier"'},
        )


def _source_symbols(source_id: str) -> List[str]:
    for source in config.sources:
        if source.id == source_id:
            return source.settings.include_symbols or ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    return ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]


def _destination_symbols(destination: DestinationCreate) -> List[str]:
    return destination.symbols or ["EURUSD.r", "GBPUSD.r", "USDJPY.r", "GOLD"]


def _refresh_mappings_for_channels(channel_names: List[str]) -> None:
    for destination in config.destinations:
        subscribed = [c for c in destination.settings.channel_subscriptions if c in channel_names]
        if not subscribed:
            continue

        source_symbols: List[str] = []
        for channel_name in subscribed:
            for source in config.sources:
                if source.channel == channel_name:
                    source_symbols.extend(_source_symbols(source.id))

        if not source_symbols:
            continue

        destination_symbols = [
            entry.destination_symbol
            for entry in destination.symbol_mappings
            if entry.destination_symbol
        ]
        if not destination_symbols:
            destination_symbols = ["EURUSD.r", "GBPUSD.r", "USDJPY.r", "GOLD"]

        initial_map = build_initial_mapping(source_symbols, destination_symbols)
        destination.symbol_mappings = merge_with_user_overrides(destination.symbol_mappings, initial_map)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, _: None = Depends(require_admin_auth)):
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/api/dashboard")
def dashboard_data() -> Dict[str, object]:
    grouped: Dict[str, Dict[str, object]] = {}
    for channel in config.channels:
        grouped[channel.name] = {
            "sources": [s.model_dump() for s in config.sources if s.channel == channel.name],
            "destinations": [
                d.model_dump()
                for d in config.destinations
                if channel.name in d.settings.channel_subscriptions
            ],
        }

    return {
        "runtime": config.runtime.model_dump(),
        "channels": grouped,
        "worker_status": engine.status(),
    }


@app.get("/api/config")
def get_config(_: None = Depends(require_admin_auth)) -> Dict[str, object]:
    return config.model_dump(mode="json")


@app.get("/api/token-hint")
def token_hint() -> Dict[str, str]:
    return {"message": "Use HTTP Basic auth with username 'admin' and your admin token as password."}


@app.post("/api/channels")
def add_channel(payload: ChannelCreate, _: None = Depends(require_admin_auth)) -> Dict[str, str]:
    if any(channel.name == payload.name for channel in config.channels):
        raise HTTPException(status_code=409, detail="Channel already exists")

    config.channels.append(ChannelConfig(name=payload.name))
    store.save(config)
    return {"status": "created", "channel": payload.name}


@app.post("/api/sources")
def add_source(payload: SourceCreate, _: None = Depends(require_admin_auth)) -> Dict[str, str]:
    if not any(channel.name == payload.channel for channel in config.channels):
        raise HTTPException(status_code=404, detail="Channel does not exist")

    source_id = f"src-{uuid4().hex[:8]}"
    source = SourceConfig(
        id=source_id,
        name=payload.name,
        channel=payload.channel,
        terminal_path=str(MT5_ROOT / "instances" / source_id),
        login=payload.login,
        server=payload.server,
        settings=SourceSettings(include_symbols=payload.symbols),
    )
    config.sources.append(source)
    _refresh_mappings_for_channels([payload.channel])

    manager.ensure_instances([source.id])
    store.save(config)
    return {"status": "created", "source_id": source.id}


@app.post("/api/destinations")
def add_destination(payload: DestinationCreate, _: None = Depends(require_admin_auth)) -> Dict[str, str]:
    destination_id = f"dst-{uuid4().hex[:8]}"
    destination = DestinationConfig(
        id=destination_id,
        name=payload.name,
        terminal_path=str(MT5_ROOT / "instances" / destination_id),
        login=payload.login,
        server=payload.server,
        settings=DestinationSettings(
            channel_subscriptions=payload.channel_subscriptions,
            risk_policy=DestinationRiskPolicy(),
        ),
    )

    source_symbols: List[str] = []
    if payload.channel_subscriptions:
        channel = payload.channel_subscriptions[0]
        matching_sources = [source for source in config.sources if source.channel == channel]
        for source in matching_sources:
            source_symbols.extend(_source_symbols(source.id))

    if not source_symbols:
        source_symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]

    initial_map = build_initial_mapping(source_symbols, _destination_symbols(payload))
    destination.symbol_mappings = merge_with_user_overrides(destination.symbol_mappings, initial_map)

    config.destinations.append(destination)
    manager.ensure_instances([destination.id])
    store.save(config)
    return {"status": "created", "destination_id": destination.id}


@app.post("/api/config/preview")
def preview_apply(payload: ConfigApplyPayload, _: None = Depends(require_admin_auth)) -> Dict[str, object]:
    new_config = payload.config

    errors = []
    for destination in new_config.destinations:
        rp = destination.settings.risk_policy
        if rp.min_lot > rp.max_lot:
            errors.append(f"{destination.name}: min_lot is greater than max_lot")
        if rp.max_open_trades < rp.max_open_trades_per_symbol:
            errors.append(f"{destination.name}: max_open_trades must be >= per-symbol limit")

    old_worker_count = config.runtime.active_workers
    new_worker_count = len([s for s in new_config.sources if s.settings.enabled]) + len(
        [d for d in new_config.destinations if d.settings.enabled]
    )

    return {
        "errors": errors,
        "changes": {
            "sources_before": len(config.sources),
            "sources_after": len(new_config.sources),
            "destinations_before": len(config.destinations),
            "destinations_after": len(new_config.destinations),
            "workers_before": old_worker_count,
            "workers_after": new_worker_count,
        },
    }


@app.post("/api/config/apply")
def apply_config(payload: ConfigApplyPayload, _: None = Depends(require_admin_auth)) -> Dict[str, object]:
    global config
    config = payload.config

    all_instances = [source.id for source in config.sources] + [destination.id for destination in config.destinations]
    manager.ensure_instances(all_instances)

    worker_counts = engine.apply(config)
    store.save(config)

    return {"status": "applied", "workers": worker_counts, "runtime": config.runtime.model_dump()}
