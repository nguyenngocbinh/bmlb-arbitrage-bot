---
description: "Use when editing or creating test files."
applyTo: "tests/**/*.py"
---

# Testing Instructions

## Framework

- pytest + pytest-asyncio
- Test files: `tests/test_*.py`
- New production imports must use the `app.*` namespace.
- Legacy `services.*`, `bots.*`, `utils.*`, `backtest.*` imports are compatibility paths only.

## Conventions

- Mỗi test class kế thừa `unittest.TestCase` hoặc dùng plain functions
- Mock ccxt exchanges — KHÔNG gọi API thật
- Dùng `@pytest.mark.asyncio` cho async tests
- Test naming: `test_<method>_<scenario>_<expected>`
- Nếu production code chuyển sang async, test integration phải `await` call tương ứng
- Với `BalanceService`, mock `async_get_balance` thay vì `get_balance`

## Common Mocks

```python
# Mock exchange
mock_exchange = MagicMock()
mock_exchange.id = 'binance'
mock_exchange.fetch_order_book = AsyncMock(return_value={...})

# Mock database — dùng `:memory:` SQLite
db = DatabaseService(db_path=':memory:')
```

## Chạy Tests

```bash
pytest tests/ -v
pytest tests/test_backtest.py -v
pytest tests/ -v -x
pytest tests/ -v -k "test_risk"
pytest tests/test_integration.py -q
```
