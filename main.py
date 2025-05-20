import os
import requests
import pandas as pd
from telegram import Bot
from datetime import datetime
import pytz

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

def get_beijing_time():
    tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

def get_spot_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)
    df['quoteVolume'] = df['quoteVolume'].astype(float)
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
    df['quoteVolume'] = df['quoteVolume'].astype(float)
    return df

def format_anomaly_side_by_side(spot_df, fut_df):
    spot_gainers = spot_df[(spot_df['priceChangePercent'] >= 100) | (spot_df['priceChangePercent'] <= -60)]
    fut_gainers = fut_df[(fut_df['priceChangePercent'] >= 100) | (fut_df['priceChangePercent'] <= -60)]

    spot_list = list(spot_gainers.itertuples())
    fut_list = list(fut_gainers.itertuples())
    max_len = max(len(spot_list), len(fut_list))

    header = f"现货异动涨跌榜       | 合约异动涨跌榜\n"
    header += f"{'-'*24}|{'-'*24}\n"

    rows = []
    for i in range(max_len):
        left = ""
        right = ""
        if i < len(spot_list):
            row = spot_list[i]
            sign = "🚀" if row.priceChangePercent >= 0 else "🔻"
            left = f"{sign} {row.symbol:<10} {row.priceChangePercent:>+6.2f}% ${row.lastPrice:.4g}"
        if i < len(fut_list):
            row = fut_list[i]
            sign = "🚀" if row.priceChangePercent >= 0 else "🔻"
            right = f"{sign} {row.symbol:<10} {row.priceChangePercent:>+6.2f}% ${row.lastPrice:.4g}"
        rows.append(f"{left:<24} | {right}")
    return header + "\n".join(rows) + "\n"

def format_combined_volume_table(df_spot, df_fut, title_spot, title_fut):
    def mark_anomaly(row):
        if row['priceChangePercent'] >= 100 or row['priceChangePercent'] <= -60:
            return "🔥"
        return ""

    spot = df_spot.copy()
    fut = df_fut.copy()

    spot['mark'] = spot.apply(mark_anomaly, axis=1)
    fut['mark'] = fut.apply(mark_anomaly, axis=1)

    spot_top = spot.sort_values('quoteVolume', ascending=False).head(10)
    fut_top = fut.sort_values('quoteVolume', ascending=False).head(10)

    header = f"{title_spot:<24} | {title_fut}\n"
    header += f"{'-'*24}|{'-'*24}\n"

    max_len = max(len(spot_top), len(fut_top))
    lines = []
    for i in range(max_len):
        left = ""
        right = ""
        if i < len(spot_top):
            row = spot_top.iloc[i]
            left = f"{row['mark']} {row['symbol']:<10} {row['priceChangePercent']:>+6.2f}% ${row['lastPrice']:.4g}"
        if i < len(fut_top):
            row = fut_top.iloc[i]
            right = f"{row['mark']} {row['symbol']:<10} {row['priceChangePercent']:>+6.2f}% ${row['lastPrice']:.4g}"
        lines.append(f"{left:<24} | {right}")
    return header + "\n".join(lines) + "\n"

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

    now = get_beijing_time()

    msg = "📊 *币安 24H 涨跌榜（USDT）*\n\n"

    msg += "🚨 异动涨跌榜（涨≥+100%，跌≤-60%）\n"
    msg += "```text\n"
    msg += format_anomaly_side_by_side(spot, fut)
    msg += "```\n"

    msg += "💰 净买入量榜单（含异动🔥标记）\n"
    msg += "```text\n"
    msg += format_combined_volume_table(
        spot.sort_values('priceChangePercent', ascending=False),
        fut.sort_values('priceChangePercent', ascending=False),
        "现货买入榜", "合约买入榜")
    msg += "```\n"

    msg += "📉 净卖出量榜单（含异动🔥标记）\n"
    msg += "```text\n"
    msg += format_combined_volume_table(
        spot.sort_values('priceChangePercent'),
        fut.sort_values('priceChangePercent'),
        "现货卖出榜", "合约卖出榜")
    msg += "```\n"

    msg += f"*更新时间*：{now}"

    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=msg,
        parse_mode='Markdown'
    )
    print("✅ 消息发送成功")

if __name__ == "__main__":
    send_to_telegram()
