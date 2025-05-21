import os
import requests
import pandas as pd
from telegram import Bot
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_random, retry_if_exception_type

# 读取环境变量
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("请先设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")

bot = Bot(token=TELEGRAM_TOKEN)

@retry(
    stop=stop_after_attempt(5),  # 最多重试5次
    wait=wait_random(min=1, max=3),  # 每次间隔1-3秒
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True
)
def fetch_binance_data(url: str):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_spot_data():
    info = fetch_binance_data("https://api.binance.com/api/v3/exchangeInfo")
    if 'symbols' not in info:
        raise RuntimeError("现货 exchangeInfo 响应格式错误")
    active_symbols = {s['symbol'] for s in info['symbols'] if s['status'] == 'TRADING'}
    data = fetch_binance_data("https://api.binance.com/api/v3/ticker/24hr")
    df = pd.DataFrame(data)
    df = df[df['symbol'].isin(active_symbols)]
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')
    df['lastPrice'] = pd.to_numeric(df['lastPrice'], errors='coerce')
    return df.dropna(subset=['priceChangePercent', 'lastPrice'])

def get_futures_data():
    info = fetch_binance_data("https://fapi.binance.com/fapi/v1/exchangeInfo")
    if 'symbols' not in info:
        raise RuntimeError("合约 exchangeInfo 响应格式错误")
    active_symbols = {s['symbol'] for s in info['symbols'] if s['status'] == 'TRADING'}
    data = fetch_binance_data("https://fapi.binance.com/fapi/v1/ticker/24hr")
    df = pd.DataFrame(data)
    df = df[df['symbol'].isin(active_symbols)]
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')
    df['lastPrice'] = pd.to_numeric(df['lastPrice'], errors='coerce')
    return df.dropna(subset=['priceChangePercent', 'lastPrice'])

def format_table(df):
    lines = []
    for _, row in df.iterrows():
        symbol = row['symbol']
        pct = row['priceChangePercent']
        last = row['lastPrice']
        sign = '+' if pct >= 0 else ''
        lines.append(f"{symbol:<12} {sign}{pct:>6.2f}%   ${last:.4g}")
    return "\n".join(lines)

def send_long_msg(text, parse_mode=None, chunk_size=4000):
    for i in range(0, len(text), chunk_size):
undefined
