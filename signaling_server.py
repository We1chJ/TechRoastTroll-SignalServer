import asyncio
import websockets
import json

clients = set()

async def handler(ws, _):
    clients.add(ws)
    try:
        async for msg in ws:
            for client in clients:
                if client != ws:
                    await client.send(msg)
    finally:
        clients.remove(ws)

start_server = websockets.serve(handler, "0.0.0.0", 8765)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
