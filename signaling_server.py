import asyncio
import json
import logging
import os
from aiohttp import web, WSMsgType
from aiohttp_cors import setup as cors_setup, ResourceOptions
import weakref

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SignalingServer:
    """WebRTC Signaling Server - Cloud Component"""
    
    def __init__(self):
        self.rooms = {}  # Store room connections
        self.connections = weakref.WeakSet()
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections for signaling"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        room_id = request.query.get('room', 'default')
        client_type = request.query.get('type', 'viewer')  # 'streamer' or 'viewer'
        
        if room_id not in self.rooms:
            self.rooms[room_id] = {'streamer': None, 'viewers': set()}
        
        room = self.rooms[room_id]
        
        if client_type == 'streamer':
            if room['streamer']:
                # Only one streamer per room
                await ws.send_str(json.dumps({'type': 'error', 'message': 'Room already has a streamer'}))
                await ws.close()
                return ws
            room['streamer'] = ws
            logger.info(f"Streamer connected to room {room_id}")
        else:
            room['viewers'].add(ws)
            logger.info(f"Viewer connected to room {room_id}")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        message_type = data.get('type')
                        
                        logger.info(f"Received {message_type} from {client_type} in room {room_id}")
                        
                        # Forward signaling messages between streamer and viewers
                        if client_type == 'streamer':
                            # Forward to all viewers
                            for viewer in room['viewers'].copy():
                                try:
                                    await viewer.send_str(msg.data)
                                except:
                                    room['viewers'].discard(viewer)
                        else:
                            # Forward to streamer
                            if room['streamer']:
                                try:
                                    await room['streamer'].send_str(msg.data)
                                except:
                                    room['streamer'] = None
                                    
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON received")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    break
                    
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            # Clean up
            if client_type == 'streamer' and room['streamer'] == ws:
                room['streamer'] = None
                logger.info(f"Streamer disconnected from room {room_id}")
            else:
                room['viewers'].discard(ws)
                logger.info(f"Viewer disconnected from room {room_id}")
        
        return ws
    
    async def health_handler(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'ok',
            'rooms': len(self.rooms),
            'active_connections': sum(len(room['viewers']) + (1 if room['streamer'] else 0) for room in self.rooms.values())
        })
    
    async def index_handler(self, request):
        """Simple status page"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>WebRTC Signaling Server</title></head>
        <body>
            <h1>WebRTC Signaling Server</h1>
            <p>Status: ✅ Running</p>
            <p>Active rooms: {len(self.rooms)}</p>
            <h3>Endpoints:</h3>
            <ul>
                <li><code>/ws?type=streamer&room=ROOM_ID</code> - For camera streamer</li>
                <li><code>/ws?type=viewer&room=ROOM_ID</code> - For viewers</li>
                <li><code>/health</code> - Health check</li>
            </ul>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

async def create_app():
    """Create and configure the web application"""
    app = web.Application()
    signaling = SignalingServer()
    
    # Add routes
    app.router.add_get('/', signaling.index_handler)
    app.router.add_get('/ws', signaling.websocket_handler)
    app.router.add_get('/health', signaling.health_handler)
    
    # Setup CORS
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    # Add CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)
    
    return app

async def main():
    """Main function"""
    app = await create_app()
    
    # Get port from environment (for cloud deployment)
    port = int(os.environ.get('PORT', 8080))
    
    # Start the server
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print("=" * 60)
    print("🌐 WebRTC Signaling Server Started!")
    print("=" * 60)
    print(f"Port: {port}")
    print("Ready for deployment to cloud platforms")
    print("=" * 60)
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")