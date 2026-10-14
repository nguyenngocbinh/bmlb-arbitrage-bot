"""Read-only public API checks; this module never creates or cancels orders."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ccxt

DEFAULT_EXCHANGES = ("binance", "okx", "bybit", "kucoin")


def check_exchange(exchange_id: str, timeout_ms: int = 10_000) -> dict[str, Any]:
    """Check public market-data access for one CCXT exchange."""
    started = datetime.now(timezone.utc).isoformat()
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({"enableRateLimit": True, "timeout": timeout_ms})
        markets = exchange.load_markets()
        result = {
            "exchange": exchange_id,
            "ok": bool(markets),
            "market_count": len(markets),
            "checked_at": started,
            "error": None if markets else "No markets returned",
        }
        exchange.close()
        return result
    except Exception as exc:  # report API/network/schema failures for monitoring
        return {
            "exchange": exchange_id,
            "ok": False,
            "market_count": 0,
            "checked_at": started,
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


def main() -> int:
    results = [check_exchange(exchange_id) for exchange_id in DEFAULT_EXCHANGES]
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results}
    output = Path("api-health-report.json")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
