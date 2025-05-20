import os
import requests
import pandas as pd
from telegram import Bot
from datetime import datetime, timedelta

# 读取 Telegram token 和 chat ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)


def get_spot_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)
    return df


def get_futures_data():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)
    return df


def format_single_table(df, title, is_up=True):
    rows = []
    for _, row in df.iterrows():
        sign = "🚀" if is_up else "🔻"
        percent = f"{row['priceChangePercent']:+.1f}%"
        rows.append(f"{sign} {row['symbol']:<10} {percent:>7}  ${row['lastPrice']:.4g}")
    return f"{title}\n" + "\n".join(rows) + "\n"


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

    # 北京时间
    now = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    msg = "📊 *币安 USDT 涨跌榜（24H）*\n\n"

    msg += "🔸 *现货涨幅榜*\n"
    msg += "```text\n" + format_single_table(spot_gainers, "") + "```\n"

    msg += "🔸 *现货跌幅榜*\n"
    msg += "```text\n" + format_single_table(spot_losers, "", is_up=False) + "```\n"

    msg += "🔸 *合约涨幅榜*\n"
    msg += "```text\n" + format_single_table(fut_gainers, "") + "```\n"

    msg += "🔸 *合约跌幅榜*\n"
    msg += "```text\n" + format_single_table(fut_losers, "", is_up=False) + "```\n"

    msg += f"\n🕒 更新时间：{now} (北京时间)"

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")



if __name__ == "__main__":
    send_to_telegram()
