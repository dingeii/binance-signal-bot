import asyncio
import aiohttp
import os
from tabulate import tabulate

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

COINGECKO_API = "https://api.coingecko.com/api/v3/coins/markets"

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

async def fetch_market_data(session):
    params = {
        "vs_currency": "usd",
        "order": "price_change_percentage_24h_desc",
        "per_page": "250",
        "page": "1",
        "price_change_percentage": "24h"
    }
    async with session.get(COINGECKO_API, params=params) as resp:
        return await resp.json()

def process_market(data):
    # 筛选币种名带 USDT 的
    filtered = [d for d in data if "usdt" in d['symbol'].lower()]
    for d in filtered:
        d["price_change_percentage_24h"] = float(d.get("price_change_percentage_24h") or 0)
    top_gainers = sorted(filtered, key=lambda x: x["price_change_percentage_24h"], reverse=True)[:10]
    top_losers = sorted(filtered, key=lambda x: x["price_change_percentage_24h"])[:10]
    return top_gainers, top_losers

def format_table(title, entries):
    table = []
    alerts = []
    for item in entries:
        percent = item["price_change_percentage_24h"]
        percent_str = f"{percent:.2f}%"
        price = item.get("current_price", "-")
        symbol = item["symbol"].upper()
        high_movement = abs(percent) > 20  # 自定义阈值20%
        table.append([symbol, price, highlight(percent_str, high_movement)])
        if high_movement:
            direction = "📈 *暴涨*" if percent > 0 else "📉 *暴跌*"
            alerts.append(
                f"{direction}\n"
                f"📊 *{symbol}*\n"
                f"💱 当前价格：`{price}`\n"
                f"📉 24h变动：*{percent:.2f}%*\n"
                f"--------------------------"
            )
    output = f"\n{title}\n" + tabulate(table, headers=["Symbol", "Price (USD)", "24h Change"], tablefmt="pretty")
    print(output)
    return alerts, output

async def monitor():
    async with aiohttp.ClientSession() as session:
        data = await fetch_market_data(session)
        gainers, losers = process_market(data)

        alerts_gainers, table_gainers = format_table("📈 Top 10 Gainers (USDT pairs)", gainers)
        alerts_losers, table_losers = format_table("📉 Top 10 Losers (USDT pairs)", losers)

        alerts = alerts_gainers + alerts_losers
        if alerts:
            message = "\n".join(alerts)
            await send_telegram_alert(session, message)
        else:
            print("无显著涨跌幅，跳过推送。")

async def main():
    await monitor()

if __name__ == "__main__":
    asyncio.run(main())
