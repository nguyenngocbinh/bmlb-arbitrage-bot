"""
Tệp cấu hình chứa các thông số cấu hình chung cho bot giao dịch.
"""
import os
from dotenv import load_dotenv

# Tải biến môi trường từ tệp .env
load_dotenv()

# Cấu hình chung
PYTHON_COMMAND = os.getenv('PYTHON_COMMAND', 'python')
ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM', 'false').lower() == 'true'
ENABLE_CTRL_C_HANDLING = os.getenv('ENABLE_CTRL_C_HANDLING', 'false').lower() == 'true'

# Tiêu chí lợi nhuận
PROFIT_CRITERIA_PCT = 0  # % lợi nhuận tối thiểu
PROFIT_CRITERIA_USD = 0  # Lợi nhuận USD tối thiểu

# Thông số giao dịch
BETTER_FILL_LESS_PROFITS = True  # Điều chỉnh fill để giảm lợi nhuận
FIRST_ORDERS_FILL_TIMEOUT = 3600  # Thời gian chờ tối đa để fill đơn hàng đầu tiên (giây)

# Danh sách các sàn giao dịch hỗ trợ
SUPPORTED_EXCHANGES = ['kucoin', 'binance', 'bybit', 'okx', 'kucoinfutures']

# Phí giao dịch của từng sàn
EXCHANGE_FEES = {
    'binance': {'give': 0.001, 'receive': 0.001},
    'kucoin': {'give': 0.001, 'receive': 0.001},
    'okx': {'give': 0.0008, 'receive': 0.001},
    'bybit': {'give': 0.001, 'receive': 0.001},
    'kucoinfutures': {'give': 0.001, 'receive': 0.001},
    # Có thể thêm nhiều sàn khác nếu cần
}

# Cấu hình Delta-Neutral
DEFAULT_FUTURES_EXCHANGE = 'kucoinfutures'  # Sàn futures mặc định
DEFAULT_LEVERAGE = 1  # Đòn bẩy mặc định
SHORT_AMOUNT_RATIO = 1/3  # Tỷ lệ số tiền để mở vị thế short (1/3 tổng số tiền)
MIN_FUTURES_QUANTITY = 1  # Số lượng tối thiểu cho giao dịch futures

# Chế độ bot
BOT_MODES = ['fake-money', 'classic', 'delta-neutral']

# Đường dẫn tệp tin
BALANCE_FILE = 'balance.txt'
START_BALANCE_FILE = 'start_balance.txt'
SYMBOL_FILE = 'symbol.txt'

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'arbitrage.db')