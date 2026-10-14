from minimal_core.settings import Settings


def test_paper_trading_is_default():
    assert Settings().trading_mode == "paper"


def test_supported_exchanges_are_explicit():
    assert Settings().enabled_exchanges == ("binance", "okx", "bybit", "kucoin")


def test_api_check_runs_daily_by_default():
    assert Settings().api_check_interval_hours == 24


def test_invalid_trading_mode_is_rejected():
    try:
        Settings(trading_mode="real-money")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid trading mode must be rejected")
