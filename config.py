import os
from google.cloud import speech, translate_v2 as translate, texttospeech


import os
from dotenv import load_dotenv
load_dotenv()

credentials_path = os.getenv("GOOGLE_API_KEY")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

speech_client = speech.SpeechClient()
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()
