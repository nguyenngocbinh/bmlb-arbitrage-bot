"""
Data recorder - Ghi dữ liệu orderbook lịch sử từ các sàn giao dịch.
Dữ liệu được lưu dưới dạng SQLite để sử dụng cho backtest.
"""
import sqlite3
import time
import json
import os
import random
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

from utils.logger import log_info, log_error


class DataRecorder:
    """
    Ghi dữ liệu orderbook real-time vào SQLite để dùng cho backtest.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Khởi tạo data recorder.

        Args:
            db_path (str, optional): Đường dẫn file SQLite.
                Mặc định: data/orderbook_history.db
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            os.makedirs(os.path.join(base_dir, 'data'), exist_ok=True)
            db_path = os.path.join(base_dir, 'data', 'orderbook_history.db')

        self.db_path = db_path
        self._initialize_database()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager cho database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_database(self) -> None:
        """Tạo bảng lưu trữ dữ liệu orderbook."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    best_bid REAL NOT NULL,
                    best_ask REAL NOT NULL,
                    bid_volume REAL,
                    ask_volume REAL,
                    recorded_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ob_symbol_ts
                ON orderbook_snapshots(symbol, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ob_exchange_ts
                ON orderbook_snapshots(exchange, timestamp)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS recording_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchanges TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    snapshot_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'recording'
                )
            """)
            columns = {
                row['name'] for row in conn.execute(
                    "PRAGMA table_info(orderbook_snapshots)"
                ).fetchall()
            }
            if 'recording_session_id' not in columns:
                conn.execute(
                    "ALTER TABLE orderbook_snapshots ADD COLUMN recording_session_id INTEGER"
                )
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ob_recording_session
                ON orderbook_snapshots(recording_session_id, timestamp)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recording_session_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    config TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    equity_curve TEXT NOT NULL,
                    FOREIGN KEY (recording_session_id) REFERENCES recording_sessions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_run_id INTEGER NOT NULL,
                    trade_number INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    buy_exchange TEXT NOT NULL,
                    sell_exchange TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    profit_usd REAL NOT NULL,
                    profit_pct REAL NOT NULL,
                    fee_usd REAL NOT NULL,
                    cumulative_profit_usd REAL NOT NULL,
                    FOREIGN KEY (backtest_run_id) REFERENCES backtest_runs(id)
                )
            """)

    def record_snapshot(self, timestamp: float, symbol: str, exchange: str, best_bid: float,
                        best_ask: float, bid_volume: Optional[float] = None,
                        ask_volume: Optional[float] = None,
                        recording_session_id: Optional[int] = None) -> None:
        """
        Ghi một snapshot orderbook.

        Args:
            timestamp (float): Unix timestamp
            symbol (str): Cặp giao dịch (VD: BTC/USDT)
            exchange (str): Tên sàn
            best_bid (float): Giá bid tốt nhất
            best_ask (float): Giá ask tốt nhất
            bid_volume (float, optional): Volume bid
            ask_volume (float, optional): Volume ask
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO orderbook_snapshots
                (timestamp, symbol, exchange, best_bid, best_ask, bid_volume, ask_volume,
                 recording_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, symbol, exchange, best_bid, best_ask, bid_volume, ask_volume,
                  recording_session_id))

    def record_batch(self, snapshots: list[dict[str, Any]]) -> None:
        """
        Ghi nhiều snapshot cùng lúc (hiệu quả hơn).

        Args:
            snapshots (list): Danh sách dict chứa thông tin snapshot
        """
        with self._get_connection() as conn:
            conn.executemany("""
                INSERT INTO orderbook_snapshots
                (timestamp, symbol, exchange, best_bid, best_ask, bid_volume, ask_volume,
                 recording_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (s['timestamp'], s['symbol'], s['exchange'],
                 s['best_bid'], s['best_ask'],
                 s.get('bid_volume'), s.get('ask_volume'),
                 s.get('recording_session_id'))
                for s in snapshots
            ])

    def start_recording_session(self, symbol: str, exchanges: list[str]) -> int:
        """
        Bắt đầu phiên ghi dữ liệu.

        Args:
            symbol (str): Cặp giao dịch
            exchanges (list): Danh sách sàn

        Returns:
            int: ID session ghi dữ liệu
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO recording_sessions (symbol, exchanges, start_time)
                VALUES (?, ?, ?)
            """, (symbol, json.dumps(exchanges), datetime.now().isoformat()))
            return cursor.lastrowid

    def end_recording_session(self, session_id: int, snapshot_count: int) -> None:
        """
        Kết thúc phiên ghi dữ liệu.

        Args:
            session_id (int): ID session
            snapshot_count (int): Tổng số snapshot đã ghi
        """
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE recording_sessions
                SET end_time = ?, snapshot_count = ?, status = 'completed'
                WHERE id = ?
            """, (datetime.now().isoformat(), snapshot_count, session_id))

    def get_snapshots(self, symbol: str, exchanges: Optional[list[str]] = None,
                      start_time: Optional[float] = None, end_time: Optional[float] = None,
                      recording_session_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Lấy dữ liệu snapshot theo điều kiện.

        Args:
            symbol (str): Cặp giao dịch
            exchanges (list, optional): Lọc theo sàn
            start_time (float, optional): Thời gian bắt đầu (unix)
            end_time (float, optional): Thời gian kết thúc (unix)

        Returns:
            list: Danh sách snapshot (dict)
        """
        query = "SELECT * FROM orderbook_snapshots WHERE symbol = ?"
        params = [symbol]

        if exchanges:
            placeholders = ','.join('?' * len(exchanges))
            query += f" AND exchange IN ({placeholders})"
            params.extend(exchanges)

        if start_time is not None:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time is not None:
            query += " AND timestamp <= ?"
            params.append(end_time)

        if recording_session_id is not None:
            query += " AND recording_session_id = ?"
            params.append(recording_session_id)

        query += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_recording_sessions(self) -> list[dict[str, Any]]:
        """
        Lấy danh sách các phiên ghi dữ liệu.

        Returns:
            list: Danh sách session (dict)
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM recording_sessions ORDER BY id DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_recording_session(self, session_id: int) -> Optional[dict[str, Any]]:
        """Lấy thông tin một phiên ghi dữ liệu."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM recording_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def save_backtest_result(self, recording_session_id: int, result: Any,
                             analysis: dict[str, Any]) -> int:
        """Lưu kết quả một lần chạy backtest và các giao dịch mô phỏng."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO backtest_runs
                (recording_session_id, config, analysis, equity_curve)
                VALUES (?, ?, ?, ?)
            """, (
                recording_session_id,
                json.dumps(result.config),
                json.dumps(analysis),
                json.dumps(result.equity_curve),
            ))
            run_id = cursor.lastrowid
            conn.executemany("""
                INSERT INTO backtest_trades
                (backtest_run_id, trade_number, timestamp, buy_exchange, sell_exchange,
                 buy_price, sell_price, amount, profit_usd, profit_pct, fee_usd,
                 cumulative_profit_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    run_id, trade['trade_number'], trade['timestamp'],
                    trade['buy_exchange'], trade['sell_exchange'], trade['buy_price'],
                    trade['sell_price'], trade['amount'], trade['profit_usd'],
                    trade['profit_pct'], trade['fee_usd'],
                    trade['cumulative_profit_usd'],
                )
                for trade in result.trades
            ])
            return run_id

    def get_backtest_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Lấy lịch sử các lần chạy backtest mới nhất."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT br.id, br.recording_session_id, br.created_at, br.config,
                       br.analysis, br.equity_curve, rs.symbol, rs.exchanges
                FROM backtest_runs br
                JOIN recording_sessions rs ON rs.id = br.recording_session_id
                ORDER BY br.id DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [self._deserialize_backtest_run(dict(row)) for row in rows]

    def get_backtest_run(self, run_id: int) -> Optional[dict[str, Any]]:
        """Lấy chi tiết một lần chạy backtest."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT br.id, br.recording_session_id, br.created_at, br.config,
                       br.analysis, br.equity_curve, rs.symbol, rs.exchanges
                FROM backtest_runs br
                JOIN recording_sessions rs ON rs.id = br.recording_session_id
                WHERE br.id = ?
            """, (run_id,)).fetchone()
            return self._deserialize_backtest_run(dict(row)) if row else None

    def get_backtest_trades(self, run_id: int, limit: int = 500) -> list[dict[str, Any]]:
        """Lấy giao dịch mô phỏng của một lần chạy backtest."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM backtest_trades
                WHERE backtest_run_id = ?
                ORDER BY trade_number ASC
                LIMIT ?
            """, (run_id, limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def _deserialize_backtest_run(run: dict[str, Any]) -> dict[str, Any]:
        """Chuyển các trường JSON của backtest run thành dữ liệu có cấu trúc."""
        run['config'] = json.loads(run['config'])
        run['analysis'] = json.loads(run['analysis'])
        run['equity_curve'] = json.loads(run['equity_curve'])
        run['exchanges'] = json.loads(run['exchanges'])
        return run

    def get_snapshot_count(self, symbol: Optional[str] = None) -> int:
        """
        Đếm số snapshot.

        Args:
            symbol (str, optional): Lọc theo symbol

        Returns:
            int: Số snapshot
        """
        query = "SELECT COUNT(*) FROM orderbook_snapshots"
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)

        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    def generate_synthetic_data(self, symbol: str, exchanges: list[str], duration_minutes: int = 60,
                                interval_seconds: float = 1, base_price: float = 50000,
                                spread_bps: float = 5, volatility_bps: float = 10) -> int:
        """
        Tạo dữ liệu orderbook giả lập cho backtest.

        Args:
            symbol (str): Cặp giao dịch
            exchanges (list): Danh sách sàn
            duration_minutes (int): Thời gian (phút)
            interval_seconds (float): Khoảng cách giữa các snapshot (giây)
            base_price (float): Giá cơ sở
            spread_bps (float): Spread trung bình (basis points)
            volatility_bps (float): Biến động giá (basis points)

        Returns:
            int: Số snapshot đã tạo
        """
        start_time = time.time()
        total_seconds = duration_minutes * 60
        steps = int(total_seconds / interval_seconds)
        count = 0

        # Giá base cho từng sàn (có chênh lệch nhỏ)
        exchange_offsets = {}
        for ex in exchanges:
            exchange_offsets[ex] = random.uniform(-0.0002, 0.0002)

        current_price = base_price
        batch = []

        for step in range(steps):
            ts = start_time + step * interval_seconds

            # Random walk cho giá
            price_change = random.gauss(0, base_price * volatility_bps / 10000)
            current_price = max(current_price + price_change, base_price * 0.9)

            for ex in exchanges:
                # Giá mỗi sàn có offset riêng
                offset = exchange_offsets[ex]
                ex_price = current_price * (1 + offset)

                # Thêm noise cho mỗi sàn
                noise = random.gauss(0, base_price * 0.00005)
                ex_price += noise

                spread = ex_price * spread_bps / 10000
                best_bid = ex_price - spread / 2
                best_ask = ex_price + spread / 2

                bid_volume = random.uniform(0.1, 5.0)
                ask_volume = random.uniform(0.1, 5.0)

                batch.append({
                    'timestamp': ts,
                    'symbol': symbol,
                    'exchange': ex,
                    'best_bid': round(best_bid, 2),
                    'best_ask': round(best_ask, 2),
                    'bid_volume': round(bid_volume, 4),
                    'ask_volume': round(ask_volume, 4),
                })
                count += 1

            # Ghi batch mỗi 1000 records
            if len(batch) >= 1000:
                self.record_batch(batch)
                batch = []

            # Thỉnh thoảng tạo opportunity lớn (spike giá)
            if random.random() < 0.005:
                spike_ex = random.choice(exchanges)
                spike_direction = random.choice([-1, 1])
                exchange_offsets[spike_ex] += spike_direction * random.uniform(0.0003, 0.001)

            # Mean reversion cho offset
            for ex in exchanges:
                exchange_offsets[ex] *= 0.999

        # Ghi batch còn lại
        if batch:
            self.record_batch(batch)

        return count
