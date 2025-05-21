import os
import requests
import pandas as pd
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime, timedelta

# 读取环境变量
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ 请先设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")

bot = Bot(token=TELEGRAM_TOKEN)

# ---------- 数据获取部分 ----------
def get_spot_data():
    url_info = "https://api.binance.com/api/v3/exchangeInfo"
    url_data = "https://api.binance.com/api/v3/ticker/24hr"

    info_resp = requests.get(url_info, timeout=10)
    info_json = info_resp.json()
    if 'symbols' not in info_json:
        raise ValueError(f"Binance现货 exchangeInfo 异常返回：{info_json}")

    active_symbols = {s['symbol'] for s in info_json['symbols'] if s['status'] == 'TRADING'}

    data_resp = requests.get(url_data, timeout=10)
    df = pd.DataFrame(data_resp.json())
    df = df[df['symbol'].isin(active_symbols)]
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)

    return df

def get_futures_data():
    url_info = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    url_data = "https://fapi.binance.com/fapi/v1/ticker/24hr"

    info_resp = requests.get(url_info, timeout=10)
    info_json = info_resp.json()
    if 'symbols' not in info_json:
        raise ValueError(f"Binance合约 exchangeInfo 异常返回：{info_json}")

    active_symbols = {s['symbol'] for s in info_json['symbols'] if s['status'] == 'TRADING'}

    data_resp = requests.get(url_data, timeout=10)
    df = pd.DataFrame(data_resp.json())
    df = df[df['symbol'].isin(active_symbols)]
    df = df[df['symbol'].str.endswith('USDT')]
    df['priceChangePercent'] = df['priceChangePercent'].astype(float)
    df['lastPrice'] = df['lastPrice'].astype(float)

    return df

def format_table(df):
    lines = []
    for _, row in df.iterrows():
        sign = '+' if row['priceChangePercent'] >= 0 else ''
        lines.append(f"{row['symbol']:<12} {sign}{row['priceChangePercent']:>6.2f}%   ${row['lastPrice']:.4g}")
    return "\n".join(lines)

# ---------- 主消息生成 ----------
def build_message():
    try:
        spot = get_spot_data()
        fut = get_futures_data()
    except Exception as e:
        return f"❌ 获取币安行情失败：\n{str(e)}"

    spot_gainers = spot.sort_values("priceChangePercent", ascending=False).head(10)
    spot_losers = spot.sort_values("priceChangePercent").head(10)
    fut_gainers = fut.sort_values("priceChangePercent", ascending=False).head(10)
    fut_losers = fut.sort_values("priceChangePercent").head(10)

    now = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M (UTC+8)")

    msg = "📊 *币安 24H 涨跌榜（USDT）*\n\n"
    msg += "🔸 *现货涨幅榜*\n```text\n" + format_table(spot_gainers) + "\n```\n"
    msg += "🔸 *现货跌幅榜*\n```text\n" + format_table(spot_losers) + "\n```\n"
    msg += "🔸 *合约涨幅榜*\n```text\n" + format_table(fut_gainers) + "\n```\n"
    msg += "🔸 *合约跌幅榜*\n```text\n" + format_table(fut_losers) + "\n```\n"
    msg += f"📅 更新时间：{now}"
    return msg

# ---------- 自动推送 ----------
def send_to_telegram():
    message = build_message()
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')

# ---------- 机器人命令监听 ----------
def handle_run_command(update: Update, context: CallbackContext):
    msg = build_message()
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')

def main():
    # 检查是否是 GitHub Actions 调用
    if os.getenv("RUN_ONCE"):
        send_to_telegram()
        return

    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("run", handle_run_command))
    updater.start_polling()
    print("🤖 Bot 正在监听 /run 命令...")
    updater.idle()

if __name__ == "__main__":
    main()
