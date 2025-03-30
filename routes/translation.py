from fastapi import APIRouter
from config import translate_client

router = APIRouter()

@router.post("/translate/")
async def translate_text(text: str, target_language: str = "fr"):
    translation = translate_client.translate(text, target_language=target_language)
    return {"translated_text": translation["translatedText"]}
