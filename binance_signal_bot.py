import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
BINANCE_24H_TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr"
BINANCE_AGG_TRADES_URL = "https://fapi.binance.com/fapi/v1/aggTrades"

FETCH_LIMIT = 1000
WINDOW_MINUTES = 5

def fetch_tickers():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BinanceBot/1.0)"
    }
    try:
        resp = requests.get(BINANCE_24H_TICKER_URL, headers=headers, timeout=5)
        if resp.status_code != 200:
            print(f"❌ 获取 ticker 数据失败: HTTP {resp.status_code}")
            print(resp.text[:300])
            return []
        data = resp.json()
        if not isinstance(data, list):
            print("❌ 响应不是列表:", data)
            return []
        return [x for x in data if x['symbol'].endswith('USDT') and not x['symbol'].endswith('_PERP')]
    except Exception as e:
        print("❌ 请求 ticker 数据时出错:", e)
        return []

def get_agg_trades(symbol, start_time_ms):
    params = {
        "symbol": symbol,
        "startTime": start_time_ms,
        "limit": FETCH_LIMIT
    }
    try:
        resp = requests.get(BINANCE_AGG_TRADES_URL, params=params, timeout=5)
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []

def calc_net_buy(symbol):
    now = int(time.time() * 1000)
    start = now - WINDOW_MINUTES * 60 * 1000
    trades = get_agg_trades(symbol, start)
    buy_volume, sell_volume = 0.0, 0.0
    for trade in trades:
        qty = float(trade['q'])
        if trade['isBuyerMaker']:
            sell_volume += qty
        else:
            buy_volume += qty
    net = buy_volume - sell_volume
    return {"symbol": symbol, "net_buy": net}

def rank_by_net_buy(symbols):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for r in executor.map(calc_net_buy, symbols):
            if r:
                results.append(r)
    top_buy = sorted(results, key=lambda x: x['net_buy'], reverse=True)[:10]
    top_sell = sorted(results, key=lambda x: x['net_buy'])[:10]
    return top_buy, top_sell

def rank_by_price_change(tickers):
    up = sorted(tickers, key=lambda x: float(x['priceChangePercent']), reverse=True)[:10]
    down = sorted(tickers, key=lambda x: float(x['priceChangePercent']))[:10]
    return up, down

def format_message(up, down, net_buy, net_sell):
    msg = "*📊 币安合约市场信号（USDT对）*\n"
    msg += f"_过去 {WINDOW_MINUTES} 分钟成交数据分析_\n\n"

    msg += "*📈 涨幅前十:*\n"
    for d in up:
        msg += f"`{d['symbol']}`: {float(d['priceChangePercent']):.2f}%\n"

    msg += "\n*📉 跌幅前十:*\n"
    for d in down:
        msg += f"`{d['symbol']}`: {float(d['priceChangePercent']):.2f}%\n"

    msg += "\n*🟢 净买入前十:*\n"
    for d in net_buy:
        msg += f"`{d['symbol']}`: +{d['net_buy']:.2f}\n"

    msg += "\n*🔴 净卖出前十:*\n"
    for d in net_sell:
        msg += f"`{d['symbol']}`: {d['net_buy']:.2f}\n"

    return msg

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ 环境变量 BOT_TOKEN 或 CHAT_ID 未设置")
        return
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(TELEGRAM_URL, data=payload)
        if not r.ok:
            print("❌ Telegram 发送失败:", r.text)
    except Exception as e:
        print("❌ 发送 Telegram 消息出错:", e)

def main():
    print("🔍 获取合约行情数据中...")
    tickers = fetch_tickers()
    if not tickers:
        print("⚠️ 未获取到有效 ticker 数据")
        return
    symbols = [x['symbol'] for x in sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)[:20]]

    print("📊 计算净买入/净卖出中...")
    net_buy_top, net_sell_top = rank_by_net_buy(symbols)

    up, down = rank_by_price_change(tickers)

    print("✉️ 构建消息...")
    message = format_message(up, down, net_buy_top, net_sell_top)

    print("🚀 发送 Telegram...")
    send_telegram_message(message)

if __name__ == "__main__":
    main()
