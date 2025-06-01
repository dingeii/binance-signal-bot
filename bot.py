import os
import requests
import matplotlib.pyplot as plt
import io
from telegram import Bot

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def fetch_binance_data(url):
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def get_top_gainers_losers(data):
    tickers = [{
        'symbol': d['symbol'],
        'priceChangePercent': float(d['priceChangePercent']),
        'volume': float(d['volume'])
    } for d in data]

    gainers = sorted(tickers, key=lambda x: x['priceChangePercent'], reverse=True)[:10]
    losers = sorted(tickers, key=lambda x: x['priceChangePercent'])[:10]
    return gainers, losers

def plot_chart(data, title):
    symbols = [d['symbol'] for d in data]
    changes = [d['priceChangePercent'] for d in data]
    volumes = [d['volume'] for d in data]

    fig, ax1 = plt.subplots(figsize=(12, 6))

    bars = ax1.bar(symbols, changes, color=['red' if x >= 0 else 'blue' for x in changes], alpha=0.7)
    ax1.set_ylabel('涨跌幅 (%)')
    ax1.set_title(title)
    ax1.axhline(0, color='black', linewidth=0.8)
    ax1.tick_params(axis='x', rotation=45)

    for bar, change in zip(bars, changes):
        height = bar.get_height()
        va = 'bottom' if height >= 0 else 'top'
        ax1.text(bar.get_x() + bar.get_width()/2, height, f'{change:.1f}%', ha='center', va=va)

    ax2 = ax1.twinx()
    ax2.plot(symbols, volumes, color='green', marker='o', linestyle='--', label='成交量')
    ax2.set_ylabel('成交量')
    ax2.legend(loc='upper right')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

def main():
    spot_url = "https://api.binance.com/api/v3/ticker/24hr"
    data = fetch_binance_data(spot_url)
    gainers, losers = get_top_gainers_losers(data)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    gainers_img = plot_chart(gainers, "币安现货市场涨幅榜前十")
    bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=gainers_img, caption="📈 币安现货涨幅榜前十")

    losers_img = plot_chart(losers, "币安现货市场跌幅榜前十")
    bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=losers_img, caption="📉 币安现货跌幅榜前十")

    print("图表已发送")

if __name__ == "__main__":
    main()
