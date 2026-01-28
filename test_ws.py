import asyncio
import websockets
import json

async def test():
    async with websockets.connect('ws://localhost:8000/ws/market', close_timeout=2) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=3)
        data = json.loads(msg)
        print(f"Type: {data.get('type')}")
        print(f"Source: {data.get('source')}")
        symbols = [t['symbol'] for t in data.get('data', [])]
        print(f"Symbols: {symbols}")
        vix = [t for t in data.get('data', []) if t['symbol'] == 'VIX']
        if vix:
            print(f"VIX: ${vix[0]['price']}")

asyncio.run(test())
