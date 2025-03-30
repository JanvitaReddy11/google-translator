from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from google.cloud import texttospeech, translate_v2 as translate
from pydantic import BaseModel
import logging
import uuid
import os
import json
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Cloud Clients
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()

# Create directories for storing files
AUDIO_DIR = "static/audio"
TRANSCRIPT_DIR = "static/transcripts"
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

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

import time

@router.post("/save_transcript/")
async def save_transcript(request: SaveTranscriptRequest):
    start_time = time.time()
    try:
        print(f"[{time.time() - start_time:.3f}s] Received save_transcript request.")
        logger.info(f"Saving transcript. Content length: {len(request.content)}, Language: {request.language}")

        # Ensure directory exists
        print(f"[{time.time() - start_time:.3f}s] Ensuring transcript directory exists...")
        os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

        # File path resolution
        file_path = os.path.join(TRANSCRIPT_DIR, request.filename)
        print(f"[{time.time() - start_time:.3f}s] File path resolved: {file_path}")

        # Write content asynchronously
        write_start_time = time.time()
        print(f"[{time.time() - start_time:.3f}s] Writing content to file asynchronously...")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.content)
            
        print(f"[{time.time() - start_time:.3f}s] File write completed in {time.time() - write_start_time:.3f}s.")

        logger.info(f"Transcript saved to {file_path}")

        # Success response
        print(f"[{time.time() - start_time:.3f}s] Returning success response.")
        return JSONResponse(
            status_code=200,
            content={
                "message": "Transcript saved successfully",
                "file_path": file_path,
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
        audio_url = generate_audio_from_text(text_to_convert, request.language_code)
        
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
        # Path to the translated text file
        file_path = os.path.join(TRANSCRIPT_DIR, "translated_text.txt")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Translated text file not found at: {file_path}")
            raise HTTPException(status_code=404, detail=f"Translated text file not found at: {file_path}")
        
        # Read the content from the file
        with open(file_path, "r", encoding="utf-8") as f:
            text_to_convert = f.read()
        
        if not text_to_convert:
            logger.error("Translated text file is empty")
            raise HTTPException(status_code=400, detail="Translated text file is empty")
            
        logger.info(f"Generating speech from file: {file_path}")
        logger.info(f"Text content: {text_to_convert[:100]}...")
        
        # Generate audio
        audio_url = generate_audio_from_text(text_to_convert, request.language_code)
        
        return {
            "message": "Audio generated successfully from file",
            "audio_url": audio_url,
            "text_used": text_to_convert[:100] + "..." if len(text_to_convert) > 100 else text_to_convert
        }
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in file-based TTS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS from file error: {str(e)}")

def generate_audio_from_text(text: str, language_code: str) -> str:
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
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        
        # Ensure the directory exists
        os.makedirs(AUDIO_DIR, exist_ok=True)
        
        # Generate speech
        logger.info(f"Generating TTS for language: {language_code}")
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Save audio file
        with open(audio_path, "wb") as f:
            f.write(response.audio_content)
        
        logger.info(f"Audio saved to {audio_path}")
        
        # Return URL to the audio file
        return f"/static/audio/{audio_filename}"
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise Exception(f"Failed to generate speech: {str(e)}")