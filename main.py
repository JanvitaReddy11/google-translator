from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from routes import speech, translation, tts
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS middleware for HTTP requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (use cautiously in production)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers for HTTP endpoints
app.include_router(speech.router, prefix="/api")
app.include_router(translation.router, prefix="/api")
app.include_router(tts.router, prefix="/api")

# IMPORTANT: Directly import the WebSocket handler function from speech.py
from routes.speech import websocket_endpoint as speech_websocket_endpoint

# Register the WebSocket endpoint directly on the main app
@app.websocket("/record_and_transcribe")
async def record_and_transcribe(
    websocket: WebSocket, 
    language: Optional[str] = Query(None)
):
    # Just forward to the handler in speech.py
    await speech_websocket_endpoint(websocket, language)

@app.get("/")
def home():
    return {"message": "Welcome to Speech-to-Text API 🚀"}