"""Small contracts that keep the core independent from concrete modules."""
from typing import Any, Protocol


class ExchangeAdapter(Protocol):
    """Read/write boundary for a single exchange implementation."""

    name: str

    def get_order_book(self, symbol: str) -> dict[str, Any]: ...

    def get_balance(self) -> dict[str, Any]: ...

    def place_order(self, symbol: str, side: str, amount: float) -> dict[str, Any]: ...


class Strategy(Protocol):
    """A strategy proposes an action; the runtime/risk layer decides whether to execute it."""

    name: str

    def evaluate(self, market_data: dict[str, Any]) -> list[dict[str, Any]]: ...


class Notifier(Protocol):
    """Optional notification adapter."""

    def send(self, message: str) -> None: ...
