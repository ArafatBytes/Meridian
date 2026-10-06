"""
Voice Analysis endpoints for Hot Word Detection
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from typing import Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analyze")
async def analyze_voice(
    audio: UploadFile = File(...),
    current_user: Any = Depends(get_current_user)
):
    """
    Analyze audio for hot words
    Returns whether SOS should be triggered
    """
    try:
        # Use default hot words (database not required for now)
        hot_words = ["help", "bachao", "save me", "police", "emergency"]
        
        # Read audio file
        audio_content = await audio.read()
        
        logger.info(f"Received audio file: {audio.filename}, size: {len(audio_content)} bytes")
        
        # For now, we'll use a simple approach:
        # In production, you would use Google Speech-to-Text here
        # from google.cloud import speech
        # client = speech.SpeechClient()
        # audio = speech.RecognitionAudio(content=audio_content)
        # config = speech.RecognitionConfig(...)
        # response = client.recognize(config=config, audio=audio)
        
        # Placeholder: Return false for now
        # TODO: Implement actual speech recognition
        transcript = ""  # Would come from Google Speech API
        
        # Check if any hot word is in transcript
        trigger = any(word.lower() in transcript.lower() for word in hot_words)
        
        logger.info(f"Voice analysis: transcript='{transcript}', trigger={trigger}")
        
        return {
            "trigger": trigger,
            "transcript": transcript,
            "hot_words_detected": [w for w in hot_words if w.lower() in transcript.lower()]
        }
        
    except Exception as e:
        logger.error(f"Voice analysis error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze voice: {str(e)}"
        )
