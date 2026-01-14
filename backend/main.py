import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import BotConfig, BotStatus, SearchConfig, MessageTemplate
from .linkedin_bot import LinkedInBot
from .crm_client import CRMClient


# Global state
class AppState:
    bot: Optional[LinkedInBot] = None
    bot_task: Optional[asyncio.Task] = None
    websocket_clients: list[WebSocket] = []
    current_config: Optional[BotConfig] = None
    crm_api_key: Optional[str] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("[*] LinkedIn Sales Robot starting...")
    yield
    # Cleanup
    if state.bot:
        await state.bot.close()
    print("[*] LinkedIn Sales Robot shutting down...")


app = FastAPI(
    title="LinkedIn Sales Robot",
    description="Automated LinkedIn outreach and CRM integration",
    version="1.0.0",
    lifespan=lifespan
)


# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


async def broadcast_status(status: BotStatus):
    """Broadcast bot status to all connected WebSocket clients"""
    message = {
        "type": "status",
        "data": status.model_dump()
    }
    disconnected = []
    for ws in state.websocket_clients:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)
    
    for ws in disconnected:
        state.websocket_clients.remove(ws)


def status_callback(status: BotStatus):
    """Callback for bot status updates"""
    asyncio.create_task(broadcast_status(status))


@app.get("/")
async def root():
    """Serve the main UI"""
    return FileResponse("frontend/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    state.websocket_clients.append(websocket)
    
    try:
        # Send current status on connect
        if state.bot:
            await websocket.send_json({
                "type": "status",
                "data": state.bot.status.model_dump()
            })
        else:
            await websocket.send_json({
                "type": "status",
                "data": BotStatus().model_dump()
            })
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)


class StartBotRequest(BaseModel):
    """Request to start the bot"""
    job_titles: list[str]
    locations: list[str] = []
    posted_within_days: int = 7
    message_template: str
    crm_stage_id: str
    crm_api_key: Optional[str] = None
    delay_between_connections: int = 30
    max_connections_per_session: int = 20


@app.post("/api/start")
async def start_bot(request: StartBotRequest):
    """Start the LinkedIn bot"""
    if state.bot and state.bot.status.is_running:
        raise HTTPException(status_code=400, detail="Bot is already running")
    
    # Store API key
    state.crm_api_key = request.crm_api_key
    
    # Create config
    config = BotConfig(
        search_config=SearchConfig(
            job_titles=request.job_titles,
            locations=request.locations,
            posted_within_days=request.posted_within_days
        ),
        message_template=MessageTemplate(
            template=request.message_template
        ),
        crm_stage_id=request.crm_stage_id,
        delay_between_connections=request.delay_between_connections,
        max_connections_per_session=request.max_connections_per_session
    )
    
    state.current_config = config
    
    # Create CRM client
    crm_client = CRMClient(api_key=request.crm_api_key)
    
    # Create and start bot
    state.bot = LinkedInBot(
        config=config,
        crm_client=crm_client,
        status_callback=status_callback
    )
    
    # Run bot in background
    state.bot_task = asyncio.create_task(state.bot.run())
    
    return {"status": "started", "message": "Bot started successfully"}


@app.post("/api/stop")
async def stop_bot():
    """Stop the LinkedIn bot"""
    if not state.bot or not state.bot.status.is_running:
        raise HTTPException(status_code=400, detail="Bot is not running")
    
    await state.bot.stop()
    return {"status": "stopped", "message": "Bot stop requested"}


@app.get("/api/status")
async def get_status():
    """Get current bot status"""
    if state.bot:
        return state.bot.status.model_dump()
    return BotStatus().model_dump()


@app.post("/api/close-browser")
async def close_browser():
    """Close the browser"""
    if state.bot:
        await state.bot.close()
        state.bot = None
    return {"status": "closed", "message": "Browser closed"}


class TestCRMRequest(BaseModel):
    """Request to test CRM connection"""
    crm_api_key: Optional[str] = None
    stage_id: str


@app.post("/api/test-crm")
async def test_crm(request: TestCRMRequest):
    """Test CRM connection"""
    try:
        crm_client = CRMClient(api_key=request.crm_api_key)
        # We can't really test without creating a lead, so just validate the input
        return {
            "status": "ok",
            "message": "CRM configuration looks valid. Connection will be tested when bot runs."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

