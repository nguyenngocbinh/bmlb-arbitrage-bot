"""
Tests cho FastAPI Web Dashboard.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from backtest.data_recorder import DataRecorder
from services.database_service import DatabaseService
from utils import launch_profile
from web.app import create_app


@pytest.fixture
def db():
    """Database tạm cho tests."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    db_service = DatabaseService(db_path=path)
    yield db_service
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client(db):
    """FastAPI test client."""
    app = create_app(db_service=db)
    return TestClient(app)


@pytest.fixture
def settings_client(db, tmp_path, monkeypatch):
    """Client Settings với profile file được cô lập."""
    monkeypatch.setattr(
        launch_profile, 'PROFILE_PATH', str(tmp_path / 'bot_launch_profile.json')
    )
    return TestClient(create_app(db_service=db))


@pytest.fixture
def recorder():
    """Data recorder tạm cho các API backtest."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    recorder_service = DataRecorder(db_path=path)
    yield recorder_service
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def backtest_client(db, recorder):
    """Client với một recording session đủ dữ liệu để chạy backtest."""
    session_id = recorder.start_recording_session('BTC/USDT', ['binance', 'kucoin'])
    snapshots = []
    for timestamp in range(10):
        snapshots.extend([
            {'timestamp': timestamp, 'symbol': 'BTC/USDT', 'exchange': 'binance',
             'best_bid': 50000, 'best_ask': 50001, 'recording_session_id': session_id},
            {'timestamp': timestamp, 'symbol': 'BTC/USDT', 'exchange': 'kucoin',
             'best_bid': 50200, 'best_ask': 50201, 'recording_session_id': session_id},
        ])
    recorder.record_batch(snapshots)
    recorder.end_recording_session(session_id, len(snapshots))
    return TestClient(create_app(db_service=db, data_recorder=recorder))


@pytest.fixture
def seeded_db(db):
    """Database với dữ liệu mẫu."""
    s_id = db.create_session('classic', 'BTC/USDT', ['binance', 'kucoin'], 1000.0, 60)
    db.record_trade(
        s_id, 1, 'BTC/USDT', 'binance', 'kucoin',
        50000.0, 50100.0, 0.01, 0.1, 1.0, 0.05, 0.00001,
        0.1, 1.0,
        actual_buy_price=50010.0, actual_sell_price=50090.0,
        buy_slippage_pct=0.02, sell_slippage_pct=-0.02,
        total_slippage_usd=0.2
    )
    db.end_session(s_id, 0.1, 1.0, 0.05, 1, 1, 0, 500.0, 1001.0)
    return db


@pytest.fixture
def seeded_client(seeded_db):
    """Client với dữ liệu mẫu."""
    app = create_app(db_service=seeded_db)
    return TestClient(app)


class TestHealthCheck:
    """Test health endpoint."""

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestDashboard:
    """Test trang dashboard."""

    def test_dashboard_empty(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Dashboard" in r.text

    def test_dashboard_with_data(self, seeded_client):
        r = seeded_client.get("/dashboard")
        assert r.status_code == 200
        assert "BTC/USDT" in r.text

    def test_landing_page_loads(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "BMLB Arbitrage Bot" in r.text


class TestBacktestAPI:
    """Test trang và API backtest."""

    def test_backtest_page_loads(self, backtest_client):
        response = backtest_client.get("/backtest")
        assert response.status_code == 200
        assert "Backtest Arbitrage" in response.text

    def test_get_backtest_sessions_returns_recordings(self, backtest_client):
        response = backtest_client.get("/api/backtest/sessions")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_run_backtest_saves_result(self, backtest_client):
        response = backtest_client.post("/api/backtest/run", json={
            "recording_session_id": 1,
            "initial_balance_usd": 10000,
        })
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["analysis"]["total_trades"] > 0
        assert result["recording_session_id"] == 1

        detail = backtest_client.get(f"/api/backtest/results/{result['id']}")
        assert detail.status_code == 200
        assert len(detail.json()["data"]["trades"]) > 0

    def test_run_backtest_rejects_unknown_recording(self, backtest_client):
        response = backtest_client.post("/api/backtest/run", json={
            "recording_session_id": 999,
        })
        assert response.status_code == 404


class TestSettingsAPI:
    """Test trang và API lưu profile cấu hình bot."""

    def test_settings_page_loads(self, settings_client):
        response = settings_client.get("/settings")
        assert response.status_code == 200
        assert "Bot Configuration" in response.text

    def test_update_bot_profile_saves_valid_configuration(self, settings_client):
        profile = {
            "mode": "fake-money",
            "renew_time": 10,
            "usdt_amount": 500,
            "exchanges": ["binance", "kucoin", "okx"],
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "dry_run": True,
            "no_recovery": True,
        }
        response = settings_client.put("/api/settings/bot-profile", json=profile)
        assert response.status_code == 200
        assert response.json()["data"] == profile
        saved_profile = settings_client.get("/api/settings/bot-profile")
        assert saved_profile.json()["data"] == profile

    def test_update_bot_profile_rejects_duplicate_exchange(self, settings_client):
        response = settings_client.put("/api/settings/bot-profile", json={
            "mode": "fake-money",
            "renew_time": 10,
            "usdt_amount": 500,
            "exchanges": ["binance", "binance", "okx"],
            "symbols": ["BTC/USDT"],
        })
        assert response.status_code == 422


class TestSessionsAPI:
    """Test sessions API."""

    def test_get_sessions_empty(self, client):
        r = client.get("/api/sessions")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["count"] == 0

    def test_get_sessions_with_data(self, seeded_client):
        r = seeded_client.get("/api/sessions")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 1

    def test_get_session_by_id(self, seeded_client):
        r = seeded_client.get("/api/sessions/1")
        assert r.status_code == 200
        assert r.json()["data"]["symbol"] == "BTC/USDT"

    def test_get_session_not_found(self, client):
        r = client.get("/api/sessions/999")
        assert r.status_code == 404

    def test_sessions_filter_status(self, seeded_client):
        r = seeded_client.get("/api/sessions?status=completed")
        assert r.status_code == 200
        for s in r.json()["data"]:
            assert s["status"] == "completed"


class TestTradesAPI:
    """Test trades API."""

    def test_get_trades_empty(self, client):
        r = client.get("/api/trades")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_get_trades_with_data(self, seeded_client):
        r = seeded_client.get("/api/trades")
        data = r.json()
        assert data["count"] >= 1
        trade = data["data"][0]
        assert "buy_exchange" in trade
        assert "sell_exchange" in trade

    def test_get_session_trades(self, seeded_client):
        r = seeded_client.get("/api/sessions/1/trades")
        assert r.status_code == 200
        assert r.json()["count"] >= 1


class TestStatsAPI:
    """Test statistics API."""

    def test_overview_stats(self, seeded_client):
        r = seeded_client.get("/api/stats/overview")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "total_sessions" in data
        assert "total_trades" in data

    def test_daily_profit(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/daily")
        assert r.status_code == 200

    def test_hourly_profit(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/hourly")
        assert r.status_code == 200

    def test_profit_by_symbol(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/by-symbol")
        assert r.status_code == 200

    def test_profit_by_exchange(self, seeded_client):
        r = seeded_client.get("/api/stats/profit/by-exchange-pair")
        assert r.status_code == 200

    def test_exchange_performance(self, seeded_client):
        r = seeded_client.get("/api/stats/exchange-performance")
        assert r.status_code == 200

    def test_slippage_stats(self, seeded_client):
        r = seeded_client.get("/api/stats/slippage")
        assert r.status_code == 200
        assert "total_slippage_usd" in r.json()["data"]

    def test_slippage_by_exchange(self, seeded_client):
        r = seeded_client.get("/api/stats/slippage/by-exchange")
        assert r.status_code == 200


class TestErrorsAPI:
    """Test errors API."""

    def test_get_errors_empty(self, client):
        r = client.get("/api/errors")
        assert r.status_code == 200
        assert r.json()["count"] == 0
