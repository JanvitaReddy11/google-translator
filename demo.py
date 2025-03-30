# Set up Google Cloud credentials (Make sure your credentials file is in the right path)
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Users/reddy/Downloads/Nao_Medical/transaltion-455219-c527c4c8bc2a.json"

import os
import queue
import threading
import time
from google.cloud import speech
from google.cloud import translate_v2 as translate
import pyaudio

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms chunks
FORMAT = pyaudio.paInt16
CHANNELS = 1

def main():
    # Create a thread-safe queue for the audio data
    audio_queue = queue.Queue()
    
    # Create a flag to indicate if we should stop
    stop_event = threading.Event()

    # Target language for translation (change as needed)
    target_language = "hi"  # Spanish - change to your desired language code
    
    # Initialize the Translation client
    translate_client = translate.Client()
    
    # Define a function to capture audio from the microphone
    def audio_capture_thread():
        print("🎙️ Starting microphone... (Speak now)")
        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        while not stop_event.is_set():
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_queue.put(data)
        
        # Cleanup
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("🛑 Microphone stopped")
    
    # Start the audio capture thread
    capture_thread = threading.Thread(target=audio_capture_thread)
    capture_thread.daemon = True
    capture_thread.start()
    
    # Create a Speech client
    speech_client = speech.SpeechClient()
    
    # Configure the recognition settings
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
        model="default",  # Change to "medical_conversation" if needed
        enable_automatic_punctuation=True,
    )
    
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,  # Show interim results
    )
    
    # Function to generate requests for the streaming API
    def generate_requests():
        while not stop_event.is_set():
            # Use a timeout to avoid blocking indefinitely
            try:
                chunk = audio_queue.get(block=True, timeout=0.5)
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                continue
    
    # Function to translate text
    def translate_text(text, target_language):
        if not text.strip():
            return ""
        try:
            translation = translate_client.translate(
                text,
                target_language=target_language
            )
            return translation['translatedText']
        except Exception as e:
            print(f"\n❌ Translation error: {e}")
            return f"[Translation error: {str(e)}]"
    
    try:
        print(f"⚙️ Starting speech recognition with translation to {target_language}...")
        print("=" * 60)
        requests = generate_requests()
        responses = speech_client.streaming_recognize(streaming_config, requests)
        
        # Process the responses
        last_transcript = ""
        for response in responses:
            if not response.results:
                continue
            
            result = response.results[0]
            is_final = result.is_final
            transcript = result.alternatives[0].transcript
            
            # Only translate final results or if transcript changed significantly
            if is_final or (not is_final and abs(len(transcript) - len(last_transcript)) > 10):
                translation = translate_text(transcript, target_language)
                last_transcript = transcript
                
                # Clear previous output
                print("\r" + " " * 100, end="\r", flush=True)
                
                # Print original transcript and translation
                status = "FINAL" if is_final else "Interim"
                #print(f"{status} (EN): {transcript}")
                print(f"{status} ({target_language.upper()}): {translation}")
                print("-" * 60)
            else:
                # Just update the transcript for interim results without translation
                print(f"\rInterim (EN): {transcript}", end="", flush=True)
        
    except KeyboardInterrupt:
        print("\n👋 Stopping by user request")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        # Cleanup
        stop_event.set()
        capture_thread.join(timeout=2.0)

if __name__ == "__main__":
    print("Real-time Speech Recognition with Translation Test")
    print("------------------------------------------------")
    print("This script will capture audio from your microphone,")
    print("display real-time transcription results and translations.")
    print("Press Ctrl+C to stop.")
    print()
    
    # Check if Google credentials are set
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("⚠️  Warning: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        print("    You may need to run:")
        print('    export GOOGLE_APPLICATION_CREDENTIALS="path/to/your-key.json"')
        print()
    
    main()