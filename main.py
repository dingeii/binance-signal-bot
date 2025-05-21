import os
import requests
import pandas as pd
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")

bot = Bot(token=TELEGRAM_TOKEN)

def fetch_binance_data(api_url: str, info_url: str) -> pd.DataFrame:
    try:
        info_resp = requests.get(info_url, timeout=10)
        info_json = info_resp.json()
        symbols = {s['symbol'] for s in info_json.get('symbols', []) if s.get('status') == 'TRADING'}

        data_resp = requests.get(api_url, timeout=10)
        data_resp.raise_for_status()
        df = pd.DataFrame(data_resp.json())

        df = df[df['symbol'].isin(symbols)]
        df = df[df['symbol'].str.endswith('USDT')]
        df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')
        df['lastPrice'] = pd.to_numeric(df['lastPrice'], errors='coerce')
        df = df.dropna(subset=['priceChangePercent', 'lastPrice'])
        return df
    except Exception as e:
        raise RuntimeError(f"获取数据失败: {e}")

def get_spot_data():
    return fetch_binance_data(
        "https://api.binance.com/api/v3/ticker/24hr",
        "https://api.binance.com/api/v3/exchangeInfo"
    )

def get_futures_data():
    return fetch_binance_data(
        "https://fapi.binance.com/fapi/v1/ticker/24hr",
        "https://fapi.binance.com/fapi/v1/exchangeInfo"
    )

def format_table(df):
    lines = []
    for _, row in df.iterrows():
        sign = '+' if row['priceChangePercent'] >= 0 else ''
        lines.append(f"{row['symbol']:<12} {sign}{row['priceChangePercent']:>6.2f}%   ${row['lastPrice']:.4g}")
    return "\n".join(lines)

def build_message() -> str:
    try:
        spot = get_spot_data()
        fut = get_futures_data()
    except Exception as e:
        return f"❌ 获取行情失败：{e}"

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

def send_to_telegram():
    msg = build_message()
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')

def handle_run(update: Update, context: CallbackContext):
    msg = build_message()
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')

def main():
    if os.getenv("RUN_ONCE") == "true":
        send_to_telegram()
        return

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("run", handle_run))

    print("🤖 Bot 正在监听 /run 命令...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
