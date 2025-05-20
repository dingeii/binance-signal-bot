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

def format_volume_table(left_df, right_df, left_title, right_title):
    result = f"{left_title:<28} | {right_title}\n"
    result += f"{'-'*28}|{'-'*24}\n"
    max_len = max(len(left_df), len(right_df))
    for i in range(max_len):
        l = left_df.iloc[i] if i < len(left_df) else None
        r = right_df.iloc[i] if i < len(right_df) else None
        left = f"{l['symbol']:<10} {l['quoteVolume']:,.0f} ${l['lastPrice']:.4g}" if l is not None else ""
        right = f"{r['symbol']:<10} {r['quoteVolume']:,.0f} ${r['lastPrice']:.4g}" if r is not None else ""
        result += f"{left:<28} | {right}\n"
    return result

def format_anomaly_side_by_side(spot_df, fut_df):
    spot_gainers = spot_df[spot_df['priceChangePercent'] >= 100]
    spot_losers = spot_df[spot_df['priceChangePercent'] <= -60]
    fut_gainers = fut_df[fut_df['priceChangePercent'] >= 100]
    fut_losers = fut_df[fut_df['priceChangePercent'] <= -60]

    spot_list = list(spot_gainers.itertuples()) + list(spot_losers.itertuples())
    fut_list = list(fut_gainers.itertuples()) + list(fut_losers.itertuples())
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

def format_anomaly_volume_side_by_side(spot_df, fut_df, gain=True):
    if gain:
        spot_filtered = spot_df[(spot_df['priceChangePercent'] >= 100)]
        fut_filtered = fut_df[(fut_df['priceChangePercent'] >= 100)]
        title_left = "现货异动买入榜"
        title_right = "合约异动买入榜"
    else:
        spot_filtered = spot_df[(spot_df['priceChangePercent'] <= -60)]
        fut_filtered = fut_df[(fut_df['priceChangePercent'] <= -60)]
        title_left = "现货异动卖出榜"
        title_right = "合约异动卖出榜"

    spot_sorted = spot_filtered.sort_values('quoteVolume', ascending=False).head(10)
    fut_sorted = fut_filtered.sort_values('quoteVolume', ascending=False).head(10)

    header = f"{title_left:<28} | {title_right}\n"
    header += f"{'-'*28}|{'-'*24}\n"

    max_len = max(len(spot_sorted), len(fut_sorted))
    rows = []
    for i in range(max_len):
        l = spot_sorted.iloc[i] if i < len(spot_sorted) else None
        r = fut_sorted.iloc[i] if i < len(fut_sorted) else None
        left = f"{l['symbol']:<10} {l['quoteVolume']:,.0f} ${l['lastPrice']:.4g}" if l is not None else ""
        right = f"{r['symbol']:<10} {r['quoteVolume']:,.0f} ${r['lastPrice']:.4g}" if r is not None else ""
        rows.append(f"{left:<28} | {right}")
    return header + "\n".join(rows) + "\n"

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

    now = get_beijing_time()

    msg = "📊 *币安 24H 涨跌榜（USDT）*\n\n"

    msg += "🚨 异动涨跌榜（涨≥+100%，跌≤-60%）\n"
    msg += "```text\n"
    msg += format_anomaly_side_by_side(spot, fut)
    msg += "```\n"

    msg += "💰 净买入量榜单（成交额）\n"
    msg += "```text\n"
    msg += format_volume_table(
        spot.sort_values('quoteVolume', ascending=False).head(10),
        fut.sort_values('quoteVolume', ascending=False).head(10),
        "现货买入榜", "合约买入榜")
    msg += "```\n"

    msg += "📉 净卖出量榜单（成交额）\n"
    msg += "```text\n"
    msg += format_volume_table(
        spot.sort_values('quoteVolume').head(10),
        fut.sort_values('quoteVolume').head(10),
        "现货卖出榜", "合约卖出榜")
    msg += "```\n"

    msg += "🚀 异动买入榜（涨≥+100%且成交额大）\n"
    msg += "```text\n"
    msg += format_anomaly_volume_side_by_side(spot, fut, gain=True)
    msg += "```\n"

    msg += "🔻 异动卖出榜（跌≤-60%且成交额大）\n"
    msg += "```text\n"
    msg += format_anomaly_volume_side_by_side(spot, fut, gain=False)
    msg += "```\n"

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
