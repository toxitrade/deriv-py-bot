import asyncio
import json
import websockets

async def fetch_chunk(symbol):
    """Fetch one chunk of 10000 ticks"""
    try:
        async with websockets.connect(
            "wss://api.derivws.com/trading/v1/options/ws/public",
            ping_interval=None, close_timeout=30
        ) as ws:
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "end": "latest",
                "start": 1,
                "style": "ticks",
                "count": 10000
            }
            await ws.send(json.dumps(req))
            
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("msg_type") == "history":
                    prices = msg.get("history", {}).get("prices", [])
                    return prices
                elif msg.get("msg_type") == "error":
                    return None
                else:
                    break
    except Exception as e:
        print(f"Error: {e}")
        return None
    return None

async def fetch_symbol(symbol, target=50000):
    all_prices = []
    
    while len(all_prices) < 50000:
        prices = await fetch_chunk(symbol)
        if prices:
            all_prices.extend(prices)
            print(f"  Fetched {len(prices)} - Total: {len(all_prices)}")
            await asyncio.sleep(1)
        else:
            break
    return all_prices

async def main():
    symbols = ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"]
    
    for symbol in ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"]:
        print(f"\nFetching {symbol}...")
        all_prices = []
        
        while len(all_prices) < 50000:
            prices = await fetch_chunk(symbol)
            if prices:
                all_prices.extend(prices)
                print(f"  {symbol}: +{len(prices)} = {len(all_prices)}")
            else:
                break
            await asyncio.sleep(1)
        
        print(f"  {symbol} final: {len(all_prices)} ticks")
        with open(f'real_{symbol}.json', 'w') as f:
            json.dump(all_prices, f)

if __name__ == "__main__":
    asyncio.run(main())