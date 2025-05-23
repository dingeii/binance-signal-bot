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

def fetch_okx_data(inst_type):
    url = f"https://www.okx.com/api/v5/market/tickers?instType={inst_type}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data['code'] != '0':
        raise RuntimeError(f"OKX API 错误: {data['msg']}")
    return data['data']

def process_data(data):
    df = pd.DataFrame(data)
    df = df[df['instId'].str.endswith('USDT')]
    df['last'] = pd.to_numeric(df['last'], errors='coerce')
    df['priceChangePercent'] = pd.to_numeric(df['changeRate'], errors='coerce') * 100  # 小数转百分比
    return df.dropna(subset=['priceChangePercent', 'last'])

def format_table(df):
    lines = []
    for _, row in df.iterrows():
        sign = '+' if row['priceChangePercent'] >= 0 else ''
        lines.append(f"{row['instId']:<15} {sign}{row['priceChangePercent']:6.2f}%  ${row['last']:.4g}")
    return "\n".join(lines)

def send_to_telegram():
    try:
        spot_data = fetch_okx_data("SPOT")
        fut_data = fetch_okx_data("FUTURES")
        spot_df = process_data(spot_data)
        fut_df = process_data(fut_data)

        spot_gainers = spot_df.sort_values("priceChangePercent", ascending=False).head(10)
        spot_losers = spot_df.sort_values("priceChangePercent").head(10)
        fut_gainers = fut_df.sort_values("priceChangePercent", ascending=False).head(10)
        fut_losers = fut_df.sort_values("priceChangePercent").head(10)

        now = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M (UTC+8)")

        msg = "📊 *OKX 24H 涨跌榜（USDT）*\n\n"
        msg += "🔸 *现货涨幅榜*\n```text\n" + format_table(spot_gainers) + "\n```\n"
        msg += "🔸 *现货跌幅榜*\n```text\n" + format_table(spot_losers) + "\n```\n"
        msg += "🔸 *合约涨幅榜*\n```text\n" + format_table(fut_gainers) + "\n```\n"
        msg += "🔸 *合约跌幅榜*\n```text\n" + format_table(fut_losers) + "\n```\n"
        msg += f"📅 更新时间：{now}"

    except Exception as e:
        msg = f"❌ 获取行情失败：{e}"

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')

if __name__ == "__main__":
    send_to_telegram()
