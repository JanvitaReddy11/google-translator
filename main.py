from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from routes import speech, translation, tts
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
import uvicorn
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables with defaults
# GCP services use PORT env variable for automatic configuration
PORT = int(os.environ.get("PORT", 8080))  # Default to 8080 for GCP
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

app = FastAPI()

# CORS middleware with configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Use environment variable for origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Set up storage paths - use /tmp for ephemeral storage on GCP
static_dir = os.environ.get("STATIC_DIR", "/tmp/static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routers for HTTP endpoints
app.include_router(speech.router, prefix="/api")
app.include_router(translation.router, prefix="/api")
app.include_router(tts.router, prefix="/api")

# Import the WebSocket handler function from speech.py
from routes.speech import websocket_endpoint as speech_websocket_endpoint

# Register the WebSocket endpoint directly on the main app
@app.websocket("/record_and_transcribe")
async def record_and_transcribe(
    websocket: WebSocket, 
    language: Optional[str] = Query(None)
):
    # Forward to the handler in speech.py
    await speech_websocket_endpoint(websocket, language)

@app.get("/")
def home():
    return {"message": "Welcome to Speech-to-Text API 🚀", "platform": "Google Cloud"}

@app.get("/healthcheck")
def healthcheck():
    """Endpoint for health checks"""
    return {"status": "healthy", "version": "1.0.0", "env": "gcp"}

# Add startup and shutdown event handlers
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting application on port {PORT}")
    # Create necessary directories - use /tmp for ephemeral storage on GCP
    os.makedirs(f"{static_dir}/audio", exist_ok=True)
    os.makedirs(f"{static_dir}/transcripts", exist_ok=True)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown")

# Add this for running the app with the correct port when called directly
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)