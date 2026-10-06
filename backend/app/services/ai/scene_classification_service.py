"""
Scene Classification Service using CLIP
Analyzes environmental context for crime detection
"""
import logging
import torch
from typing import Dict, Any, List, Tuple
from PIL import Image
import numpy as np
from transformers import CLIPProcessor, CLIPModel

logger = logging.getLogger(__name__)


class SceneClassificationService:
    """
    Service for classifying scenes and environmental context using CLIP
    """
    
    # Scene categories for crime detection
    SCENE_CATEGORIES = [
        "street",
        "dark alley",
        "park",
        "building interior",
        "parking lot",
        "store",
        "residential area",
        "public transport",
        "commercial area",
        "empty road"
    ]
    
    # Lighting conditions
    LIGHTING_CONDITIONS = [
        "bright daylight",
        "nighttime",
        "dim lighting",
        "well-lit indoor"
    ]
    
    # Crowd density
    CROWD_DENSITY_LEVELS = [
        "empty",
        "few people",
        "moderate crowd",
        "crowded"
    ]
    
    # Risk levels per scene type
    SCENE_RISK_LEVELS = {
        "dark alley": "high",
        "empty road": "high",
        "parking lot": "medium",
        "public transport": "medium",
        "street": "low",
        "park": "low",
        "building interior": "low",
        "store": "low",
        "residential area": "low",
        "commercial area": "low"
    }
    
    def __init__(self):
        """Initialize CLIP model for scene classification"""
        try:
            logger.info("Loading CLIP model for scene classification...")
            
            # Use smaller CLIP model for faster inference
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            # Move to CPU (or GPU if available)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode
            
            logger.info(f"✅ Scene Classification Service initialized successfully (device: {self.device})")
            
        except Exception as e:
            logger.error(f"Failed to initialize Scene Classification Service: {str(e)}")
            raise
    
    def classify_scene(self, image: Image.Image) -> Dict[str, Any]:
        """
        Classify the scene type from an image
        
        Args:
            image: PIL Image object
            
        Returns:
            Dictionary with scene classification results
        """
        try:
            # Classify scene type
            scene_type, scene_confidence = self._classify_category(
                image, 
                self.SCENE_CATEGORIES,
                "a photo of "
            )
            
            # Classify lighting condition
            lighting, lighting_confidence = self._classify_category(
                image,
                self.LIGHTING_CONDITIONS,
                "a photo taken in "
            )
            
            # Classify crowd density
            crowd_density, crowd_confidence = self._classify_category(
                image,
                self.CROWD_DENSITY_LEVELS,
                "a photo showing "
            )
            
            # Determine environmental risk level
            risk_level = self._calculate_environmental_risk(
                scene_type, 
                lighting, 
                crowd_density
            )
            
            # Additional environmental factors
            time_of_day = self._infer_time_of_day(lighting)
            isolation_level = self._assess_isolation(crowd_density, scene_type)
            
            result = {
                "scene_type": scene_type,
                "scene_confidence": round(scene_confidence, 3),
                "lighting_condition": lighting,
                "lighting_confidence": round(lighting_confidence, 3),
                "crowd_density": crowd_density,
                "crowd_confidence": round(crowd_confidence, 3),
                "risk_level": risk_level,
                "time_of_day": time_of_day,
                "isolation_level": isolation_level
            }
            
            logger.info(
                f"Scene classified: {scene_type} ({scene_confidence:.2%}), "
                f"lighting: {lighting}, crowd: {crowd_density}, risk: {risk_level}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error classifying scene: {str(e)}")
            return self._get_default_scene()
    
    def _classify_category(
        self, 
        image: Image.Image, 
        categories: List[str],
        prefix: str = ""
    ) -> Tuple[str, float]:
        """
        Classify image into one of the given categories using CLIP
        
        Args:
            image: PIL Image
            categories: List of category names
            prefix: Text prefix for prompts (e.g., "a photo of ")
            
        Returns:
            Tuple of (best_category, confidence_score)
        """
        try:
            # Prepare text prompts
            text_prompts = [f"{prefix}{category}" for category in categories]
            
            # Process inputs
            inputs = self.processor(
                text=text_prompts,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1)
            
            # Get best match
            best_idx = probs.argmax().item()
            confidence = probs[0][best_idx].item()
            
            return categories[best_idx], confidence
            
        except Exception as e:
            logger.error(f"Error in category classification: {str(e)}")
            return categories[0], 0.5
    
    def _calculate_environmental_risk(
        self, 
        scene_type: str, 
        lighting: str, 
        crowd_density: str
    ) -> str:
        """
        Calculate environmental risk level based on scene factors
        
        Args:
            scene_type: Type of scene
            lighting: Lighting condition
            crowd_density: Crowd density level
            
        Returns:
            Risk level: "high", "medium", "low"
        """
        # Base risk from scene type
        base_risk = self.SCENE_RISK_LEVELS.get(scene_type, "medium")
        
        # Risk modifiers
        risk_score = 0
        
        if base_risk == "high":
            risk_score = 3
        elif base_risk == "medium":
            risk_score = 2
        else:
            risk_score = 1
        
        # Lighting increases risk
        if "nighttime" in lighting or "dim" in lighting:
            risk_score += 1
        
        # Empty places increase risk
        if crowd_density == "empty":
            risk_score += 1
        elif crowd_density == "few people":
            risk_score += 0.5
        
        # Crowded places can also be risky
        if crowd_density == "crowded":
            risk_score += 0.5
        
        # Final risk level
        if risk_score >= 4:
            return "high"
        elif risk_score >= 2.5:
            return "medium"
        else:
            return "low"
    
    def _infer_time_of_day(self, lighting: str) -> str:
        """
        Infer time of day from lighting condition
        
        Args:
            lighting: Lighting condition
            
        Returns:
            Time of day: "day", "night", "evening"
        """
        if "nighttime" in lighting:
            return "night"
        elif "dim" in lighting:
            return "evening"
        else:
            return "day"
    
    def _assess_isolation(self, crowd_density: str, scene_type: str) -> str:
        """
        Assess isolation level of the location
        
        Args:
            crowd_density: Crowd density level
            scene_type: Type of scene
            
        Returns:
            Isolation level: "isolated", "semi-isolated", "populated"
        """
        if crowd_density == "empty":
            if scene_type in ["dark alley", "empty road", "parking lot"]:
                return "isolated"
            else:
                return "semi-isolated"
        elif crowd_density == "few people":
            return "semi-isolated"
        else:
            return "populated"
    
    def _get_default_scene(self) -> Dict[str, Any]:
        """
        Return default scene classification when detection fails
        
        Returns:
            Default scene dictionary
        """
        return {
            "scene_type": "unknown",
            "scene_confidence": 0.0,
            "lighting_condition": "unknown",
            "lighting_confidence": 0.0,
            "crowd_density": "unknown",
            "crowd_confidence": 0.0,
            "risk_level": "medium",
            "time_of_day": "unknown",
            "isolation_level": "unknown"
        }
    
    def get_scene_context_text(self, scene_data: Dict[str, Any]) -> str:
        """
        Generate human-readable scene context text
        
        Args:
            scene_data: Scene classification result
            
        Returns:
            Descriptive text about the scene
        """
        scene = scene_data.get("scene_type", "unknown")
        lighting = scene_data.get("lighting_condition", "unknown")
        crowd = scene_data.get("crowd_density", "unknown")
        risk = scene_data.get("risk_level", "medium")
        
        context = f"Scene: {scene.replace('_', ' ').title()}"
        
        if lighting != "unknown":
            context += f", Lighting: {lighting}"
        
        if crowd != "unknown":
            context += f", Crowd: {crowd}"
        
        if risk != "medium":
            context += f" (⚠️ {risk.upper()} risk environment)"
        
        return context
    
    def __del__(self):
        """Cleanup model resources"""
        if hasattr(self, 'model'):
            del self.model
            del self.processor
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
