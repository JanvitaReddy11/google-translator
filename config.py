import os
from google.cloud import speech, translate_v2 as translate, texttospeech


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Users/reddy/Downloads/Nao_Medical/transaltion-455219-c527c4c8bc2a.json"
speech_client = speech.SpeechClient()
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()
