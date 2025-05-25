import os
import asyncio
import aiohttp
from tabulate import tabulate

# 从环境变量读取，方便部署时配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BINANCE_SPOT_API = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_FUTURES_API = "https://fapi.binance.com/fapi/v1/ticker/24hr"

def highlight(text, change):
    """涨跌幅高亮，涨用绿箭头，跌用红箭头"""
    if change >= 5:
        return f"🟢 +{text}"
    elif change <= -5:
        return f"🔴 {text}"
    return text

async def send_telegram(session, message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram 配置缺失，跳过推送")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                print(f"Telegram 推送失败，状态码 {resp.status}")
    except Exception as e:
        print("Telegram 推送异常：", e)

def process_market(data):
    # 过滤 USDT 交易对，转换涨跌幅为 float
    filtered = [d for d in data if d["symbol"].endswith("USDT")]
    for d in filtered:
        d["priceChangePercent"] = float(d["priceChangePercent"])
    # 排序取前10涨幅和跌幅
    gainers = sorted(filtered, key=lambda x: x["priceChangePercent"], reverse=True)[:10]
    losers = sorted(filtered, key=lambda x: x["priceChangePercent"])[:10]
    return gainers, losers

def format_table(title, entries):
    table = []
    alerts = []
    for e in entries:
        pct = e["priceChangePercent"]
        pct_str = f"{pct:+.2f}%"
        price = e.get("lastPrice", "-")
        symbol = e["symbol"]
        table.append([symbol, price, highlight(pct_str, pct)])
        # 涨跌幅特别大时加入警报消息
        if abs(pct) >= 10:
            direction = "🚀暴涨" if pct > 0 else "💥暴跌"
            alerts.append(f"{direction} {symbol} 价格：{price} 涨跌幅：{pct_str}")
    text = tabulate(table, headers=["交易对", "最新价", "24小时涨跌幅"], tablefmt="pretty")
    return f"### {title}\n{text}", alerts

async def fetch_json(session, url):
    async with session.get(url) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"请求 {url} 失败，状态码 {resp.status}，响应内容: {text}")
        return await resp.json()

async def monitor():
    async with aiohttp.ClientSession() as session:
        try:
            spot_data, futures_data = await asyncio.gather(
                fetch_json(session, BINANCE_SPOT_API),
                fetch_json(session, BINANCE_FUTURES_API)
            )
            spot_gainers, spot_losers = process_market(spot_data)
            futures_gainers, futures_losers = process_market(futures_data)

            messages = []
            alerts = []

            for title, data in [
                ("币安现货涨幅榜", spot_gainers),
                ("币安现货跌幅榜", spot_losers),
                ("币安合约涨幅榜", futures_gainers),
                ("币安合约跌幅榜", futures_losers),
            ]:
                msg, alert = format_table(title, data)
                messages.append(msg)
                alerts.extend(alert)

            full_message = "\n\n".join(messages)
            if alerts:
                alert_message = "\n⚠️ 重要提醒 ⚠️\n" + "\n".join(alerts)
                full_message += "\n\n" + alert_message

            await send_telegram(session, full_message)
            print("推送完成！")

        except Exception as e:
            err_msg = f"❌ 监控异常: {e}"
            print(err_msg)
            await send_telegram(session, err_msg)

async def main():
    await monitor()

if __name__ == "__main__":
    asyncio.run(main())
