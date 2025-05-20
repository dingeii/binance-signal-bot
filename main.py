import requests
import pandas as pd
import logging
from telegram import Bot
from datetime import datetime
import os

# === 环境变量从 GitHub Secrets 读取 ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === 日志设置 ===
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_TOKEN)

# === 获取数据函数 ===

def get_binance_data(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)
        df = df[df['symbol'].str.endswith('USDT')]
        df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')
        df['lastPrice'] = pd.to_numeric(df['lastPrice'], errors='coerce')
        df = df.dropna(subset=['priceChangePercent', 'lastPrice'])
        return df
    except Exception as e:
        logging.error(f"❌ 获取数据失败: {e}")
        return pd.DataFrame()

def get_spot_data():
    return get_binance_data("https://api.binance.com/api/v3/ticker/24hr")

def get_futures_data():
    return get_binance_data("https://fapi.binance.com/fapi/v1/ticker/24hr")

def get_top_movers(df, top_n=10):
    gainers = df.sort_values("priceChangePercent", ascending=False).head(top_n)
    losers = df.sort_values("priceChangePercent").head(top_n)
    return gainers, losers

def format_side_by_side(left_df, right_df, left_title, right_title):
    result = f"🔹 {left_title:<28} | 🔸 {right_title}\n"
    result += f"{'-'*30}|{'-'*30}\n"
    for i in range(max(len(left_df), len(right_df))):
        l = left_df.iloc[i] if i < len(left_df) else None
        r = right_df.iloc[i] if i < len(right_df) else None
        left_row = f"{l['symbol']:<10} {l['priceChangePercent']:>+6.2f}% ${l['lastPrice']:.4g}" if l is not None else ""
        right_row = f"{r['symbol']:<10} {r['priceChangePercent']:>+6.2f}% ${r['lastPrice']:.4g}" if r is not None else ""
        result += f"{left_row:<30}| {right_row}\n"
    return result

def format_anomaly_list(spot_df, fut_df):
    combined = pd.concat([spot_df, fut_df])
    combined['priceChangePercent'] = pd.to_numeric(combined['priceChangePercent'], errors='coerce')
    combined['lastPrice'] = pd.to_numeric(combined['lastPrice'], errors='coerce')

    gainers = combined[combined['priceChangePercent'] >= 100]
    losers = combined[combined['priceChangePercent'] <= -60]

    result = ""
    if not gainers.empty or not losers.empty:
        result += "🚨 *异动榜（涨幅 ≥ +100%，跌幅 ≤ -60%）*\n"
        result += "```\n"
        for _, row in gainers.iterrows():
            result += f"🚀 {row['symbol']:<10} {row['priceChangePercent']:>+6.2f}% ${row['lastPrice']:.4g}\n"
        for _, row in losers.iterrows():
            result += f"🔻 {row['symbol']:<10} {row['priceChangePercent']:>+6.2f}% ${row['lastPrice']:.4g}\n"
        result += "```\n\n"
    return result

def send_to_telegram():
    spot = get_spot_data()
    fut = get_futures_data()

    if spot.empty or fut.empty:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ 获取币安行情失败，请检查网络或API限制。")
        return

    spot_gainers, spot_losers = get_top_movers(spot)
    fut_gainers, fut_losers = get_top_movers(fut)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    msg = "📊 *币安 24H 涨跌榜（USDT）*\n\n"
    msg += format_anomaly_list(spot, fut)
    msg += "```text\n"
    msg += format_side_by_side(spot_gainers, fut_gainers, "现货涨幅榜", "合约涨幅榜")
    msg += "\n"
    msg += format_side_by_side(spot_losers, fut_losers, "现货跌幅榜", "合约跌幅榜")
    msg += "```\n"
    msg += f"📅 更新时间：{now}"

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')

if __name__ == "__main__":
    send_to_telegram()
