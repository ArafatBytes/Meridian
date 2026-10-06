"""
Crime AI API endpoints for image analysis.
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel, Field

from app.services.ai.crime_vision_service import get_crime_vision_service

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalysisResponse(BaseModel):
    """Response model for crime image analysis."""
    success: bool
    message: Optional[str] = None
    crime_type: Optional[str] = None
    confidence: float
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    details: Optional[dict] = None
    processing_time: float
    model_version: Optional[str] = None


class ModelStatus(BaseModel):
    """Model status information."""
    loaded: bool
    model_name: str
    status: str
    error: Optional[str] = None


class SupportedCrime(BaseModel):
    """Supported crime type information."""
    crime_type: str
    severity: str
    required_objects: list
    description: str


@router.post("/analyze-image", response_model=AnalysisResponse)
async def analyze_crime_image(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.25
):
    """
    Analyze an image for crime detection using AI.
    
    Args:
        file: Image file (JPEG, PNG, etc.)
        confidence_threshold: Minimum confidence for object detection (0.0-1.0)
    
    Returns:
        Analysis results with crime type, confidence, and suggested report content
    
    Example:
        ```python
        files = {'file': open('crime_image.jpg', 'rb')}
        response = requests.post(
            'http://localhost:8000/crime-ai/analyze-image',
            files=files,
            params={'confidence_threshold': 0.3}
        )
        ```
    """
    logger.info(f"Received image analysis request: {file.filename}")
    
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
                detail="AI models not loaded. Please contact administrator or check /models/status"
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
            confidence_threshold=confidence_threshold
        )
        
        # Log result
        if result["success"]:
            logger.info(
                f"✅ Analysis successful: {result['crime_type']} "
                f"({result['confidence']:.1%}) in {result['processing_time']:.2f}s"
            )
        else:
            logger.warning(f"⚠️  Analysis unsuccessful: {result.get('message')}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing image: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing image: {str(e)}"
        )


@router.get("/models/status", response_model=ModelStatus)
async def get_model_status():
    """
    Get the status of AI models.
    
    Returns:
        Model loading status and information
    """
    try:
        service = get_crime_vision_service()
        
        if service.model_loaded:
            return {
                "loaded": True,
                "model_name": "YOLOv9c",
                "status": "ready",
                "error": None
            }
        else:
            # Try to load models
            logger.info("Attempting to load models...")
            success = service.load_models()
            
            if success:
                return {
                    "loaded": True,
                    "model_name": "YOLOv9c",
                    "status": "ready",
                    "error": None
                }
            else:
                return {
                    "loaded": False,
                    "model_name": "YOLOv9c",
                    "status": "failed",
                    "error": "Failed to load models. Run 'python scripts/download_models.py' first."
                }
    
    except Exception as e:
        logger.error(f"Error checking model status: {str(e)}")
        return {
            "loaded": False,
            "model_name": "YOLOv9c",
            "status": "error",
            "error": str(e)
        }


@router.get("/supported-crimes", response_model=list[SupportedCrime])
async def get_supported_crimes():
    """
    Get list of crime types that can be detected.
    
    Returns:
        List of supported crime types with descriptions
    """
    service = get_crime_vision_service()
    
    supported = []
    for crime_type, rules in service.CRIME_RULES.items():
        supported.append({
            "crime_type": crime_type,
            "severity": rules["severity"],
            "required_objects": rules["objects"],
            "description": f"Detects {crime_type} based on objects: {', '.join(rules['objects'][:3])}"
        })
    
    return supported


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Service health status
    """
    try:
        service = get_crime_vision_service()
        return {
            "status": "healthy",
            "service": "crime-ai",
            "models_loaded": service.model_loaded
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "crime-ai",
                "error": str(e)
            }
        )
