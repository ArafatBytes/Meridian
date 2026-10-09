"""
AI and NLP API Endpoints
Speech-to-Text, Crime Detection, and other AI services
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, status, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from PIL import UnidentifiedImageError

from app.core.security import get_current_user
from app.llm.client import FEATURE_CRIME, LLMUnavailable, chain, keys_for
from app.services.ai.speech_service import speech_service
from app.vision.analyze import analyze_photo
from app.vision.mapping import (
    CUE_FIELDS,
    PROPOSABLE_FROM_PHOTO,
    UNREACHABLE_FROM_PHOTO,
)
from app.vision.replay import FIXTURE_PATH as REPLAY_FIXTURE
from app.vision.storage import signed_url, store_evidence

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/speech-to-text", response_model=dict)
async def transcribe_speech(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = Form(default="en-US", description="Language code (e.g., en-US, bn-BD)"),
):
    """
    Convert speech audio to text using Google Cloud Speech-to-Text API
    
    **Supported audio formats:**
    - M4A (iOS/Android recordings)
    - MP3
    - WAV
    - FLAC
    - OGG
    
    **Supported languages:**
    - en-US (English - United States)
    - bn-BD (Bengali - Bangladesh)
    - And 100+ more languages
    
    **Parameters:**
    - audio: Audio file (max 30 seconds for real-time, longer for async)
    - language: Language code (default: en-US)
    
    **Returns:**
    - text: Transcribed text
    - confidence: Confidence score (0-1)
    - language: Language used
    - word_count: Number of words transcribed
    """
    try:
        # Validate file
        if not audio.filename:
            raise HTTPException(status_code=400, detail="No audio file provided")

        # Get file extension
        file_extension = audio.filename.split('.')[-1].lower()
        valid_formats = ['m4a', 'mp3', 'wav', 'flac', 'ogg', 'aac', 'webm']
        
        if file_extension not in valid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {file_extension}. "
                       f"Supported formats: {', '.join(valid_formats)}"
            )

        # Read audio file
        logger.info(f"Received audio file: {audio.filename} ({file_extension})")
        audio_content = await audio.read()
        
        # Check file size (max 10MB for real-time)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(audio_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"Audio file too large. Maximum size: 10MB"
            )

        # Transcribe audio
        result = await speech_service.transcribe_audio(
            audio_content=audio_content,
            language_code=language,
            audio_format=file_extension,
            enable_automatic_punctuation=True,
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": result,
                "message": "Audio transcribed successfully"
            }
        )

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to transcribe audio: {str(e)}"
        )


@router.get("/supported-languages", response_model=dict)
async def get_supported_languages():
    """
    Get list of supported languages for speech-to-text
    
    **Returns:**
    - List of language codes and names
    """
    languages = [
        {"code": "en-US", "name": "English (United States)"},
        {"code": "en-GB", "name": "English (United Kingdom)"},
        {"code": "bn-BD", "name": "Bengali (Bangladesh)"},
        {"code": "hi-IN", "name": "Hindi (India)"},
        {"code": "es-ES", "name": "Spanish (Spain)"},
        {"code": "fr-FR", "name": "French (France)"},
        {"code": "de-DE", "name": "German (Germany)"},
        {"code": "ja-JP", "name": "Japanese (Japan)"},
        {"code": "ko-KR", "name": "Korean (South Korea)"},
        {"code": "zh-CN", "name": "Chinese (Mandarin, Simplified)"},
        {"code": "ar-SA", "name": "Arabic (Saudi Arabia)"},
        {"code": "pt-BR", "name": "Portuguese (Brazil)"},
        {"code": "ru-RU", "name": "Russian (Russia)"},
        {"code": "it-IT", "name": "Italian (Italy)"},
        {"code": "nl-NL", "name": "Dutch (Netherlands)"},
    ]
    
    return {
        "success": True,
        "data": {
            "languages": languages,
            "total": len(languages),
            "default": "en-US"
        },
        "message": "Supported languages retrieved successfully"
    }


@router.get("/health", response_model=dict)
async def ai_service_health():
    """
    Check health status of AI services
    
    **Returns:**
    - Status of Speech-to-Text service
    """
    try:
        # Check if speech service is initialized
        is_available = speech_service.client is not None
        
        return {
            "success": True,
            "data": {
                "speech_to_text": "available" if is_available else "unavailable",
                "provider": "Google Cloud Speech-to-Text",
                "status": "healthy" if is_available else "unhealthy"
            },
            "message": "AI service health check completed"
        }
    except Exception as e:
        return {
            "success": False,
            "data": {
                "speech_to_text": "error",
                "error": str(e)
            },
            "message": "AI service health check failed"
        }


# ============================================================================
# CRIME DETECTION AI ENDPOINTS
# ============================================================================

@router.post("/crime-detection/analyze", response_model=dict)
async def analyze_crime_image(
    file: UploadFile = File(..., description="Report photo to analyse"),
    report_text: Optional[str] = Form(
        default=None,
        description="What the reporter wrote, for the corroboration cross-check.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Read the visible cues out of a report photo. D07, ADR 0006.

    **The model does not name a crime, and this endpoint does not file one.** It
    answers five questions about what is physically visible; our own code
    (`app/vision/mapping.py`) turns those into at most a *candidate* category;
    the reporter confirms or overrides it. The category that gets filed is
    always a human's.

    `engine` says which tier answered -- `gemini`, `replay` or `ollama`. It is
    returned so the screen can show it: a cached or locally-computed answer is
    labelled rather than passed off as a live cloud call.

    `proposed_category` is `null` whenever no cue came back a definite `yes`,
    which is the normal result for a benign photo. `unreachable_from_photo`
    lists the categories a photograph cannot establish at all.

    The old `include_pose_analysis`, `include_scene_analysis`, `use_ml_fusion`
    and `confidence_threshold` parameters are gone. The pose path never once
    executed, the scene classifier is replaced by one field of the model's
    answer, and the fusion weights produced numbers nobody had validated.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Please upload an image.",
        )

    image_data = await file.read()
    if not image_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file received",
        )

    try:
        result = await analyze_photo(image_data, report_text=report_text)
    except UnidentifiedImageError:
        # Claimed to be an image and is not. A 400, not a 500: the caller sent it.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That file could not be read as an image.",
        )
    except LLMUnavailable as exhausted:
        # Every tier is gone. Say so plainly rather than inventing a result --
        # the photo is still evidence and the caller stores it either way.
        logger.warning("crime vision unavailable: %s", exhausted)
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "data": {"engine": "none", "proposed_category": None},
                "message": (
                    "Could not analyse this photo right now. It will still be "
                    "attached to your report."
                ),
            },
        )

    # Store the EXIF-stripped bytes, not the upload. A failure here is logged and
    # returns None: the analysis still goes back and the report is still filable.
    photo_path = await store_evidence(
        current_user["user_id"], result.prepared_jpeg, result.image_sha256
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "evidence_photo_path": photo_path,
                "engine": result.engine,
                "elapsed_seconds": result.elapsed_seconds,
                "image_sha256": result.image_sha256,
                "description": result.cues.description,
                "people_count": result.cues.people_count,
                "scene": result.cues.scene,
                "cues": result.cues.model_dump(
                    exclude={"description", "people_count", "scene"}
                ),
                "cues_fired": list(result.cues_fired),
                "proposed_category": result.proposed_category,
                "confidence": result.confidence,
                "reason": result.reason,
                "agreement": result.agreement,
                "unreachable_from_photo": list(UNREACHABLE_FROM_PHOTO),
            },
            "message": (
                f"Analysed by {result.engine} in {result.elapsed_seconds}s."
                if result.proposed_category
                else f"Nothing specific found. Analysed by {result.engine}."
            ),
        },
    )


@router.get("/crime-detection/evidence-url", response_model=dict)
async def evidence_photo_url(
    path: str,
    current_user: dict = Depends(get_current_user),
):
    """
    A short-lived URL for one stored evidence photo. D07.

    The bucket is private, so there is no permanent link to hand out. This mints
    a signed URL valid for an hour.

    **A caller may only sign their own photos.** Object paths begin with the
    owner's user id, so the check is a prefix comparison -- but it has to be
    here, because the service-role key the signing call uses bypasses row
    security entirely. Without this, any logged-in user could sign any path they
    could guess.
    """
    owner_prefix = f"{current_user['user_id']}/"
    if not path.startswith(owner_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That photo belongs to another report.",
        )

    url = await signed_url(path)
    if url is None:
        # Deleted from the bucket, or storage is unreachable. Either way the
        # screen shows "photo unavailable", which is the truth.
        return {
            "success": False,
            "data": {"url": None},
            "message": "That photo is no longer available.",
        }
    return {"success": True, "data": {"url": url}, "message": "Signed."}


@router.get("/crime-detection/status", response_model=dict)
async def get_crime_detection_status():
    """
    What the vision chain is configured to use, and which tiers can answer.

    Rewritten in D07. It used to report whether the YOLOv9c weights had loaded;
    there are no weights now. What matters instead is which tiers of
    `LLM_CHAIN_CRIME` are actually usable, because a missing key or a stopped
    Ollama is the failure that would otherwise only show up on stage.

    `configured` is not `reachable`: this does not call anything. A tier listed
    here can still fail, and the chain falls through when it does.
    """
    tiers = []
    for provider, model in chain(FEATURE_CRIME):
        if provider == "replay":
            captured = REPLAY_FIXTURE.is_file()
            tiers.append({
                "provider": provider,
                "model": model,
                "configured": captured,
                "note": (
                    "rehearsed photos captured"
                    if captured
                    else "no capture yet - run `python -m app.agents export-vision-replay`"
                ),
            })
            continue
        has_key = bool(keys_for(provider, FEATURE_CRIME))
        tiers.append({
            "provider": provider,
            "model": model,
            "configured": has_key,
            "note": (
                "ready" if has_key
                else f"no {provider.upper()}_KEY_{FEATURE_CRIME}_* key set"
            ),
        })

    usable = [t for t in tiers if t["configured"]]
    return {
        "success": bool(usable),
        "data": {
            "chain": tiers,
            "tiers_configured": len(usable),
            "approach": (
                "A vision-language model reports which physical cues are visible. "
                "Our own code maps cues to a candidate category. The reporter "
                "confirms it, so the filed category is always a human's."
            ),
        },
        "message": (
            f"{len(usable)} of {len(tiers)} tier(s) configured."
            if usable
            else "No tier is configured - photo analysis will be unavailable."
        ),
    }


@router.get("/crime-detection/supported-crimes", response_model=dict)
async def get_supported_crime_types():
    """
    Which categories a photograph can support, and which it cannot.

    It used to be impossible to answer honestly: the old endpoint enumerated
    object-detection rules whose required objects (`gun`, `blood`, `broken
    window`) were not in the detector's vocabulary at all, so it advertised
    categories nothing could ever produce.

    Only `fraud` is beyond a photograph now. Theft and robbery were on that list
    until 2026-10-10, on the reasoning that a photo cannot show ownership or who
    took what -- true, but the wrong conclusion. A photo *can* show goods going
    into a bag, or two people pulling one bag. Those propose at `weak`
    confidence and the reporter confirms, which is what the whole design is for.
    """
    return {
        "success": True,
        "data": {
            "proposable": sorted(PROPOSABLE_FROM_PHOTO),
            "not_proposable": sorted(UNREACHABLE_FROM_PHOTO),
            "why_not": {
                "fraud": "A document or a conversation, not a scene.",
            },
            "cues": sorted(CUE_FIELDS),
            "note": (
                "A photo cannot establish intent, consent, who started it, or "
                "whether a scene is staged. Categories are proposed, never filed."
            ),
        },
        "message": (
            f"{len(PROPOSABLE_FROM_PHOTO)} categories can be proposed from a photo, "
            f"{len(UNREACHABLE_FROM_PHOTO)} cannot."
        ),
    }
