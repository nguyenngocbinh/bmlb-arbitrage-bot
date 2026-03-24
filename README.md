# Crypto Arbitrage Bot

Bot giao dịch chênh lệch giá crypto tự động giữa nhiều sàn. Hỗ trợ Binance, KuCoin, OKX, Bybit.

## Tính năng

- **3 chế độ bot**: Classic arbitrage, Delta-neutral hedging, Fake money (mô phỏng)
- **Realtime orderbook**: WebSocket qua ccxt.pro, phát hiện cơ hội tức thì
- **Đặt lệnh song song**: Mua/bán đồng thời trên nhiều sàn (async orders)
- **Multi-pair**: Giao dịch nhiều cặp tiền cùng lúc
- **Risk management**: Max drawdown, lỗ liên tiếp, cooldown, circuit breaker
- **Rate limiting**: Token bucket per exchange, tránh bị ban API
- **Slippage tracking**: So sánh giá kỳ vọng vs giá thực tế
- **Database**: SQLite lưu lịch sử sessions, trades, opportunities
- **Web dashboard**: FastAPI + Jinja2 theo dõi giao dịch qua trình duyệt
- **Backtesting**: Replay dữ liệu lịch sử, parameter sweep, phân tích metrics
- **Telegram alerts**: Thông báo cơ hội, giao dịch, lỗi qua Telegram

## Cấu trúc dự án

```
aws-arbitrage-bot/
├── main.py                 # Entry point
├── configs.py              # Cấu hình: exchanges, fees, risk, paths
├── requirements.txt        # Dependencies
│
├── bots/                   # Bot implementations
│   ├── base_bot.py         #   Lớp cơ sở (orderbook loop, session management)
│   ├── classic_bot.py      #   Mua sàn giá thấp → bán sàn giá cao
│   ├── delta_neutral_bot.py#   Spot arbitrage + short futures hedge
│   ├── fake_money_bot.py   #   Mô phỏng, không đặt lệnh thật
│   └── demo_fake_bot.py    #   Demo standalone (không cần API key)
│
├── services/               # Business logic
│   ├── exchange_service.py #   Kết nối sàn (ccxt/ccxt.pro)
│   ├── balance_service.py  #   Quản lý số dư
│   ├── order_service.py    #   Đặt lệnh đồng bộ
│   ├── async_order_service.py# Đặt lệnh bất đồng bộ (song song)
│   ├── database_service.py #   SQLite persistence
│   ├── notification_service.py# Telegram alerts
│   ├── risk_manager.py     #   Stop-loss & risk management
│   ├── rate_limiter.py     #   Token bucket rate limiting
│   └── multi_pair_manager.py#  Giao dịch đa cặp đồng thời
│
├── backtest/               # Backtesting framework
│   ├── data_recorder.py    #   Ghi orderbook vào SQLite
│   ├── engine.py           #   Replay engine + parameter sweep
│   └── analyzer.py         #   Phân tích: win rate, Sharpe, drawdown
│
├── web/                    # Web dashboard
│   ├── app.py              #   FastAPI app (REST API + HTML)
│   └── templates/          #   Jinja2 templates
│
├── utils/                  # Tiện ích
│   ├── exceptions.py       #   Custom exceptions
│   ├── helpers.py          #   Hàm tiện ích
│   ├── logger.py           #   Logging có màu + file
│   └── env_loader.py       #   Load .env
│
├── tests/                  # 12 test files, 221+ tests
├── data/                   # SQLite database (auto-created)
└── logs/                   # Log files (auto-created)
```

## Cài đặt

```bash
git clone https://github.com/nguyenngocbinh/aws-arbitrage-bot.git
cd aws-arbitrage-bot
pip install -r requirements.txt
```

## Cấu hình

Tạo file `.env` trong thư mục gốc:

```env
# Exchange API keys (cần cho classic/delta-neutral mode)
BINANCE_API_KEY=your_key
BINANCE_SECRET=your_secret

KUCOIN_API_KEY=your_key
KUCOIN_SECRET=your_secret
KUCOIN_PASSWORD=your_password

OKX_API_KEY=your_key
OKX_SECRET=your_secret
OKX_PASSWORD=your_password

BYBIT_API_KEY=your_key
BYBIT_SECRET=your_secret

# Telegram (tùy chọn)
TELEGRAM_TOKEN=your_bot_token
CHAT_ID=your_chat_id
```

## Sử dụng

### Demo nhanh (không cần API key)

```bash
# Dữ liệu thực từ sàn, tiền giả
python -m bots.demo_fake_bot --symbol BTC/USDT --exchanges binance okx bybit --duration 5
```

### Chạy bot đầy đủ

```bash
# Fake money — mô phỏng với dữ liệu thực
python main.py fake-money 15 1000 binance kucoin okx BTC/USDT

# Classic arbitrage — giao dịch thật (cần API keys)
python main.py classic 15 1000 binance kucoin okx BTC/USDT

# Delta-neutral — spot + futures hedge
python main.py delta-neutral 15 1000 binance kucoin okx BTC/USDT

# Multi-pair
python main.py fake-money 15 1000 binance kucoin okx --symbols BTC/USDT ETH/USDT SOL/USDT
```

**Tham số**:
| Tham số | Mô tả |
|---------|--------|
| `mode` | `fake-money`, `classic`, `delta-neutral` |
| `renew_time` | Thời gian mỗi phiên (phút) |
| `usdt_amount` | Vốn USDT |
| `exchange1-3` | 3 sàn giao dịch |
| `symbol` | Cặp tiền (tùy chọn, tự tìm nếu bỏ trống) |
| `--symbols` | Nhiều cặp tiền cho multi-pair mode |
| `--debug` | Bật debug logging |
| `--dry-run` | Chạy không đặt lệnh thật |

### Web Dashboard

```bash
uvicorn web.app:app --reload --port 8000
# Truy cập: http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Backtesting

```python
from backtest.data_recorder import DataRecorder
from backtest.engine import BacktestEngine
from backtest.analyzer import BacktestAnalyzer

recorder = DataRecorder(db_path=':memory:')
recorder.generate_sample_data('BTC/USDT', ['binance', 'kucoin'], 500, 50000.0, (100, 300))

engine = BacktestEngine(data_source=recorder, initial_balance=10000.0, fee_rate=0.001)
result = engine.run(symbol='BTC/USDT', exchanges=['binance', 'kucoin'])

analyzer = BacktestAnalyzer()
analyzer.add_result('test', result)
print(analyzer.generate_report('test'))
```

## Testing

```bash
# Tất cả tests (221+ tests)
pytest tests/ -v

# Một module cụ thể
pytest tests/test_backtest.py -v
pytest tests/test_risk_manager.py -v

# Dừng khi gặp lỗi
pytest tests/ -v -x
```

## Sàn hỗ trợ

| Sàn | Spot | Futures | Phí mặc định |
|-----|------|---------|-------------|
| Binance | ✅ | — | 0.1% / 0.1% |
| KuCoin | ✅ | ✅ | 0.1% / 0.1% |
| OKX | ✅ | — | 0.08% / 0.1% |
| Bybit | ✅ | — | 0.1% / 0.1% |

## Risk Management

Cấu hình trong `configs.py` → `RISK_CONFIG`:

| Tham số | Mặc định | Mô tả |
|---------|----------|--------|
| `max_drawdown_pct` | 5% | Drawdown tối đa trước khi dừng |
| `max_loss_per_trade_usd` | $10 | Lỗ tối đa mỗi giao dịch |
| `max_session_loss_pct` | 3% | Lỗ tối đa trong phiên |
| `max_consecutive_losses` | 5 | Lỗ liên tiếp tối đa |
| `max_slippage_pct` | 0.5% | Slippage cho phép |
| `cooldown_after_loss_sec` | 30s | Cooldown sau lỗ lớn |

## License

MIT License — tự do sử dụng và chỉnh sửa.

## Liên hệ

- GitHub: [nguyenngocbinh](https://github.com/nguyenngocbinh)
- Issues: Mở issue trên GitHub nếu gặp vấn đề
