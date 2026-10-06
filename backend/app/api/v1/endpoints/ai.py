"""
AI and NLP API Endpoints
Speech-to-Text, Crime Detection, and other AI services
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, status
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from app.services.ai.speech_service import speech_service
from app.services.ai.crime_vision_service import get_crime_vision_service

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
    file: UploadFile = File(..., description="Crime scene image to analyze"),
    confidence_threshold: float = 0.25,
    include_pose_analysis: bool = True,
    include_scene_analysis: bool = True,
    use_ml_fusion: bool = True
):
    """
    Analyze an image for crime detection using AI (Multi-Phase System).
    
    **Phase 1: Object Detection**
    - YOLOv9 for detecting persons, weapons, vehicles, etc.
    - Rule-based crime classification
    
    **Phase 2: Pose & Action Analysis**
    - MediaPipe pose estimation
    - Action recognition (punching, kicking, running, etc.)
    - Threat level assessment
    - Multi-person interaction analysis
    
    **Phase 3: Scene Classification**
    - CLIP-based scene understanding
    - Environmental context (lighting, crowd, location type)
    - Risk level assessment
    
    **Phase 4: ML Fusion Engine (NEW!)**
    - Intelligent multi-signal integration
    - Weighted decision fusion
    - Confidence calibration
    - Cross-validation rules
    
    **Supported Crime Types:**
    - Assault (weapons, fighting)
    - Robbery (armed theft)
    - Theft (stolen items, pickpocketing)
    - Burglary (break-in)
    - Harassment (threatening behavior)
    - Vandalism (property damage)
    
    **Parameters:**
    - file: Image file (JPEG, PNG, etc.)
    - confidence_threshold: Detection confidence (0.0-1.0, default 0.25)
    - include_pose_analysis: Enable Phase 2 pose detection (default True)
    - include_scene_analysis: Enable Phase 3 scene classification (default True)
    - use_ml_fusion: Enable Phase 4 ML fusion engine (default True)
    
    **Returns:**
    - crime_type: Detected crime category
    - confidence: Classification confidence (0-1)
    - title: Auto-generated report title
    - description: Auto-generated report description
    - details: Object detection details
    - pose_analysis: Pose and action data (Phase 2)
    - scene_analysis: Environmental context (Phase 3)
    - decision_engine: Engine used ("ml_fusion_v1" or "rule_based")
    - fusion_signals: Signal breakdown (Phase 4)
    - processing_time: Analysis duration in seconds
    - model_version: AI models used
    
    **Example:**
    ```python
    files = {'file': open('crime_scene.jpg', 'rb')}
    response = requests.post(
        'http://localhost:8000/api/v1/ai/crime-detection/analyze',
        files=files,
        params={
            'confidence_threshold': 0.3,
            'include_pose_analysis': True,
            'include_scene_analysis': True,
            'use_ml_fusion': True
        }
    )
    ```
    """
    logger.info(f"🔍 Crime detection request: {file.filename}")
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Please upload an image."
        )
    
    # Validate confidence threshold
    if not 0.0 <= confidence_threshold <= 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confidence_threshold must be between 0.0 and 1.0"
        )
    
    try:
        # Get crime vision service
        service = get_crime_vision_service()
        
        if not service.model_loaded:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI models not loaded. Run 'python scripts/download_models.py' first, or contact administrator."
            )
        
        # Read image data
        image_data = await file.read()
        
        if len(image_data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file received"
            )
        
        # Analyze image
        result = await service.analyze_crime_image(
            image_data=image_data,
            confidence_threshold=confidence_threshold,
            include_pose_analysis=include_pose_analysis,
            include_scene_analysis=include_scene_analysis,
            use_ml_fusion=use_ml_fusion
        )
        
        # Log result
        if result["success"]:
            logger.info(
                f"✅ Detection successful: {result['crime_type']} "
                f"({result['confidence']:.1%}) in {result['processing_time']:.2f}s"
            )
        else:
            logger.warning(f"⚠️  Detection unsuccessful: {result.get('message')}")
        
        return JSONResponse(
            status_code=200 if result["success"] else 400,
            content={
                "success": result["success"],
                "data": result if result["success"] else {
                    # Include detected_objects and analysis data even when no crime detected
                    "detected_objects": result.get("detected_objects", []),
                    "pose_analysis": result.get("pose_analysis"),
                    "scene_analysis": result.get("scene_analysis"),
                    "processing_time": result.get("processing_time"),
                },
                "message": result.get("message", "Crime analysis completed" if result["success"] else "Analysis failed")
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error analyzing crime image: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing image: {str(e)}"
        )


@router.get("/crime-detection/status", response_model=dict)
async def get_crime_detection_status():
    """
    Get the status of crime detection AI models.
    
    **Returns:**
    - Model loading status
    - Model version information
    - Readiness for inference
    """
    try:
        service = get_crime_vision_service()
        
        if service.model_loaded:
            return {
                "success": True,
                "data": {
                    "loaded": True,
                    "model_name": "YOLOv9c",
                    "model_version": "9.0",
                    "status": "ready",
                    "provider": "Ultralytics YOLO",
                    "phase": "1 - MVP"
                },
                "message": "Crime detection models are ready"
            }
        else:
            # Try to load models
            logger.info("Attempting to load crime detection models...")
            success = service.load_models()
            
            if success:
                return {
                    "success": True,
                    "data": {
                        "loaded": True,
                        "model_name": "YOLOv9c",
                        "status": "ready"
                    },
                    "message": "Models loaded successfully"
                }
            else:
                return {
                    "success": False,
                    "data": {
                        "loaded": False,
                        "model_name": "YOLOv9c",
                        "status": "failed"
                    },
                    "message": "Failed to load models. Run 'python scripts/download_models.py' first."
                }
    
    except Exception as e:
        logger.error(f"Error checking model status: {str(e)}")
        return {
            "success": False,
            "data": {
                "loaded": False,
                "status": "error",
                "error": str(e)
            },
            "message": f"Error checking model status: {str(e)}"
        }


@router.get("/crime-detection/supported-crimes", response_model=dict)
async def get_supported_crime_types():
    """
    Get list of crime types that can be detected.
    
    **Returns:**
    - List of supported crime types
    - Severity levels
    - Required objects for detection
    """
    try:
        service = get_crime_vision_service()
        
        supported = []
        for crime_type, rules in service.CRIME_RULES.items():
            supported.append({
                "crime_type": crime_type,
                "severity": rules["severity"],
                "required_objects": rules["objects"][:3],  # First 3 objects
                "min_persons": rules.get("min_persons", 0),
                "description": f"Detects {crime_type} based on: {', '.join(rules['objects'][:3])}"
            })
        
        return {
            "success": True,
            "data": {
                "supported_crimes": supported,
                "total": len(supported),
                "phase": "1 - MVP"
            },
            "message": "Supported crime types retrieved successfully"
        }
    
    except Exception as e:
        logger.error(f"Error getting supported crimes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving supported crimes: {str(e)}"
        )

