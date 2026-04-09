from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MappingStatus(str, Enum):
    AUTO_CONFIRMED = "auto_confirmed"
    NEEDS_REVIEW = "needs_review"
    USER_OVERRIDE = "user_override"
    UNMAPPED = "unmapped"


class SourceSettings(BaseModel):
    enabled: bool = True
    include_symbols: List[str] = Field(default_factory=list)
    exclude_symbols: List[str] = Field(default_factory=list)
    allowed_order_types: List[str] = Field(default_factory=lambda: ["market", "limit", "stop"])
    min_lot: float = 0.01
    max_lot: float = 100.0
    max_broadcasts_per_minute: int = 120


class RiskPreset(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class DestinationRiskPolicy(BaseModel):
    preset: RiskPreset = RiskPreset.BALANCED
    sizing_mode: str = "multiplier"
    fixed_lot: float = 0.01
    lot_multiplier: float = 1.0
    balance_ratio: float = 1.0
    risk_percent: float = 1.0
    min_lot: float = 0.01
    max_lot: float = 5.0
    max_open_trades: int = 20
    max_open_trades_per_symbol: int = 5
    max_drawdown_percent: float = 25.0
    max_spread_points: int = 50
    max_slippage_points: int = 30
    reverse_copy: bool = False


class DestinationSettings(BaseModel):
    enabled: bool = True
    channel_subscriptions: List[str] = Field(default_factory=list)
    symbol_mapping_mode: str = "mixed"
    copy_sl_tp: bool = True
    risk_policy: DestinationRiskPolicy = Field(default_factory=DestinationRiskPolicy)


class SymbolMappingEntry(BaseModel):
    source_symbol: str
    destination_symbol: Optional[str] = None
    status: MappingStatus = MappingStatus.UNMAPPED
    confidence: float = 0.0
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    user_locked: bool = False
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SourceConfig(BaseModel):
    id: str
    name: str
    channel: str
    terminal_path: str
    login: str = ""
    server: str = ""
    settings: SourceSettings = Field(default_factory=SourceSettings)


class DestinationConfig(BaseModel):
    id: str
    name: str
    terminal_path: str
    login: str = ""
    server: str = ""
    settings: DestinationSettings = Field(default_factory=DestinationSettings)
    symbol_mappings: List[SymbolMappingEntry] = Field(default_factory=list)


class ChannelConfig(BaseModel):
    name: str


class RuntimeState(BaseModel):
    last_applied_at: Optional[str] = None
    active_workers: int = 0


class AppConfig(BaseModel):
    version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    admin_token: str
    channels: List[ChannelConfig] = Field(default_factory=list)
    sources: List[SourceConfig] = Field(default_factory=list)
    destinations: List[DestinationConfig] = Field(default_factory=list)
    runtime: RuntimeState = Field(default_factory=RuntimeState)
