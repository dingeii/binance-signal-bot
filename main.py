import asyncio
import aiohttp
import os
from tabulate import tabulate

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CRYPTOCOMPARE_API_KEY = os.getenv("CRYPTOCOMPARE_API_KEY")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not CRYPTOCOMPARE_API_KEY:
    raise ValueError("请设置 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 和 CRYPTOCOMPARE_API_KEY 环境变量")

API_URL = "https://min-api.cryptocompare.com/data/top/totalvolfull"

def highlight(text, condition):
    if condition:
        return f"\033[92m🔺{text}\033[0m" if not text.startswith('-') else f"\033[91m🔻{text}\033[0m"
    return text

async def send_telegram_alert(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"Telegram 推送失败: 状态码 {resp.status}, 内容: {text}")
    except Exception as e:
        print("Telegram 推送异常:", e)

async def fetch_cryptocompare_data(session):
    params = {
        "limit": 100,
        "tsym": "USDT",
        "api_key": CRYPTOCOMPARE_API_KEY,
    }
    async with session.get(API_URL, params=params) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"CryptoCompare API 错误: 状态码 {resp.status}, 内容: {text}")
        return await resp.json()

def process_data(data):
    # data结构在 ['Data'] -> list，每项 ['CoinInfo'], ['RAW']['USDT']['PRICE'], ['DISPLAY']['USDT']['CHANGE24HOURPCT']
    entries = []
    for item in data.get("Data", []):
        coin = item.get("CoinInfo", {}).get("Name")
        raw_usdt = item.get("RAW", {}).get("USDT", {})
        display_usdt = item.get("DISPLAY", {}).get("USDT", {})
        if not coin or not raw_usdt or "PRICE" not in raw_usdt or "CHANGE24HOURPCT" not in raw_usdt:
            continue
        price = raw_usdt["PRICE"]
        change_pct = raw_usdt["CHANGE24HOURPCT"]
        entries.append({
            "symbol": coin,
            "price": price,
            "change_pct": change_pct
        })
    return entries

def format_table(title, entries):
    table = []
    alerts = []
    for item in entries:
        symbol = item["symbol"]
        price = item["price"]
        change_pct = item["change_pct"]
        change_str = f"{change_pct:.2f}%"
        high_move = abs(change_pct) > 20
        table.append([symbol, f"${price:.4f}", highlight(change_str, high_move)])
        if high_move:
            direction = "📈 *暴涨*" if change_pct > 0 else "📉 *暴跌*"
            alerts.append(
                f"{direction}\n"
                f"📊 *{symbol}*\n"
                f"💱 当前价格：`${price:.4f}`\n"
                f"📉 24小时变动：*{change_pct:.2f}%*\n"
                "--------------------------"
            )
    table_str = tabulate(table, headers=["币种", "当前价格 (USDT)", "24小时涨跌幅"], tablefmt="pretty")
    print(f"\n{title}\n{table_str}")
    return alerts, table_str

async def monitor():
    async with aiohttp.ClientSession() as session:
        data = await fetch_cryptocompare_data(session)
        entries = process_data(data)
        if not entries:
            print("未获取到行情数据")
            return

        gainers = sorted(entries, key=lambda x: x["change_pct"], reverse=True)[:10]
        losers = sorted(entries, key=lambda x: x["change_pct"])[:10]

        alerts_gainers, table_gainers = format_table("📈 Top 10 涨幅榜", gainers)
        alerts_losers, table_losers = format_table("📉 Top 10 跌幅榜", losers)

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
