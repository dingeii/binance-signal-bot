import os
import requests
import pandas as pd
from telegram import Bot
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("请先设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")

bot = Bot(token=TELEGRAM_TOKEN)

def fetch_binance_data(endpoint):
    url = f"https://api.binance.com/api/v3/ticker/24hr" if endpoint == "spot" else f"https://fapi.binance.com/fapi/v1/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

def process_data(data):
    df = pd.DataFrame(data)
    df = df[df['symbol'].str.endswith('USDT')]
    df['lastPrice'] = pd.to_numeric(df['lastPrice'], errors='coerce')
    df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')
    return df.dropna(subset=['priceChangePercent', 'lastPrice'])

def format_table(df):
    lines = []
    for _, row in df.iterrows():
        sign = '+' if row['priceChangePercent'] >= 0 else ''
        lines.append(f"{row['symbol']:<12} {sign}{row['priceChangePercent']:6.2f}%  ${row['lastPrice']:.4g}")
    return "\n".join(lines)

def send_to_telegram():
    try:
        spot_data = fetch_binance_data("spot")
        fut_data = fetch_binance_data("futures")

        spot_df = process_data(spot_data)
        fut_df = process_data(fut_data)

        spot_gainers = spot_df.sort_values("priceChangePercent", ascending=False).head(10)
        spot_losers = spot_df.sort_values("priceChangePercent").head(10)
        fut_gainers = fut_df.sort_values("priceChangePercent", ascending=False).head(10)
        fut_losers = fut_df.sort_values("priceChangePercent").head(10)

        now = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M (UTC+8)")

        msg = "📊 *Binance 24H 涨跌榜（USDT）*\n\n"
        msg += "🔸 *现货涨幅榜*\n```text\n" + format_table(spot_gainers) + "\n```\n"
        msg += "🔸 *现货跌幅榜*\n```text\n" + format_table(spot_losers) + "\n```\n"
        msg += "🔸 *合约涨幅榜*\n```text\n" + format_table(fut_gainers) + "\n```\n"
        msg += "🔸 *合约跌幅榜*\n```text\n" + format_table(fut_losers) + "\n```\n"
        msg += f"📅 更新时间：{now}"

    except Exception as e:
        msg = f"❌ 获取行情失败：{e}"

    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
        print("✅ Telegram 消息发送成功")
    except Exception as e:
        print(f"❌ Telegram 发送消息失败: {e}")

if __name__ == "__main__":
    send_to_telegram()
