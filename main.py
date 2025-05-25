import asyncio
import aiohttp
from tabulate import tabulate
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BINANCE_SPOT_API = "https://binance.vision/api/v3/ticker/24hr"
BINANCE_FUTURES_API = "https://binance.vision/fapi/v1/ticker/24hr"

def highlight(text, condition):
    if condition:
        return f"\033[91m🔻{text}\033[0m" if text.startswith('-') else f"\033[92m🔺{text}\033[0m"
    return text

async def send_telegram_alert(session, message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram 配置缺失，跳过推送")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        async with session.post(url, json=payload) as resp:
            await resp.text()
    except Exception as e:
        print("Telegram 推送失败:", e)

async def fetch_spot(session):
    async with session.get(BINANCE_SPOT_API) as resp:
        return await resp.json()

async def fetch_futures(session):
    async with session.get(BINANCE_FUTURES_API) as resp:
        return await resp.json()

def process_market(data):
    if not isinstance(data, list):
        print("返回数据格式异常:", data)
        return [], []
    filtered = [d for d in data if d["symbol"].endswith("USDT")]
    for d in filtered:
        d["priceChangePercent"] = float(d["priceChangePercent"])
    top_gainers = sorted(filtered, key=lambda x: x["priceChangePercent"], reverse=True)[:10]
    top_losers = sorted(filtered, key=lambda x: x["priceChangePercent"])[:10]
    return top_gainers, top_losers

def format_table(title, entries):
    print(f"\n{title}")
    table = []
    alerts = []
    for item in entries:
        percent = item["priceChangePercent"]
        percent_str = f"{percent:.2f}%"
        last_price = item.get("lastPrice", "-")
        symbol = item["symbol"]
        high_movement = percent >= 100 or percent <= -60
        table.append([symbol, last_price, highlight(percent_str, high_movement)])
        if high_movement:
            direction = "📈 *暴涨*" if percent >= 100 else "📉 *暴跌*"
            alerts.append(
                f"{direction}\n"
                f"📊 *{symbol}*\n"
                f"💱 当前价格：`{last_price}`\n"
                f"📉 24h变动：*{percent:.2f}%*\n"
                f"来源：*{title}*\n"
                f"--------------------------"
            )
    print(tabulate(table, headers=["Symbol", "Last Price", "24h Change"], tablefmt="pretty"))
    return alerts

async def monitor():
    async with aiohttp.ClientSession() as session:
        spot_data, futures_data = await asyncio.gather(
            fetch_spot(session),
            fetch_futures(session)
        )

        spot_gainers, spot_losers = process_market(spot_data)
        futures_gainers, futures_losers = process_market(futures_data)

        alerts = []
        alerts += format_table("📈 Spot Gainers", spot_gainers)
        alerts += format_table("📉 Spot Losers", spot_losers)
        alerts += format_table("📈 Futures Gainers", futures_gainers)
        alerts += format_table("📉 Futures Losers", futures_losers)

        if alerts:
            message = "\n".join(alerts)
            await send_telegram_alert(session, message)
        else:
            print("无显著价格变动，未推送")

async def main():
    await monitor()

if __name__ == "__main__":
    asyncio.run(main())
