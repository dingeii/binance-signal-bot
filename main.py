import os
import requests
import pandas as pd
from telegram import Bot
from datetime import datetime

# 从环境变量读取
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

def get_spot_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)
    return df

def get_futures_data():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)
    return df

def format_dual_table(left_df, right_df, left_title, right_title):
    result = f"{left_title:<24} | {right_title}\n"
    result += f"{'-'*24}|{'-'*24}\n"
    max_len = max(len(left_df), len(right_df))
    for i in range(max_len):
        l = left_df.iloc[i] if i < len(left_df) else None
        r = right_df.iloc[i] if i < len(right_df) else None
        left = f"{l['symbol']:<10} {l['priceChangePercent']:>+6.2f}% ${l['lastPrice']:.4g}" if l is not None else ""
        right = f"{r['symbol']:<10} {r['priceChangePercent']:>+6.2f}% ${r['lastPrice']:.4g}" if r is not None else ""
        result += f"{left:<24} | {right}\n"
    return result

def send_to_telegram():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")
        return

    try:
        spot = get_spot_data()
        fut = get_futures_data()
    except Exception as e:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ 获取币安行情失败：{e}")
        return

    spot_gainers = spot.sort_values("priceChangePercent", ascending=False).head(10)
    spot_losers = spot.sort_values("priceChangePercent").head(10)
    fut_gainers = fut.sort_values("priceChangePercent", ascending=False).head(10)
    fut_losers = fut.sort_values("priceChangePercent").head(10)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    msg = "📊 *币安 24H 涨跌榜（USDT）*\n\n"

    msg += "🔸 现货涨跌榜\n"
    msg += "```text\n"
    msg += format_dual_table(spot_gainers, spot_losers, "涨幅榜", "跌幅榜")
    msg += "```\n"

    msg += "🔸 合约涨跌榜\n"
    msg += "```text\n"
    msg += format_dual_table(fut_gainers, fut_losers, "涨幅榜", "跌幅榜")
    msg += "```\n"

    msg += f"📅 更新时间：{now}"

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')

if __name__ == "__main__":
    send_to_telegram()
