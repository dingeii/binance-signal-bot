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
            print(f"请求状态码: {resp.status_code} 网址: {url}")
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

def get_futures_data():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    data = request_with_retry(url)
    if data is None:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(data)
    df = df[df['symbol'].str.endswith("USDT")]
    df['priceChangePercent'] = pd.to_numeric(df['priceChangePercent'], errors='coerce')

    gainers = df.sort_values(by='priceChangePercent', ascending=False).head(10)
    losers = df.sort_values(by='priceChangePercent').head(10)
    return gainers, losers

def plot_two_charts(spot_gainers, spot_losers, fut_gainers, fut_losers):
    fig, axs = plt.subplots(2, 1, figsize=(14, 10))
    
    # 现货涨跌幅图
    axs[0].bar(spot_gainers['symbol'], spot_gainers['priceChangePercent'], color='green', label='现货涨幅Top10')
    axs[0].bar(spot_losers['symbol'], spot_losers['priceChangePercent'], color='red', label='现货跌幅Top10')
    axs[0].axhline(0, color='black', linewidth=0.8)
    axs[0].set_title("币安现货USDT交易对涨跌榜Top10")
    axs[0].set_ylabel("涨跌幅 (%)")
    axs[0].legend()
    axs[0].tick_params(axis='x', rotation=45)
    
    # 合约涨跌幅图
    axs[1].bar(fut_gainers['symbol'], fut_gainers['priceChangePercent'], color='green', label='合约涨幅Top10')
    axs[1].bar(fut_losers['symbol'], fut_losers['priceChangePercent'], color='red', label='合约跌幅Top10')
    axs[1].axhline(0, color='black', linewidth=0.8)
    axs[1].set_title("币安永续合约USDT交易对涨跌榜Top10")
    axs[1].set_ylabel("涨跌幅 (%)")
    axs[1].legend()
    axs[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return buf

def send_to_telegram():
    spot_gainers, spot_losers = get_spot_data()
    fut_gainers, fut_losers = get_futures_data()

    if spot_gainers.empty or spot_losers.empty:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ 获取币安现货行情失败，请检查网络或API限制。")
        return
    if fut_gainers.empty or fut_losers.empty:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ 获取币安合约行情失败，请检查网络或API限制。")
        return

    msg = "📈 币安现货USDT交易对涨跌榜Top10\n"
    msg += "🚀 涨幅榜:\n"
    for _, row in spot_gainers.iterrows():
        msg += f"{row['symbol']}: {row['priceChangePercent']:.2f}%\n"

    msg += "\n📉 跌幅榜:\n"
    for _, row in spot_losers.iterrows():
        msg += f"{row['symbol']}: {row['priceChangePercent']:.2f}%\n"

    msg += "\n\n🔥 币安永续合约USDT交易对涨跌榜Top10\n"
    msg += "🚀 涨幅榜:\n"
    for _, row in fut_gainers.iterrows():
        msg += f"{row['symbol']}: {row['priceChangePercent']:.2f}%\n"

    msg += "\n📉 跌幅榜:\n"
    for _, row in fut_losers.iterrows():
        msg += f"{row['symbol']}: {row['priceChangePercent']:.2f}%\n"

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

    img_buf = plot_two_charts(spot_gainers, spot_losers, fut_gainers, fut_losers)
    bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=img_buf)

if __name__ == "__main__":
    send_to_telegram()
