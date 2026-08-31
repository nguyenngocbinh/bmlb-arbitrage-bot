"""Quản lý profile khởi chạy bot được cấu hình từ dashboard."""
import json
import os
from typing import Any

from configs import BOT_MODES, SUPPORTED_EXCHANGES


PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
    'bot_launch_profile.json',
)

DEFAULT_PROFILE: dict[str, Any] = {
    'mode': 'fake-money',
    'renew_time': 15,
    'usdt_amount': 1000.0,
    'exchanges': ['binance', 'kucoin', 'okx'],
    'symbols': ['BTC/USDT'],
    'dry_run': True,
    'no_recovery': True,
}


def validate_bot_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Kiểm tra và chuẩn hóa profile cấu hình khởi chạy bot."""
    mode = profile.get('mode')
    renew_time = profile.get('renew_time')
    usdt_amount = profile.get('usdt_amount')
    exchanges = profile.get('exchanges')
    symbols = profile.get('symbols')

    if mode not in BOT_MODES:
        raise ValueError(f"Chế độ không hợp lệ: {mode}")
    if not isinstance(renew_time, int) or renew_time < 1:
        raise ValueError("Thời gian làm mới phải là số nguyên dương")
    if not isinstance(usdt_amount, (int, float)) or usdt_amount <= 0:
        raise ValueError("Vốn USDT phải lớn hơn 0")
    if not isinstance(exchanges, list) or len(exchanges) != 3:
        raise ValueError("Cần chọn đúng ba sàn giao dịch")
    if len(set(exchanges)) != len(exchanges) or any(
            exchange not in SUPPORTED_EXCHANGES for exchange in exchanges):
        raise ValueError("Sàn giao dịch không được hỗ trợ hoặc bị trùng")
    if not isinstance(symbols, list) or not symbols or any(
            not isinstance(symbol, str) or not symbol.strip() for symbol in symbols):
        raise ValueError("Cần nhập ít nhất một cặp giao dịch")

    return {
        'mode': mode,
        'renew_time': renew_time,
        'usdt_amount': float(usdt_amount),
        'exchanges': exchanges,
        'symbols': [symbol.strip().upper() for symbol in symbols],
        'dry_run': bool(profile.get('dry_run', False)),
        'no_recovery': bool(profile.get('no_recovery', True)),
    }


def load_bot_profile() -> dict[str, Any]:
    """Đọc profile đã lưu hoặc trả về cấu hình an toàn mặc định."""
    if not os.path.exists(PROFILE_PATH):
        return DEFAULT_PROFILE.copy()

    with open(PROFILE_PATH, 'r', encoding='utf-8') as profile_file:
        return validate_bot_profile(json.load(profile_file))


def save_bot_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Kiểm tra và lưu profile cấu hình khởi chạy bot."""
    validated_profile = validate_bot_profile(profile)
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    temporary_path = f"{PROFILE_PATH}.tmp"
    with open(temporary_path, 'w', encoding='utf-8') as profile_file:
        json.dump(validated_profile, profile_file, ensure_ascii=True, indent=2)
    os.replace(temporary_path, PROFILE_PATH)
    return validated_profile
