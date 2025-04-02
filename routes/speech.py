from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from google.cloud import speech
from google.cloud import translate_v2 as translate
import asyncio
import json
import logging
import uuid
import os
import queue
import threading
import pyaudio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Body
from pydantic import BaseModel
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Google Cloud credentials
# When running on GCP, the application will use the service account automatically
# For local development, you'll still need to set GOOGLE_APPLICATION_CREDENTIALS
from dotenv import load_dotenv
try:
    # Only load .env file if not running on GCP (helps with local development)
    if not os.environ.get("K_SERVICE"):  # K_SERVICE is set when running on Cloud Run
        load_dotenv()
except ImportError:
    pass

# Get credentials path from environment variable if provided
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if credentials_path:
    # Make sure the path exists
    if os.path.exists(credentials_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    else:
        logger.warning(f"Credentials file not found at {credentials_path}")
        logger.info("Using default GCP service account credentials")
else:
    logger.info("No explicit credentials path provided, using default GCP service account")

# Initialize clients
speech_client = speech.SpeechClient()
translate_client = translate.Client()

router = APIRouter()

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms chunks
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Active WebSockets and their stop events
active_connections = {}

# Function to translate text
def translate_text(text, target_language):
    if not text or not text.strip():
        return ""
    
    # Extract language code from language-country format (e.g., "en-US" -> "en")
    target_language_code = target_language.split('-')[0] if '-' in target_language else target_language
    
    try:
        translation = translate_client.translate(
            text,
            target_language=target_language_code
        )
        return translation['translatedText']
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return f"[Translation error: {str(e)}]"

# Process speech responses with better stop handling
async def process_speech_responses(responses, send_message, stop_event, target_language):
    last_transcript = ""
    final_sent = False
    
    try:
        for response in responses:
            if stop_event.is_set():
                logger.info("Stop event detected during response processing")
                break
                
            if not response.results:
                continue

            result = response.results[0]
            is_final = result.is_final
            transcript = result.alternatives[0].transcript

            # Only translate final results or if transcript changed significantly
            if is_final or (not is_final and abs(len(transcript) - len(last_transcript)) > 10):
                translation = translate_text(transcript, target_language)
                last_transcript = transcript

                status = "FINAL" if is_final else "INTERIM"
                message = json.dumps({
                    "status": status,
                    "original": transcript,
                    "translation": translation,
                    "is_final": is_final
                })
                await send_message(message)
            else:
                # Just update the transcript for interim results without translation
                message = json.dumps({
                    "status": "INTERIM",
                    "original": transcript,
                    "is_final": False
                })
                await send_message(message)
        
        # Always send a final COMPLETE message when done (if not already stopped)
        if not stop_event.is_set() and not final_sent:
            logger.info("Sending COMPLETE message")
            await send_message(json.dumps({
                "status": "COMPLETE",
                "is_final": True
            }))
            final_sent = True
            
    except Exception as e:
        logger.error(f"Error in process_speech_responses: {str(e)}")
        if not stop_event.is_set() and not final_sent:
            try:
                await send_message(json.dumps({
                    "status": "ERROR",
                    "error": str(e),
                    "is_final": True
                }))
            except:
                pass
    finally:
        # Ensure we always send a COMPLETE message if not already sent
        if not stop_event.is_set() and not final_sent:
            try:
                logger.info("Sending final COMPLETE message from finally block")
                await send_message(json.dumps({
                    "status": "COMPLETE",
                    "is_final": True
                }))
            except:
                pass

@router.websocket("/record_and_transcribe")
async def websocket_endpoint(
    websocket: WebSocket, 
    language: Optional[str] = Query(None)
):
    """WebSocket endpoint that processes audio sent from client and returns transcriptions."""
    logger.info(f"WebSocket connection request received with language={language}")
    connection_id = str(uuid.uuid4())

    try:
        await websocket.accept()
        
        # Create stop event and store connection info
        stop_event = threading.Event()
        active_connections[connection_id] = {
            "websocket": websocket,
            "stop_event": stop_event
        }
        
        logger.info(f"WebSocket connection established: {connection_id}")

        # Send connection message
        await websocket.send_text(json.dumps({"status": "connected", "connection_id": connection_id}))

        # Create a thread-safe queue for audio data
        audio_queue = queue.Queue()

        # Target language for translation - use the one provided in the query parameter or default to "en-US"
        target_language = language if language else "en-US"
        logger.info(f"Using target language: {target_language}")

        # Start the audio capture in a background thread
        def audio_capture_thread():
            logger.info("🎙️ Starting microphone... (Speak now)")
            p = pyaudio.PyAudio()
            stream = None
            
            try:
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )

                while not stop_event.is_set():
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        audio_queue.put(data)
                    except Exception as e:
                        logger.error(f"Error reading from audio stream: {e}")
                        if stop_event.is_set():
                            break
            except Exception as e:
                logger.error(f"Error in audio capture: {e}")
            finally:
                # Clean up resources
                logger.info("🛑 Stopping audio capture")
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass
                try:
                    p.terminate()
                except:
                    pass
                logger.info("🛑 Audio capture resources released")

        # Start the audio capture thread
        capture_thread = threading.Thread(target=audio_capture_thread)
        capture_thread.daemon = True
        capture_thread.start()

        # Configure speech recognition settings
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )

        # Generator for streaming requests
        def generate_requests():
            try:
                while not stop_event.is_set():
                    try:
                        # Smaller timeout to be more responsive to stop events
                        chunk = audio_queue.get(block=True, timeout=0.3)
                        yield speech.StreamingRecognizeRequest(audio_content=chunk)
                    except queue.Empty:
                        # No data available, check if we should stop
                        continue
                    except Exception as e:
                        logger.error(f"Error generating request: {e}")
                        if stop_event.is_set():
                            break
            finally:
                logger.info("Request generator ended")

        # Function to send message to WebSocket
        async def send_message(msg):
            try:
                if not stop_event.is_set():
                    await websocket.send_text(msg)
                    return True
                return False
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                stop_event.set()
                return False

        # Process WebSocket messages from client
        async def process_client_messages():
            try:
                while not stop_event.is_set():
                    try:
                        # Set a smaller timeout for receiving messages to be more responsive
                        message = await asyncio.wait_for(websocket.receive_text(), timeout=0.3)
                        try:
                            data = json.loads(message)
                            if data.get("command") == "stop":
                                logger.info(f"Received stop command from client: {connection_id}")
                                stop_event.set()
                                # Send acknowledgment back to client
                                await send_message(json.dumps({
                                    "status": "STOPPING",
                                    "message": "Stop command received"
                                }))
                                break
                        except json.JSONDecodeError:
                            # Binary data (audio) - no action needed here
                            pass
                    except asyncio.TimeoutError:
                        # This is expected, just continue
                        pass
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected in message processor: {connection_id}")
                stop_event.set()
            except Exception as e:
                logger.error(f"Error in client message processor: {e}")
                stop_event.set()
            finally:
                logger.info(f"Client message processor ended: {connection_id}")

        # Start message processing task
        message_task = asyncio.create_task(process_client_messages())

        # Start streaming recognition with the improved process_speech_responses function
        try:
            logger.info(f"⚙️ Starting speech recognition with translation to {target_language}...")
            requests = generate_requests()
            responses = speech_client.streaming_recognize(streaming_config, requests)
            
            # Process the responses using the improved function
            await process_speech_responses(responses, send_message, stop_event, target_language)

        except Exception as e:
            logger.error(f"Error in speech recognition or translation: {str(e)}")
            if not stop_event.is_set():
                await send_message(json.dumps({"error": str(e)}))
        finally:
            stop_event.set()
            if not message_task.done():
                message_task.cancel()
            
            # Wait for capture thread to stop
            capture_thread.join(timeout=2.0)
            
            # Send a final message indicating completion if not already sent
            try:
                if not stop_event.is_set():
                    await send_message(json.dumps({
                        "status": "COMPLETE",
                        "message": "Processing completed"
                    }))
            except:
                pass

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except:
            pass
    finally:
        # Make sure to clean up resources
        if 'stop_event' in locals():
            stop_event.set()
        
        if 'message_task' in locals() and not message_task.done():
            try:
                message_task.cancel()
            except:
                pass

        # Clean up active connections
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        # Ensure stream and PyAudio are cleaned up (redundant but safe)
        if 'p' in locals():
            try:
                p.terminate()
            except:
                pass
                
        if 'stream' in locals() and stream:
            try:
                stream.stop_stream()
                stream.close()
            except:
                pass
                
        logger.info(f"Connection closed and cleaned up: {connection_id}")

# Use /tmp directory for transcripts on GCP services
static_dir = os.environ.get("STATIC_DIR", "/tmp/static")
TRANSCRIPT_DIR = f"{static_dir}/transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)