"""Minimal-core defaults. Existing legacy entry points are intentionally unchanged."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    trading_mode: str = "paper"
    enabled_exchanges: tuple[str, ...] = ("binance", "okx", "bybit", "kucoin")
    api_check_interval_hours: int = 24

    def __post_init__(self) -> None:
        if self.trading_mode not in {"paper", "live", "monitor"}:
            raise ValueError("trading_mode must be paper, live, or monitor")
        if self.api_check_interval_hours < 1:
            raise ValueError("api_check_interval_hours must be >= 1")
