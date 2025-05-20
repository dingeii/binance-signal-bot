import os
import requests
import matplotlib.pyplot as plt
from io import BytesIO
import telegram
import pandas as pd
import time

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise Exception("请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")

bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
HEADERS = {"User-Agent": "Mozilla/5.0"}

def request_with_retry(url, max_retries=3, timeout=10):
    for i in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"请求失败，重试 {i+1}/{max_retries}，错误: {e}")
            time.sleep(2)
    print("请求多次失败，放弃")
    return None

def get_spot_data():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    data = request_with_retry(url)
    if data is None:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(data)
    df = df[df['symbol'].str.endswith("USDT")]

    df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')

    gainers = df.sort_values(by='priceChangePercent', ascending=False).head(10)
    losers = df.sort_values(by='priceChangePercent').head(10)
    return gainers, losers

def plot_top_movers(gainers, losers):
    plt.figure(figsize=(12,6))
    plt.bar(gainers['symbol'], gainers['priceChangePercent'], color='green', label='涨幅榜Top10')
    plt.bar(losers['symbol'], losers['priceChangePercent'], color='red', label='跌幅榜Top10')
    plt.axhline(0, color='black', linewidth=0.8)
    plt.ylabel('24小时涨跌幅 (%)')
    plt.title('币安现货USDT交易对涨跌榜Top10')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return buf

def send_to_telegram():
    gainers, losers = get_spot_data()
    if gainers.empty or losers.empty:
        msg = "❌ 获取币安现货行情失败，请检查网络或API限制。"
        print(msg)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return

    msg = "📈 币安现货USDT交易对涨跌榜Top10\n\n"
    msg += "🚀 涨幅榜Top10:\n"
    for _, row in gainers.iterrows():
        msg += f"{row['symbol']}: {row['priceChangePercent']:.2f}%\n"

    msg += "\n📉 跌幅榜Top10:\n"
    for _, row in losers.iterrows():
        msg += f"{row['symbol']}: {row['priceChangePercent']:.2f}%\n"

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    img_buf = plot_top_movers(gainers, losers)
    bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=img_buf)

if __name__ == "__main__":
    send_to_telegram()
