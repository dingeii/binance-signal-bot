import requests
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor

# ============ 配置 ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

CACHE_FILE = "net_buy_cache.json"
NET_BUY_THRESHOLD = 10000      # 净买入超过此值触发预警
NET_BUY_MULTIPLIER = 3         # 当前净买入超过过去平均 x 倍
MIN_DATA_POINTS = 3

FETCH_LIMIT = 1000
WINDOW_MINUTES = 5

# ============ API 地址 ============
BINANCE_24H_TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr"
BINANCE_AGG_TRADES_URL = "https://fapi.binance.com/fapi/v1/aggTrades"

# ============ 获取行情 ============
def fetch_tickers():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(BINANCE_24H_TICKER_URL, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        return [x for x in data if x['symbol'].endswith('USDT') and not x['symbol'].endswith('_PERP')]
    except Exception as e:
        print(f"❌ 获取 ticker 数据失败: {e}")
        return []

# ============ 获取 aggTrades ============
def get_agg_trades(symbol, start_time_ms):
    try:
        r = requests.get(BINANCE_AGG_TRADES_URL, params={
            "symbol": symbol,
            "startTime": start_time_ms,
            "limit": FETCH_LIMIT
        }, timeout=5)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []

# ============ 计算净买入 ============
def calc_net_buy(symbol):
    now = int(time.time() * 1000)
    start = now - WINDOW_MINUTES * 60 * 1000
    trades = get_agg_trades(symbol, start)
    buy_vol, sell_vol = 0.0, 0.0
    for t in trades:
        qty = float(t['q'])
        if t['isBuyerMaker']:
            sell_vol += qty
        else:
            buy_vol += qty
    return {"symbol": symbol, "net_buy": buy_vol - sell_vol}

def rank_by_net_buy(symbols):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for result in executor.map(calc_net_buy, symbols):
            if result:
                results.append(result)
    top_buy = sorted(results, key=lambda x: x['net_buy'], reverse=True)[:10]
    top_sell = sorted(results, key=lambda x: x['net_buy'])[:10]
    return top_buy, top_sell

# ============ 净买入历史缓存 ============
def load_net_buy_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_net_buy_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def update_net_buy_cache(cache, net_data):
    for item in net_data:
        sym = item['symbol']
        val = item['net_buy']
        cache.setdefault(sym, []).append(val)
        if len(cache[sym]) > 10:
            cache[sym] = cache[sym][-10:]
    save_net_buy_cache(cache)

# ============ 激增检测 ============
def detect_net_buy_spikes(net_buy_data, cache):
    spikes = []
    for item in net_buy_data:
        sym = item['symbol']
        current = item['net_buy']
        history = cache.get(sym, [])
        if len(history) >= MIN_DATA_POINTS:
            avg = sum(history) / len(history)
            if current > NET_BUY_THRESHOLD or current > avg * NET_BUY_MULTIPLIER:
                spikes.append({"symbol": sym, "current": current, "average": avg})
    return spikes

# ============ 涨跌幅排名 ============
def rank_by_price_change(tickers):
    up = sorted(tickers, key=lambda x: float(x['priceChangePercent']), reverse=True)[:10]
    down = sorted(tickers, key=lambda x: float(x['priceChangePercent']))[:10]
    return up, down

# ============ 格式化消息 ============
def format_message(up, down, net_buy, net_sell):
    msg = "*📊 币安合约市场信号（USDT对）*\n"
    msg += f"_过去 {WINDOW_MINUTES} 分钟成交分析_\n\n"

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

def format_alert_message(spikes):
    if not spikes:
        return None
    msg = "*🚨 净买入激增预警:*\n"
    for s in spikes:
        msg += f"`{s['symbol']}` 净买入: +{s['current']:.2f}（均值: {s['average']:.2f}）\n"
    return msg

# ============ 发送 Telegram ============
def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ BOT_TOKEN 或 CHAT_ID 未设置")
        return
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(TELEGRAM_URL, data=payload)
        if not r.ok:
            print("❌ Telegram 推送失败:", r.text)
    except Exception as e:
        print("❌ Telegram 错误:", e)

# ============ 主逻辑 ============
def main():
    print("📥 获取行情数据中...")
    tickers = fetch_tickers()
    if not tickers:
        print("⚠️ 获取失败，退出")
        return

    top_symbols = [x['symbol'] for x in sorted(tickers, key=lambda x: float(x['quoteVolume']), reverse=True)[:20]]
    
    print("📊 计算净买入...")
    net_buy_top, net_sell_top = rank_by_net_buy(top_symbols)

    # 缓存和激增检测
    cache = load_net_buy_cache()
    update_net_buy_cache(cache, net_buy_top + net_sell_top)
    spikes = detect_net_buy_spikes(net_buy_top, cache)

    if spikes:
        alert_msg = format_alert_message(spikes)
        send_telegram_message(alert_msg)

    up, down = rank_by_price_change(tickers)
    msg = format_message(up, down, net_buy_top, net_sell_top)
    send_telegram_message(msg)

if __name__ == "__main__":
    main()
