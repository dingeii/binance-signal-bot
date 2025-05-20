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
    print("准备发送消息到Telegram...")
    try:
        async with session.post(url, data=data) as resp:
            resp_json = await resp.json()
            print("Telegram接口返回:", resp_json)
            if not resp_json.get("ok", True):
                print("Telegram发送失败:", resp_json)
            else:
                print("消息发送成功！")
            return resp_json
    except Exception as e:
        print("发送消息异常:", e)
        return None

async def get_futures_tickers(session):
    try:
        async with session.get(BINANCE_FUTURES_API) as resp:
            text = await resp.text()
            try:
                data = await resp.json()
            except Exception:
                print("接口返回非JSON格式:", text)
                return []
            if isinstance(data, list):
                print(f"获取到{len(data)}个合约行情数据")
                return data
            else:
                print("接口返回数据格式异常:", data)
                return []
    except Exception as e:
        print("请求币安合约行情接口失败:", e)
        return []

async def get_order_book(session, symbol, limit=50):
    params = {'symbol': symbol, 'limit': limit}
    try:
        async with session.get(DEPTH_API, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                print(f"请求盘口深度失败 {symbol}: 状态码{resp.status}")
                return None
    except Exception as e:
        print(f"请求盘口深度异常 {symbol}:", e)
        return None

async def main():
    print("脚本启动")
    print("TELEGRAM_BOT_TOKEN:", TELEGRAM_BOT_TOKEN)
    print("TELEGRAM_CHAT_ID:", TELEGRAM_CHAT_ID)
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("请设置环境变量 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
        return

    async with aiohttp.ClientSession() as session:
        tickers = await get_futures_tickers(session)
        if not tickers:
            print("获取合约行情失败或为空，程序退出")
            return

        sorted_by_change = sorted(tickers, key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)
        top10_up = sorted_by_change[:10]
        top10_down = sorted_by_change[-10:]

        print("开始获取盘口深度信息，请稍等...")
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
            else:
                # 如果盘口数据获取失败，则净买卖量记为0
                net_volumes.append({'symbol': tickers[i]['symbol'], 'net': 0})

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

        print("发送的消息内容:\n", message)

        await send_telegram_message(session, message)
        print("通知已发送")

if __name__ == "__main__":
    asyncio.run(main())
