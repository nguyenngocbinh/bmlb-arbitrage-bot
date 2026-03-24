"""
Service quản lý cơ sở dữ liệu SQLite cho lịch sử giao dịch và thống kê.
"""
import os
import sqlite3
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from utils.logger import log_info, log_error, log_debug


# Đường dẫn mặc định cho database
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'arbitrage.db')


class DatabaseService:
    """
    Lớp dịch vụ quản lý cơ sở dữ liệu SQLite cho bot giao dịch.
    Lưu trữ lịch sử giao dịch, phiên, cơ hội, và số dư.
    """

    def __init__(self, db_path=None):
        """
        Khởi tạo dịch vụ cơ sở dữ liệu.

        Args:
            db_path (str, optional): Đường dẫn đến file database.
                Mặc định là data/arbitrage.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH

        # Tạo thư mục data nếu chưa tồn tại
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Khởi tạo database
        self._initialize_database()

    @contextmanager
    def _get_connection(self):
        """
        Context manager để lấy kết nối database.

        Yields:
            sqlite3.Connection: Kết nối database với row_factory
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_database(self):
        """Tạo các bảng cần thiết nếu chưa tồn tại."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    exchanges TEXT NOT NULL,
                    usdt_amount REAL NOT NULL,
                    renew_time_minutes INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_profit_pct REAL DEFAULT 0,
                    total_profit_usd REAL DEFAULT 0,
                    total_fees_usd REAL DEFAULT 0,
                    opportunities_found INTEGER DEFAULT 0,
                    trades_executed INTEGER DEFAULT 0,
                    trades_failed INTEGER DEFAULT 0,
                    total_volume_usd REAL DEFAULT 0,
                    final_balance REAL,
                    status TEXT DEFAULT 'running',
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    trade_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    buy_exchange TEXT NOT NULL,
                    sell_exchange TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    profit_pct REAL NOT NULL,
                    profit_usd REAL NOT NULL,
                    fee_usd REAL NOT NULL,
                    fee_crypto REAL NOT NULL,
                    cumulative_profit_pct REAL NOT NULL,
                    cumulative_profit_usd REAL NOT NULL,
                    status TEXT DEFAULT 'executed',
                    order_buy_id TEXT,
                    order_sell_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    buy_exchange TEXT NOT NULL,
                    sell_exchange TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    spread_pct REAL NOT NULL,
                    estimated_profit_usd REAL NOT NULL,
                    executed INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS balance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    usdt_balance REAL NOT NULL,
                    crypto_balance REAL NOT NULL,
                    crypto_symbol TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    timestamp TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    exchange TEXT,
                    message TEXT NOT NULL,
                    details TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_trades_session ON trades(session_id);
                CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_opportunities_session ON opportunities(session_id);
                CREATE INDEX IF NOT EXISTS idx_balance_snapshots_session ON balance_snapshots(session_id);
                CREATE INDEX IF NOT EXISTS idx_error_log_session ON error_log(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
                CREATE INDEX IF NOT EXISTS idx_sessions_symbol ON sessions(symbol);
            """)
            log_info(f"Database đã được khởi tạo: {self.db_path}")

    # ─── Session Management ───────────────────────────────────────────

    def create_session(self, mode, symbol, exchanges, usdt_amount, renew_time_minutes):
        """
        Tạo một phiên giao dịch mới.

        Args:
            mode (str): Chế độ bot
            symbol (str): Cặp giao dịch
            exchanges (list): Danh sách sàn giao dịch
            usdt_amount (float): Số tiền USDT
            renew_time_minutes (int): Thời gian làm mới (phút)

        Returns:
            int: ID của phiên giao dịch
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO sessions 
                   (mode, symbol, exchanges, usdt_amount, renew_time_minutes, start_time, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'running')""",
                (mode, symbol, ','.join(exchanges), usdt_amount, renew_time_minutes,
                 datetime.now(timezone.utc).isoformat())
            )
            session_id = cursor.lastrowid
            log_info(f"Đã tạo phiên giao dịch #{session_id}")
            return session_id

    def update_session(self, session_id, **kwargs):
        """
        Cập nhật thông tin phiên giao dịch.

        Args:
            session_id (int): ID phiên giao dịch
            **kwargs: Các trường cần cập nhật
        """
        allowed_fields = {
            'end_time', 'total_profit_pct', 'total_profit_usd', 'total_fees_usd',
            'opportunities_found', 'trades_executed', 'trades_failed',
            'total_volume_usd', 'final_balance', 'status', 'error_message'
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not fields:
            return

        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [session_id]

        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE sessions SET {set_clause} WHERE id = ?",
                values
            )

    def end_session(self, session_id, total_profit_pct, total_profit_usd,
                    total_fees_usd, opportunities_found, trades_executed,
                    trades_failed, total_volume_usd, final_balance, status='completed'):
        """
        Kết thúc một phiên giao dịch.

        Args:
            session_id (int): ID phiên giao dịch
            total_profit_pct (float): Tổng lợi nhuận %
            total_profit_usd (float): Tổng lợi nhuận USD
            total_fees_usd (float): Tổng phí USD
            opportunities_found (int): Số cơ hội phát hiện
            trades_executed (int): Số giao dịch thành công
            trades_failed (int): Số giao dịch thất bại
            total_volume_usd (float): Tổng khối lượng
            final_balance (float): Số dư cuối
            status (str): Trạng thái (completed/error/interrupted)
        """
        self.update_session(
            session_id,
            end_time=datetime.now(timezone.utc).isoformat(),
            total_profit_pct=total_profit_pct,
            total_profit_usd=total_profit_usd,
            total_fees_usd=total_fees_usd,
            opportunities_found=opportunities_found,
            trades_executed=trades_executed,
            trades_failed=trades_failed,
            total_volume_usd=total_volume_usd,
            final_balance=final_balance,
            status=status
        )
        log_info(f"Phiên giao dịch #{session_id} đã kết thúc. Trạng thái: {status}")

    def get_session(self, session_id):
        """
        Lấy thông tin chi tiết phiên giao dịch.

        Args:
            session_id (int): ID phiên giao dịch

        Returns:
            dict: Thông tin phiên giao dịch, hoặc None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_sessions(self, limit=50, offset=0, status=None, symbol=None):
        """
        Lấy danh sách phiên giao dịch với phân trang và bộ lọc.

        Args:
            limit (int): Số lượng tối đa
            offset (int): Vị trí bắt đầu
            status (str, optional): Lọc theo trạng thái
            symbol (str, optional): Lọc theo cặp giao dịch

        Returns:
            list[dict]: Danh sách phiên giao dịch
        """
        query = "SELECT * FROM sessions WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ─── Trade Management ─────────────────────────────────────────────

    def record_trade(self, session_id, trade_number, symbol, buy_exchange,
                     sell_exchange, buy_price, sell_price, amount, profit_pct,
                     profit_usd, fee_usd, fee_crypto, cumulative_profit_pct,
                     cumulative_profit_usd, status='executed',
                     order_buy_id=None, order_sell_id=None):
        """
        Ghi lại một giao dịch.

        Args:
            session_id (int): ID phiên giao dịch
            trade_number (int): Số thứ tự giao dịch
            symbol (str): Cặp giao dịch
            buy_exchange (str): Sàn mua
            sell_exchange (str): Sàn bán
            buy_price (float): Giá mua
            sell_price (float): Giá bán
            amount (float): Số lượng
            profit_pct (float): Lợi nhuận %
            profit_usd (float): Lợi nhuận USD
            fee_usd (float): Phí USD
            fee_crypto (float): Phí crypto
            cumulative_profit_pct (float): Lợi nhuận tích lũy %
            cumulative_profit_usd (float): Lợi nhuận tích lũy USD
            status (str): Trạng thái
            order_buy_id (str, optional): ID lệnh mua
            order_sell_id (str, optional): ID lệnh bán

        Returns:
            int: ID của giao dịch
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO trades 
                   (session_id, trade_number, timestamp, symbol, buy_exchange, sell_exchange,
                    buy_price, sell_price, amount, profit_pct, profit_usd, fee_usd, fee_crypto,
                    cumulative_profit_pct, cumulative_profit_usd, status, order_buy_id, order_sell_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, trade_number, datetime.now(timezone.utc).isoformat(), symbol,
                 buy_exchange, sell_exchange, buy_price, sell_price, amount,
                 profit_pct, profit_usd, fee_usd, fee_crypto,
                 cumulative_profit_pct, cumulative_profit_usd, status,
                 order_buy_id, order_sell_id)
            )
            return cursor.lastrowid

    def get_trades_by_session(self, session_id, limit=100, offset=0):
        """
        Lấy danh sách giao dịch của một phiên.

        Args:
            session_id (int): ID phiên giao dịch
            limit (int): Số lượng tối đa
            offset (int): Vị trí bắt đầu

        Returns:
            list[dict]: Danh sách giao dịch
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM trades WHERE session_id = ?
                   ORDER BY trade_number ASC LIMIT ? OFFSET ?""",
                (session_id, limit, offset)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_all_trades(self, limit=100, offset=0, symbol=None,
                       buy_exchange=None, sell_exchange=None,
                       start_date=None, end_date=None):
        """
        Lấy danh sách giao dịch với bộ lọc.

        Args:
            limit (int): Số lượng tối đa
            offset (int): Vị trí bắt đầu
            symbol (str, optional): Lọc theo cặp giao dịch
            buy_exchange (str, optional): Lọc theo sàn mua
            sell_exchange (str, optional): Lọc theo sàn bán
            start_date (str, optional): Lọc từ ngày (ISO format)
            end_date (str, optional): Lọc đến ngày (ISO format)

        Returns:
            list[dict]: Danh sách giao dịch
        """
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if buy_exchange:
            query += " AND buy_exchange = ?"
            params.append(buy_exchange)
        if sell_exchange:
            query += " AND sell_exchange = ?"
            params.append(sell_exchange)
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ─── Opportunity Management ───────────────────────────────────────

    def record_opportunity(self, session_id, symbol, buy_exchange, sell_exchange,
                           buy_price, sell_price, spread_pct, estimated_profit_usd,
                           executed=False):
        """
        Ghi lại một cơ hội giao dịch.

        Args:
            session_id (int): ID phiên giao dịch
            symbol (str): Cặp giao dịch
            buy_exchange (str): Sàn mua
            sell_exchange (str): Sàn bán
            buy_price (float): Giá mua
            sell_price (float): Giá bán
            spread_pct (float): Chênh lệch %
            estimated_profit_usd (float): Lợi nhuận ước tính USD
            executed (bool): Đã thực hiện hay không

        Returns:
            int: ID của cơ hội
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO opportunities 
                   (session_id, timestamp, symbol, buy_exchange, sell_exchange,
                    buy_price, sell_price, spread_pct, estimated_profit_usd, executed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, datetime.now(timezone.utc).isoformat(), symbol,
                 buy_exchange, sell_exchange, buy_price, sell_price,
                 spread_pct, estimated_profit_usd, 1 if executed else 0)
            )
            return cursor.lastrowid

    def get_opportunities_by_session(self, session_id, executed_only=False, limit=100):
        """
        Lấy danh sách cơ hội của một phiên.

        Args:
            session_id (int): ID phiên giao dịch
            executed_only (bool): Chỉ lấy cơ hội đã thực hiện
            limit (int): Số lượng tối đa

        Returns:
            list[dict]: Danh sách cơ hội
        """
        query = "SELECT * FROM opportunities WHERE session_id = ?"
        params = [session_id]

        if executed_only:
            query += " AND executed = 1"

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ─── Balance Snapshot Management ──────────────────────────────────

    def record_balance_snapshot(self, session_id, exchange, usdt_balance,
                                crypto_balance, crypto_symbol):
        """
        Ghi lại snapshot số dư.

        Args:
            session_id (int): ID phiên giao dịch
            exchange (str): Sàn giao dịch
            usdt_balance (float): Số dư USDT
            crypto_balance (float): Số dư crypto
            crypto_symbol (str): Symbol crypto

        Returns:
            int: ID snapshot
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO balance_snapshots 
                   (session_id, timestamp, exchange, usdt_balance, crypto_balance, crypto_symbol)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, datetime.now(timezone.utc).isoformat(), exchange,
                 usdt_balance, crypto_balance, crypto_symbol)
            )
            return cursor.lastrowid

    def record_all_balances(self, session_id, usd_balances, crypto_balances, symbol):
        """
        Ghi lại snapshot số dư cho tất cả sàn.

        Args:
            session_id (int): ID phiên giao dịch
            usd_balances (dict): {exchange: usdt_amount}
            crypto_balances (dict): {exchange: crypto_amount}
            symbol (str): Cặp giao dịch
        """
        from utils.helpers import extract_base_asset
        crypto_symbol = extract_base_asset(symbol)

        with self._get_connection() as conn:
            timestamp = datetime.now(timezone.utc).isoformat()
            for exchange in usd_balances:
                conn.execute(
                    """INSERT INTO balance_snapshots 
                       (session_id, timestamp, exchange, usdt_balance, crypto_balance, crypto_symbol)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, timestamp, exchange,
                     usd_balances.get(exchange, 0),
                     crypto_balances.get(exchange, 0),
                     crypto_symbol)
                )

    def get_balance_history(self, session_id, exchange=None):
        """
        Lấy lịch sử số dư.

        Args:
            session_id (int): ID phiên giao dịch
            exchange (str, optional): Lọc theo sàn

        Returns:
            list[dict]: Danh sách snapshot
        """
        query = "SELECT * FROM balance_snapshots WHERE session_id = ?"
        params = [session_id]

        if exchange:
            query += " AND exchange = ?"
            params.append(exchange)

        query += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ─── Error Log ────────────────────────────────────────────────────

    def record_error(self, error_type, message, exchange=None,
                     session_id=None, details=None):
        """
        Ghi lại lỗi.

        Args:
            error_type (str): Loại lỗi
            message (str): Nội dung lỗi
            exchange (str, optional): Sàn giao dịch
            session_id (int, optional): ID phiên giao dịch
            details (str, optional): Chi tiết lỗi
        """
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO error_log 
                   (session_id, timestamp, error_type, exchange, message, details)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, datetime.now(timezone.utc).isoformat(),
                 error_type, exchange, message, details)
            )

    def get_errors(self, session_id=None, error_type=None, limit=100):
        """
        Lấy danh sách lỗi.

        Args:
            session_id (int, optional): Lọc theo phiên
            error_type (str, optional): Lọc theo loại lỗi
            limit (int): Số lượng tối đa

        Returns:
            list[dict]: Danh sách lỗi
        """
        query = "SELECT * FROM error_log WHERE 1=1"
        params = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if error_type:
            query += " AND error_type = ?"
            params.append(error_type)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ─── Statistics & Analytics ───────────────────────────────────────

    def get_overall_stats(self):
        """
        Lấy thống kê tổng hợp tất cả phiên.

        Returns:
            dict: Thống kê tổng hợp
        """
        with self._get_connection() as conn:
            session_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_sessions,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_sessions,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_sessions,
                    COALESCE(SUM(total_profit_usd), 0) as total_profit_usd,
                    COALESCE(SUM(total_fees_usd), 0) as total_fees_usd,
                    COALESCE(SUM(total_volume_usd), 0) as total_volume_usd,
                    COALESCE(SUM(trades_executed), 0) as total_trades_executed,
                    COALESCE(SUM(trades_failed), 0) as total_trades_failed,
                    COALESCE(SUM(opportunities_found), 0) as total_opportunities,
                    COALESCE(AVG(total_profit_pct), 0) as avg_profit_pct
                FROM sessions
            """).fetchone()

            trade_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COALESCE(AVG(profit_usd), 0) as avg_profit_per_trade_usd,
                    COALESCE(MAX(profit_usd), 0) as best_trade_usd,
                    COALESCE(MIN(profit_usd), 0) as worst_trade_usd,
                    COALESCE(AVG(profit_pct), 0) as avg_profit_per_trade_pct
                FROM trades WHERE status = 'executed'
            """).fetchone()

            return {
                **dict(session_stats),
                **dict(trade_stats)
            }

    def get_profit_by_exchange_pair(self):
        """
        Lấy lợi nhuận theo cặp sàn giao dịch.

        Returns:
            list[dict]: Thống kê theo cặp sàn
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    buy_exchange, sell_exchange,
                    COUNT(*) as trade_count,
                    SUM(profit_usd) as total_profit_usd,
                    AVG(profit_usd) as avg_profit_usd,
                    SUM(fee_usd) as total_fees_usd
                FROM trades WHERE status = 'executed'
                GROUP BY buy_exchange, sell_exchange
                ORDER BY total_profit_usd DESC
            """).fetchall()
            return [dict(row) for row in rows]

    def get_profit_by_symbol(self):
        """
        Lấy lợi nhuận theo cặp giao dịch.

        Returns:
            list[dict]: Thống kê theo cặp giao dịch
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    symbol,
                    COUNT(*) as trade_count,
                    SUM(profit_usd) as total_profit_usd,
                    AVG(profit_usd) as avg_profit_usd,
                    SUM(fee_usd) as total_fees_usd,
                    SUM(amount * buy_price) as total_volume_usd
                FROM trades WHERE status = 'executed'
                GROUP BY symbol
                ORDER BY total_profit_usd DESC
            """).fetchall()
            return [dict(row) for row in rows]

    def get_hourly_profit(self, session_id=None, days=7):
        """
        Lấy lợi nhuận theo giờ.

        Args:
            session_id (int, optional): Lọc theo phiên
            days (int): Số ngày lấy dữ liệu

        Returns:
            list[dict]: Lợi nhuận theo giờ
        """
        query = """
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp) as hour,
                COUNT(*) as trade_count,
                SUM(profit_usd) as total_profit_usd,
                SUM(fee_usd) as total_fees_usd
            FROM trades 
            WHERE status = 'executed'
              AND timestamp >= datetime('now', ?)
        """
        params = [f'-{days} days']

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " GROUP BY hour ORDER BY hour ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_daily_profit(self, days=30):
        """
        Lấy lợi nhuận theo ngày.

        Args:
            days (int): Số ngày lấy dữ liệu

        Returns:
            list[dict]: Lợi nhuận theo ngày
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    strftime('%Y-%m-%d', timestamp) as date,
                    COUNT(*) as trade_count,
                    SUM(profit_usd) as total_profit_usd,
                    SUM(fee_usd) as total_fees_usd,
                    AVG(profit_pct) as avg_profit_pct
                FROM trades 
                WHERE status = 'executed'
                  AND timestamp >= datetime('now', ?)
                GROUP BY date
                ORDER BY date ASC
            """, (f'-{days} days',)).fetchall()
            return [dict(row) for row in rows]

    def get_exchange_performance(self):
        """
        Lấy hiệu suất theo từng sàn giao dịch.

        Returns:
            list[dict]: Hiệu suất từng sàn
        """
        with self._get_connection() as conn:
            # Thống kê khi sàn là bên mua
            buy_stats = conn.execute("""
                SELECT 
                    buy_exchange as exchange,
                    'buy' as role,
                    COUNT(*) as trade_count,
                    SUM(profit_usd) as total_profit_usd,
                    AVG(buy_price) as avg_price
                FROM trades WHERE status = 'executed'
                GROUP BY buy_exchange
            """).fetchall()

            # Thống kê khi sàn là bên bán
            sell_stats = conn.execute("""
                SELECT 
                    sell_exchange as exchange,
                    'sell' as role,
                    COUNT(*) as trade_count,
                    SUM(profit_usd) as total_profit_usd,
                    AVG(sell_price) as avg_price
                FROM trades WHERE status = 'executed'
                GROUP BY sell_exchange
            """).fetchall()

            return {
                'buy_performance': [dict(row) for row in buy_stats],
                'sell_performance': [dict(row) for row in sell_stats]
            }
