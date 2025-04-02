from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from google.cloud import texttospeech, translate_v2 as translate
from pydantic import BaseModel
import logging
import uuid
import os
import json
import time
import asyncio
from google.cloud import storage  # Changed from Azure to Google Cloud Storage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Cloud Clients
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()

# Create directories for storing files with environment variable support
# Use /tmp for Cloud Run and other GCP stateless services
static_dir = os.environ.get("STATIC_DIR", "/tmp/static")
AUDIO_DIR = os.environ.get("AUDIO_DIR", f"{static_dir}/audio")
TRANSCRIPT_DIR = os.environ.get("TRANSCRIPT_DIR", f"{static_dir}/transcripts")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# Initialize Google Cloud Storage client (if environment variables are set)
storage_client = None
bucket_name = os.environ.get("GCS_BUCKET_NAME")
if bucket_name:
    try:
        storage_client = storage.Client()
        logger.info(f"Google Cloud Storage client initialized for bucket: {bucket_name}")
    except Exception as e:
        logger.error(f"Error initializing Google Cloud Storage: {e}")

router = APIRouter()

# Model for saving transcript
class SaveTranscriptRequest(BaseModel):
    content: str
    filename: str = "translated_text.txt"
    language: str = "es"

# Model for TTS request
class TextToSpeechRequest(BaseModel):
    text: str = None
    language_code: str = ""
    use_saved_file: bool = False

# Function to save file to Google Cloud Storage or local filesystem
async def save_to_storage(folder_name, blob_name, content, is_binary=False):
    """Save content to storage (Google Cloud Storage or local filesystem)."""
    if storage_client and bucket_name:
        try:
            # Use Google Cloud Storage
            bucket = storage_client.bucket(bucket_name)
            
            # Create full blob path with folder
            full_blob_name = f"{folder_name}/{blob_name}"
            blob = bucket.blob(full_blob_name)
            
            # Upload the content
            if is_binary:
                blob.upload_from_string(content, content_type="audio/mpeg" if blob_name.endswith(".mp3") else "application/octet-stream")
            else:
                blob.upload_from_string(content, content_type="text/plain")
            
            # Make the blob publicly accessible
            blob.make_public()
            
            # Return the public URL to the blob
            return blob.public_url
        except Exception as e:
            logger.error(f"Error saving to Google Cloud Storage: {e}")
            # Fall back to local storage on error
    
    # Local storage fallback
    local_dir = AUDIO_DIR if folder_name == "audio" else TRANSCRIPT_DIR
    local_path = os.path.join(local_dir, blob_name)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    mode = "wb" if is_binary else "w"
    encoding = None if is_binary else "utf-8"
    
    with open(local_path, mode, encoding=encoding) as f:
        f.write(content)
    
    # Return a path relative to the static directory
    relative_path = f"/static/{folder_name}/{blob_name}"
    return relative_path

@router.post("/save_transcript/")
async def save_transcript(request: SaveTranscriptRequest):
    start_time = time.time()
    try:
        print(f"[{time.time() - start_time:.3f}s] Received save_transcript request.")
        logger.info(f"Saving transcript. Content length: {len(request.content)}, Language: {request.language}")

        # Generate a unique filename if one is not provided
        if request.filename == "translated_text.txt":
            timestamp = int(time.time())
            request.filename = f"transcript_{timestamp}.txt"

        # Save to storage (GCS or local)
        file_url = await save_to_storage("transcripts", request.filename, request.content)
        
        print(f"[{time.time() - start_time:.3f}s] Transcript saved to {file_url}")
        logger.info(f"Transcript saved to {file_url}")

        # Success response
        print(f"[{time.time() - start_time:.3f}s] Returning success response.")
        return JSONResponse(
            status_code=200,
            content={
                "message": "Transcript saved successfully",
                "file_path": file_url,
                "content_preview": request.content[:100] + "..." if len(request.content) > 100 else request.content
            }
        )

    except Exception as e:
        print(f"[{time.time() - start_time:.3f}s] Error occurred: {str(e)}")
        logger.error(f"Error saving transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save transcript: {str(e)}")

# Regular TTS endpoint (text in request body)
@router.post("/tts/")
async def text_to_speech(request: TextToSpeechRequest):
    try:
        # Validate input
        if not request.text and not request.use_saved_file:
            raise HTTPException(status_code=400, detail="Text is required when not using saved file")
        
        # Get text from the request
        text_to_convert = request.text
        
        # Generate audio
        audio_url = await generate_audio_from_text(text_to_convert, request.language_code)
        
        return {
            "message": "Audio generated successfully",
            "audio_url": audio_url
        }
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in TTS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")

# File-based TTS endpoint
@router.post("/tts_from_file/")
async def tts_from_file(request: TextToSpeechRequest):
    try:
        # Path to the translated text file - check if we're using Google Cloud Storage
        file_content = None
        
        if storage_client and bucket_name:
            try:
                # Try to get the file from Google Cloud Storage
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob("transcripts/translated_text.txt")
                
                # Download the blob
                file_content = blob.download_as_text()
            except Exception as e:
                logger.warning(f"Could not get file from Google Cloud Storage: {e}")
                # Continue to try local file
        
        # If we couldn't get the file from Google Cloud Storage, try local file
        if file_content is None:
            file_path = os.path.join(TRANSCRIPT_DIR, "translated_text.txt")
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"Translated text file not found at: {file_path}")
                raise HTTPException(status_code=404, detail=f"Translated text file not found at: {file_path}")
            
            # Read the content from the file
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        
        if not file_content:
            logger.error("Translated text file is empty")
            raise HTTPException(status_code=400, detail="Translated text file is empty")
            
        logger.info(f"Generating speech from file content")
        logger.info(f"Text content: {file_content[:100]}...")
        
        # Generate audio
        audio_url = await generate_audio_from_text(file_content, request.language_code)
        
        return {
            "message": "Audio generated successfully from file",
            "audio_url": audio_url,
            "text_used": file_content[:100] + "..." if len(file_content) > 100 else file_content
        }
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in file-based TTS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS from file error: {str(e)}")

async def generate_audio_from_text(text: str, language_code: str) -> str:
    """Generates speech from text and returns the file URL."""
    try:
        # Create synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Configure voice
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        
        # Configure audio
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Generate unique filename with timestamp to avoid caching issues
        timestamp = int(time.time())
        audio_filename = f"output_{timestamp}.mp3"
        
        # Generate speech
        logger.info(f"Generating TTS for language: {language_code}")
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Save audio file to appropriate storage
        audio_url = await save_to_storage("audio", audio_filename, response.audio_content, is_binary=True)
        
        logger.info(f"Audio saved to {audio_url}")
        
        # Return URL to the audio file
        return audio_url
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise Exception(f"Failed to generate speech: {str(e)}")