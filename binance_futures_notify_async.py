import os
import asyncio
import aiohttp

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

BINANCE_FUTURES_API = "https://fapi.binance.com/fapi/v1/ticker/24hr"
DEPTH_API = "https://fapi.binance.com/fapi/v1/depth"

async def send_telegram_message(session, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    async with session.post(url, data=data) as resp:
        return await resp.json()

async def get_futures_tickers(session):
    async with session.get(BINANCE_FUTURES_API) as resp:
        return await resp.json()

async def get_order_book(session, symbol, limit=50):
    params = {'symbol': symbol, 'limit': limit}
    try:
        async with session.get(DEPTH_API, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
    except:
        pass
    return None

async def main():
    async with aiohttp.ClientSession() as session:
        tickers = await get_futures_tickers(session)
        if not tickers:
            print("获取合约行情失败")
            return
        
        sorted_by_change = sorted(tickers, key=lambda x: float(x['priceChangePercent']), reverse=True)
        top10_up = sorted_by_change[:10]
        top10_down = sorted_by_change[-10:]

        tasks = [get_order_book(session, t['symbol'], 50) for t in tickers]
        order_books = await asyncio.gather(*tasks)

        net_volumes = []
        for i, ob in enumerate(order_books):
            if ob:
                bids = ob.get('bids', [])
                asks = ob.get('asks', [])
                bid_qty = sum(float(bid[1]) for bid in bids)
                ask_qty = sum(float(ask[1]) for ask in asks)
                net = bid_qty - ask_qty
                net_volumes.append({'symbol': tickers[i]['symbol'], 'net': net})

        net_volumes_sorted = sorted(net_volumes, key=lambda x: x['net'], reverse=True)
        top10_net_buy = net_volumes_sorted[:10]
        top10_net_sell = net_volumes_sorted[-10:]

        message = "*币安合约行情快报*\n\n"
        message += "*涨幅前10：*\n"
        for t in top10_up:
            message += f"{t['symbol']}: {t['priceChangePercent']}%\n"

        message += "\n*跌幅前10：*\n"
        for t in top10_down:
            message += f"{t['symbol']}: {t['priceChangePercent']}%\n"

        message += "\n*净买入前10：*\n"
        for t in top10_net_buy:
            message += f"{t['symbol']}: 净买入量 {t['net']:.2f}\n"

        message += "\n*净卖出前10：*\n"
        for t in top10_net_sell:
            message += f"{t['symbol']}: 净卖出量 {t['net']:.2f}\n"

        await send_telegram_message(session, message)
        print("通知已发送")

if __name__ == "__main__":
    asyncio.run(main())
