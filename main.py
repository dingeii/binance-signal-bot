import os
import time
import requests
import schedule
from telegram import Bot
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import pandas as pd
import mplfinance as mpf
from datetime import datetime

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# 多币种列表（你可以修改或增删）
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

def get_futures_data():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return [item for item in data if item['symbol'].endswith("USDT")]

def get_top_10_volume(data):
    sorted_pairs = sorted(data, key=lambda x: float(x['quoteVolume']), reverse=True)
    return sorted_pairs[:10]

def get_gainers_losers(data, limit=10):
    sorted_up = sorted(data, key=lambda x: float(x["priceChangePercent"]), reverse=True)[:limit]
    sorted_down = sorted(data, key=lambda x: float(x["priceChangePercent"]))[:limit]
    gainers = [(item["symbol"], float(item["priceChangePercent"])) for item in sorted_up]
    losers = [(item["symbol"], float(item["priceChangePercent"])) for item in sorted_down]
    return gainers, losers

def draw_volume_chart(top10, filename='top10_volume.png'):
    symbols = [item['symbol'] for item in top10]
    volumes = [float(item['quoteVolume']) for item in top10]

    plt.figure(figsize=(12,6))
    bars = plt.bar(symbols, volumes, color='dodgerblue')
    plt.title('币安USDT合约成交额Top10')
    plt.xlabel('合约对')
    plt.ylabel('24h成交额(USDT)')
    plt.xticks(rotation=45)
    for bar, vol in zip(bars, volumes):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{vol/1e9:.2f}B', ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def draw_gainers_losers_chart(gainers, losers, filename='gainers_losers.png'):
    fig, ax = plt.subplots(figsize=(12,6))
    symbols_up, values_up = zip(*gainers)
    symbols_down, values_down = zip(*losers)

    ax.barh(symbols_up[::-1], values_up[::-1], color='green', label='涨幅Top10')
    ax.barh(symbols_down[::-1], values_down[::-1], color='red', label='跌幅Top10')
    ax.set_title('📊 涨跌幅排行榜（过去24小时）')
    ax.set_xlabel('涨跌幅 %')
    ax.legend()
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

def get_kline_data(symbol="BTCUSDT", interval="1h", limit=24):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def draw_kline_chart(data, symbol, filename):
    # 生成DataFrame
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume", 
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('open_time', inplace=True)
    df = df.astype(float)

    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc)

    mpf.plot(df[['open', 'high', 'low', 'close']], type='candle', style=s, 
             title=f"{symbol} 近24小时K线图", 
             ylabel='价格(USDT)', savefig=filename)

def send_to_telegram():
    # 1. 获取数据
    all_data = get_futures_data()
    top10 = get_top_10_volume(all_data)
    gainers, losers = get_gainers_losers(all_data)

    # 2. 生成图表
    draw_volume_chart(top10)
    draw_gainers_losers_chart(gainers, losers)

    # 3. 构建消息文本
    msg = "📈 [币安USDT合约热门榜Top10]\n\n"
    for i, item in enumerate(top10, 1):
        msg += f"{i}. {item['symbol']} 成交额: {float(item['quoteVolume']):,.0f} USDT 最新价: {item['lastPrice']}\n"

    # 4. 发送成交额和涨跌幅图
    with open("top10_volume.png", "rb") as f1, open("gainers_losers.png", "rb") as f2:
        bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=f1, caption=msg)
        bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=f2, caption="📊 涨跌幅排行榜")

    # 5. 多币种K线图发送
    for symbol in SYMBOLS:
        try:
            kline = get_kline_data(symbol)
            filename = f"kline_{symbol}.png"
            draw_kline_chart(kline, symbol, filename)
            with open(filename, "rb") as img:
                bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=img, caption=f"🕯️ {symbol} 近24小时K线图")
        except Exception as e:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⚠️ 获取或绘制 {symbol} K线失败: {e}")

if __name__ == "__main__":
    if os.getenv("ONCE") == "1":
        send_to_telegram()
    else:
        schedule.every().hour.do(send_to_telegram)
        print("🤖 机器人启动，每小时运行一次")
        send_to_telegram()
        while True:
            schedule.run_pending()
            time.sleep(10)
