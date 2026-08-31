# Migration to the domain architecture

## Old → new

| Old path | New path |
|---|---|
| `configs.py` | `app/core/config.py` |
| `utils/exceptions.py` | `app/core/exceptions.py` |
| `utils/helpers.py` | `app/core/helpers.py` |
| `utils/logger.py` | `app/core/logging.py` |
| `utils/env_loader.py` | `app/core/env.py` |
| `utils/launch_profile.py` | `app/core/launch_profile.py` |
| `utils/session_recovery.py` | `app/recovery/session.py` |
| `services/exchange_service.py` | `app/exchanges/service.py` |
| `services/risk_manager.py` | `app/risk/manager.py` |
| `services/rate_limiter.py` | `app/risk/rate_limiter.py` |
| `services/balance_service.py` | `app/trading/balances.py` |
| `services/order_service.py` | `app/trading/orders.py` |
| `services/async_order_service.py` | `app/trading/async_orders.py` |
| `services/multi_pair_manager.py` | `app/trading/multi_pair.py` |
| `services/database_service.py` | `app/persistence/database.py` |
| `services/notification_service.py` | `app/notifications/telegram.py` |
| `bots/base_bot.py` | `app/arbitrage/base.py` |
| `bots/classic_bot.py` | `app/arbitrage/classic.py` |
| `bots/delta_neutral_bot.py` | `app/arbitrage/delta_neutral.py` |
| `bots/fake_money_bot.py` | `app/arbitrage/fake_money.py` |
| `bots/demo_fake_bot.py` | `app/arbitrage/demo_fake.py` |
| `backtest/data_recorder.py` | `app/backtesting/recorder.py` |
| `backtest/engine.py` | `app/backtesting/engine.py` |
| `backtest/analyzer.py` | `app/backtesting/analyzer.py` |
| `web/app.py` | `app/web/app.py` |

## Rule for new code

Do not add new modules to `bots/`, `services/`, `utils/`, `backtest/` or `web/`. Use `app/` instead.
