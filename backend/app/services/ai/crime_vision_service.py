"""
Crime Vision Service - AI-powered image analysis for crime detection.
Phase 1 MVP: Object detection with rule-based classification.
Phase 2: Pose estimation and action recognition.
Phase 3: Scene classification and environmental context.
Phase 4: ML Fusion Decision Engine - Intelligent multi-signal integration.
"""
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
from PIL import Image
import io
from datetime import datetime

# Import AI services
from app.services.ai.pose_detection_service import PoseDetectionService
from app.services.ai.scene_classification_service import SceneClassificationService
from app.services.ai.crime_decision_engine import CrimeDecisionEngine

logger = logging.getLogger(__name__)


class CrimeVisionService:
    """AI service for analyzing crime images using YOLOv9."""
    
    # Crime classification rules based on detected objects
    CRIME_RULES = {
        "assault": {
            "objects": ["knife", "gun", "baseball bat", "person"],
            "min_persons": 2,
            "keywords": ["fight", "attack", "weapon"],
            "severity": "high"
        },
        "theft": {
            "objects": ["person", "handbag", "backpack", "laptop", "cell phone"],
            "min_persons": 1,
            "keywords": ["steal", "grab", "run"],
            "severity": "medium"
        },
        "vandalism": {
            "objects": ["graffiti", "broken window", "damaged car"],
            "keywords": ["damage", "destroy", "break"],
            "severity": "low"
        },
        "robbery": {
            "objects": ["gun", "knife", "person", "car"],
            "min_persons": 1,
            "keywords": ["weapon", "threat"],
            "severity": "high"
        },
        "burglary": {
            "objects": ["person", "window", "door", "broken glass"],
            "keywords": ["break in", "enter"],
            "severity": "high"
        },
        "harassment": {
            "objects": ["person"],
            "min_persons": 2,
            "keywords": ["threaten", "intimidate"],
            "severity": "medium"
        }
    }
    
    # Map YOLO object classes to crime-relevant objects
    YOLO_TO_CRIME_MAP = {
        "person": "person",
        "knife": "knife",
        "scissors": "knife",  # Similar weapon
        "car": "car",
        "truck": "car",
        "bus": "car",
        "motorcycle": "car",
        "handbag": "handbag",
        "backpack": "backpack",
        "suitcase": "backpack",
        "umbrella": "baseball bat",  # Potential weapon
        "baseball bat": "baseball bat",
        "sports ball": "thrown object",
        "bottle": "thrown object",
        "wine glass": "thrown object",
        "cell phone": "cell phone",
        "laptop": "laptop",
        "fire": "fire",
        "smoke": "smoke"
    }
    
    def __init__(self):
        """Initialize the crime vision service."""
        self.model = None
        self.model_loaded = False
        self.model_path = None
        
        # Initialize pose detection with error handling (Phase 2)
        try:
            self.pose_service = PoseDetectionService()
            logger.info("✅ Pose detection initialized")
        except Exception as e:
            logger.warning(f"⚠️ Pose detection initialization failed: {str(e)}")
            logger.warning("Continuing with object detection only...")
            self.pose_service = None
        
        # Initialize scene classification with error handling (Phase 3)
        try:
            self.scene_service = SceneClassificationService()
            logger.info("✅ Scene classification initialized")
        except Exception as e:
            logger.warning(f"⚠️ Scene classification initialization failed: {str(e)}")
            logger.warning("Continuing without scene analysis...")
            self.scene_service = None
        
        # Initialize ML fusion decision engine (Phase 4)
        try:
            self.decision_engine = CrimeDecisionEngine()
            logger.info("✅ ML Fusion Decision Engine initialized")
        except Exception as e:
            logger.warning(f"⚠️ Decision engine initialization failed: {str(e)}")
            logger.warning("Continuing with legacy rule-based system...")
            self.decision_engine = None
        
        logger.info("✅ CrimeVisionService initialized with all AI services")
    
    def load_models(self) -> bool:
        """
        Load YOLOv9 model.
        
        Returns:
            bool: True if models loaded successfully, False otherwise
        """
        try:
            from ultralytics import YOLO
            
            logger.info("Loading YOLOv9 model...")
            
            # Load YOLOv9 model (will auto-download if not present)
            self.model = YOLO('yolov9c.pt')
            self.model_path = 'yolov9c.pt'
            
            self.model_loaded = True
            logger.info("✅ YOLOv9 model loaded successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading models: {str(e)}")
            self.model_loaded = False
            return False
    
    def detect_objects(self, image: Image.Image, confidence: float = 0.25) -> List[Dict]:
        """
        Detect objects in image using YOLOv9.
        
        Args:
            image: PIL Image object
            confidence: Minimum confidence threshold (0.0 to 1.0)
        
        Returns:
            List of detected objects with confidence scores
        """
        if not self.model_loaded:
            raise RuntimeError("Models not loaded. Call load_models() first.")
        
        try:
            # Run YOLOv9 inference
            results = self.model(image, conf=confidence, verbose=False)
            
            detections = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Get object class name
                    cls_id = int(box.cls[0])
                    class_name = self.model.names[cls_id]
                    conf = float(box.conf[0])
                    
                    # Map to crime-relevant objects
                    mapped_object = self.YOLO_TO_CRIME_MAP.get(class_name, class_name)
                    
                    detections.append({
                        "object": mapped_object,
                        "original_class": class_name,
                        "confidence": round(conf, 3),
                        "bbox": box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    })
            
            logger.info(f"Detected {len(detections)} objects in image")
            return detections
            
        except Exception as e:
            logger.error(f"Error in object detection: {str(e)}")
            raise
    
    def classify_crime(
        self, 
        detections: List[Dict], 
        pose_data: Optional[Dict] = None,
        scene_data: Optional[Dict] = None,
        use_ml_fusion: bool = True
    ) -> Tuple[Optional[str], float, Dict]:
        """
        Classify crime type based on detected objects, pose/action analysis, and scene context.
        
        Phase 4: Uses ML Fusion Decision Engine for intelligent multi-signal integration.
        Falls back to legacy rule-based system if engine unavailable.
        
        Args:
            detections: List of detected objects from detect_objects()
            pose_data: Optional pose analysis data from MediaPipe
            scene_data: Optional scene classification data from CLIP
            use_ml_fusion: Whether to use Phase 4 ML fusion engine (default: True)
        
        Returns:
            Tuple of (crime_type, confidence, details)
        """
        # **Phase 4: Use ML Fusion Decision Engine if available**
        if use_ml_fusion and self.decision_engine:
            logger.info("🧠 Using ML Fusion Decision Engine (Phase 4)")
            try:
                crime_type, confidence, details = self.decision_engine.fuse_decision(
                    detections,
                    pose_data,
                    scene_data
                )
                
                # If decision engine succeeded, return its result
                if crime_type:
                    return crime_type, confidence, details
                else:
                    # No crime detected by engine
                    return None, 0.0, details
                    
            except Exception as e:
                logger.warning(f"⚠️ ML Fusion engine error, falling back to legacy: {str(e)}")
                # Fall through to legacy system
        
        # **Legacy rule-based system (Phase 1-3 integration)**
        logger.info("📋 Using legacy rule-based classification")
        return self._classify_crime_legacy(detections, pose_data, scene_data)
    
    def _classify_crime_legacy(
        self,
        detections: List[Dict],
        pose_data: Optional[Dict] = None,
        scene_data: Optional[Dict] = None
    ) -> Tuple[Optional[str], float, Dict]:
        """
        Legacy rule-based crime classification (Phase 1-3).
        Kept as fallback for the ML fusion engine.
        """
        # Count detected objects
        object_counts = {}
        total_confidence = 0
        
        for det in detections:
            obj = det["object"]
            if obj not in object_counts:
                object_counts[obj] = {"count": 0, "max_confidence": 0}
            object_counts[obj]["count"] += 1
            object_counts[obj]["max_confidence"] = max(
                object_counts[obj]["max_confidence"], 
                det["confidence"]
            )
            total_confidence += det["confidence"]
        
        # Count persons
        person_count = object_counts.get("person", {}).get("count", 0)
        
        # Score each crime type
        crime_scores = {}
        
        for crime_type, rules in self.CRIME_RULES.items():
            score = 0
            matched_objects = []
            
            # Check object matches
            for rule_obj in rules["objects"]:
                if rule_obj in object_counts:
                    score += 20  # Base score for matching object
                    score += object_counts[rule_obj]["max_confidence"] * 30  # Confidence boost
                    matched_objects.append(rule_obj)
            
            # Check person count requirement
            if "min_persons" in rules:
                if person_count >= rules["min_persons"]:
                    score += 25
                elif person_count > 0:
                    score += 10  # Partial credit
            
            # **Phase 2: Add pose/action-based scoring**
            if pose_data:
                actions = pose_data.get("actions", [])
                threat_levels = pose_data.get("threat_levels", [])
                interaction = pose_data.get("interaction")
                
                # High threat actions (punching, kicking)
                high_threat_actions = ["punching", "kicking"]
                if any(action in high_threat_actions for action in actions):
                    score += 35  # Strong indicator for assault/robbery
                    if crime_type == "assault":
                        score += 15  # Extra boost for assault
                
                # Medium threat actions (hands_raised, running, reaching)
                medium_threat_actions = ["hands_raised", "running", "reaching"]
                if any(action in medium_threat_actions for action in actions):
                    score += 20  # Moderate indicator
                    if crime_type in ["robbery", "theft"]:
                        score += 10  # Boost for theft-related crimes
                
                # Fallen or crouching (could indicate victim)
                victim_actions = ["fallen", "crouching"]
                if any(action in victim_actions for action in actions):
                    score += 15
                    if crime_type == "assault":
                        score += 10
                
                # Interaction analysis (Phase 2)
                if interaction:
                    interaction_type = interaction.get("interaction_type")
                    risk_level = interaction.get("risk_level")
                    
                    if interaction_type == "physical_altercation":
                        score += 30  # Strong indicator
                        if crime_type in ["assault", "harassment"]:
                            score += 15
                    elif interaction_type == "confrontation":
                        score += 20
                    elif interaction_type == "threatening_behavior":
                        score += 25
                    
                    # Risk level multiplier
                    if risk_level == "high":
                        score *= 1.15
                    elif risk_level == "medium":
                        score *= 1.05
            
            # **Phase 3: Add scene-based scoring**
            if scene_data:
                scene_type = scene_data.get("scene_type", "unknown")
                lighting = scene_data.get("lighting_condition", "unknown")
                crowd_density = scene_data.get("crowd_density", "unknown")
                risk_level = scene_data.get("risk_level", "medium")
                
                # High-risk locations increase score
                if risk_level == "high":
                    score += 25  # Strong environmental indicator
                    if crime_type in ["assault", "robbery", "theft"]:
                        score += 10  # Extra for crimes common in high-risk areas
                
                # Dark/nighttime increases risk
                if "nighttime" in lighting or "dim" in lighting:
                    score += 15
                    if crime_type in ["assault", "robbery", "burglary"]:
                        score += 5
                
                # Isolated locations increase risk
                isolation = scene_data.get("isolation_level", "unknown")
                if isolation == "isolated":
                    score += 20
                    if crime_type in ["assault", "robbery"]:
                        score += 10
                elif isolation == "semi-isolated":
                    score += 10
                
                # Specific scene type modifiers
                if scene_type == "dark alley" and crime_type in ["assault", "robbery"]:
                    score += 20
                elif scene_type == "parking lot" and crime_type in ["theft", "burglary"]:
                    score += 15
                elif scene_type == "public transport" and crime_type in ["theft", "harassment"]:
                    score += 10
            
            # Store if any score
            if score > 0:
                crime_scores[crime_type] = {
                    "score": score,
                    "matched_objects": matched_objects,
                    "severity": rules["severity"]
                }
        
        # Get best match
        if not crime_scores:
            return None, 0.0, {
                "reason": "No crime indicators detected",
                "detected_objects": list(object_counts.keys())
            }
        
        best_crime = max(crime_scores.items(), key=lambda x: x[1]["score"])
        crime_type = best_crime[0]
        crime_data = best_crime[1]
        
        # Calculate confidence (normalize score to 0-1)
        # Updated max score to account for pose and scene data
        max_possible_score = 200 if (pose_data and scene_data) else (150 if pose_data else (100 if scene_data else 75))
        confidence = min(crime_data["score"] / max_possible_score, 0.95)
        
        # Adjust confidence based on number of detections
        if len(detections) < 2:
            confidence *= 0.8  # Lower confidence with few detections
        elif len(detections) > 5:
            confidence *= 1.1  # Higher confidence with multiple detections
            confidence = min(confidence, 0.95)  # Cap at 95%
        
        # Boost confidence if pose data confirms the classification
        if pose_data:
            high_threat_count = sum(1 for level in pose_data.get("threat_levels", []) if level == "high")
            if high_threat_count > 0:
                confidence *= 1.1
                confidence = min(confidence, 0.95)
        
        # Boost confidence if scene data confirms high-risk environment
        if scene_data and scene_data.get("risk_level") == "high":
            confidence *= 1.08
            confidence = min(confidence, 0.95)
        
        details = {
            "matched_objects": crime_data["matched_objects"],
            "severity": crime_data["severity"],
            "person_count": person_count,
            "total_detections": len(detections),
            "all_objects": list(object_counts.keys())
        }
        
        logger.info(f"Classified as: {crime_type} (confidence: {confidence:.2%})")
        if pose_data:
            logger.info(f"Pose data enhanced classification: {len(pose_data.get('actions', []))} actions detected")
        if scene_data:
            logger.info(f"Scene context: {scene_data.get('scene_type')}, risk: {scene_data.get('risk_level')}")
        
        return crime_type, confidence, details
    
    def generate_title(self, crime_type: str, details: Dict, pose_data: Optional[Dict] = None, scene_data: Optional[Dict] = None) -> str:
        """Generate a descriptive title for the crime report (Phase 3 enhanced)."""
        # Extract from nested 'inputs' dict for ML Fusion, or top-level for legacy
        person_count = (
            details.get("inputs", {}).get("person_count") or
            details.get("person_count", 0)
        )
        # Use matched_objects if available (legacy), otherwise use detected_objects (ML Fusion)
        matched_objects = details.get("matched_objects", [])
        if not matched_objects:
            matched_objects = (
                details.get("inputs", {}).get("detected_objects") or
                details.get("detected_objects", [])
            )
        
        # Filter out 'person' from objects for title
        objects = [obj for obj in matched_objects if obj != "person"]
        
        # Extract pose/action info
        action_context = ""
        if pose_data:
            actions = pose_data.get("actions", [])
            if "punching" in actions or "kicking" in actions:
                action_context = " (physical violence detected)"
            elif "hands_raised" in actions:
                action_context = " (threatening behavior detected)"
            elif "fallen" in actions:
                action_context = " (person down)"
        
        # Extract scene context (Phase 3)
        scene_context = ""
        if scene_data:
            scene_type = scene_data.get("scene_type", "")
            lighting = scene_data.get("lighting_condition", "")
            
            if "dark alley" in scene_type:
                scene_context = " in dark alley"
            elif "parking lot" in scene_type:
                scene_context = " in parking lot"
            elif "public transport" in scene_type:
                scene_context = " on public transport"
            elif "nighttime" in lighting:
                scene_context = " at night"
        
        if crime_type == "assault":
            if "knife" in objects or "gun" in objects:
                weapon = "knife" if "knife" in objects else "gun"
                return f"Assault with {weapon} - {person_count} persons involved{scene_context}{action_context}"
            return f"Physical assault - {person_count} persons involved{scene_context}{action_context}"
        
        elif crime_type == "theft":
            stolen_items = [obj for obj in objects if obj in ["handbag", "backpack", "laptop", "cell phone"]]
            if stolen_items:
                return f"Theft of {stolen_items[0]}{scene_context}{action_context}"
            return f"Suspected theft incident{scene_context}{action_context}"
        
        elif crime_type == "vandalism":
            return f"Property vandalism detected{scene_context}{action_context}"
        
        elif crime_type == "robbery":
            return f"Armed robbery - {person_count} persons{scene_context}{action_context}"
        
        elif crime_type == "burglary":
            return f"Suspected burglary/break-in{scene_context}{action_context}"
        
        elif crime_type == "harassment":
            return f"Harassment incident - {person_count} persons{scene_context}{action_context}"
        
        return f"{crime_type.title()} incident detected{scene_context}{action_context}"
    
    def generate_description(self, crime_type: str, details: Dict, confidence: float, pose_data: Optional[Dict] = None, scene_data: Optional[Dict] = None) -> str:
        """Generate a detailed description for the crime report (Phase 2 enhanced)."""
        # Extract from nested 'inputs' dict for ML Fusion, or top-level for legacy
        all_objects = (
            details.get("inputs", {}).get("detected_objects") or
            details.get("all_objects", [])
        )
        person_count = (
            details.get("inputs", {}).get("person_count") or
            details.get("person_count", 0)
        )
        severity = details.get("severity", "medium")
        
        desc = f"AI-detected {crime_type} incident (confidence: {confidence:.1%}).\n\n"
        desc += f"Detected objects: {', '.join(all_objects) if all_objects else 'None'}\n"
        
        if person_count > 0:
            desc += f"Number of persons visible: {person_count}\n"
        
        # **Phase 2: Add pose/action analysis to description**
        if pose_data:
            poses_detected = pose_data.get("poses_detected", 0)
            actions = pose_data.get("actions", [])
            threat_levels = pose_data.get("threat_levels", [])
            interaction = pose_data.get("interaction")
            
            if poses_detected > 0:
                desc += f"\n📊 Pose Analysis:\n"
                desc += f"• Persons with detected poses: {poses_detected}\n"
                
                # Describe actions
                if actions:
                    unique_actions = list(set(actions))
                    action_desc = ", ".join(unique_actions)
                    desc += f"• Detected actions: {action_desc}\n"
                
                # Describe threat levels
                if threat_levels:
                    high_threats = sum(1 for t in threat_levels if t == "high")
                    medium_threats = sum(1 for t in threat_levels if t == "medium")
                    if high_threats > 0:
                        desc += f"• ⚠️ High threat behavior detected ({high_threats} person(s))\n"
                    elif medium_threats > 0:
                        desc += f"• ⚡ Medium threat behavior detected ({medium_threats} person(s))\n"
                
                # Describe interaction
                if interaction:
                    interaction_type = interaction.get("interaction_type")
                    risk_level = interaction.get("risk_level")
                    proximity = interaction.get("proximity")
                    
                    desc += f"\n👥 Interaction Analysis:\n"
                    desc += f"• Type: {interaction_type.replace('_', ' ').title()}\n"
                    desc += f"• Risk level: {risk_level}\n"
                    desc += f"• Proximity: {proximity}\n"
        
        # **Phase 3: Add scene/environment analysis to description**
        if scene_data and scene_data.get("scene_type") != "unknown":
            scene_type = scene_data.get("scene_type", "unknown")
            lighting = scene_data.get("lighting_condition", "unknown")
            crowd = scene_data.get("crowd_density", "unknown")
            risk = scene_data.get("risk_level", "medium")
            time_of_day = scene_data.get("time_of_day", "unknown")
            isolation = scene_data.get("isolation_level", "unknown")
            
            desc += f"\n🏙️ Scene & Environment Analysis:\n"
            desc += f"• Location type: {scene_type.replace('_', ' ').title()}\n"
            desc += f"• Lighting condition: {lighting}\n"
            desc += f"• Crowd density: {crowd}\n"
            desc += f"• Time of day: {time_of_day}\n"
            desc += f"• Isolation level: {isolation}\n"
            
            if risk == "high":
                desc += f"• ⚠️ HIGH RISK environment detected\n"
            elif risk == "medium":
                desc += f"• ⚡ Medium risk environment\n"
        
        desc += f"\nSeverity level: {severity}\n\n"
        desc += "This report was automatically generated by AI analysis"
        if pose_data and scene_data:
            desc += " with pose estimation, action recognition, and scene classification"
        elif pose_data:
            desc += " with pose estimation and action recognition"
        elif scene_data:
            desc += " with scene classification and environmental analysis"
        desc += ". Please review and add any additional details you observed."
        
        return desc
    
    def _estimate_severity(self, crime_type: str, details: Dict) -> str:
        """Estimate incident severity."""
        return self.CRIME_RULES.get(crime_type, {}).get("severity", "medium")
    
    async def analyze_crime_image(
        self, 
        image_data: bytes,
        confidence_threshold: float = 0.25,
        include_pose_analysis: bool = True,
        include_scene_analysis: bool = True,
        use_ml_fusion: bool = True
    ) -> Dict:
        """
        Main method to analyze a crime image.
        Phase 1: Object detection with YOLOv9
        Phase 2: Pose estimation and action recognition with MediaPipe
        Phase 3: Scene classification and environmental context with CLIP
        Phase 4: ML Fusion Decision Engine for intelligent classification
        
        Args:
            image_data: Image bytes
            confidence_threshold: Minimum confidence for object detection
            include_pose_analysis: Whether to include pose/action analysis (Phase 2)
            include_scene_analysis: Whether to include scene classification (Phase 3)
            use_ml_fusion: Whether to use ML Fusion Decision Engine (Phase 4)
        
        Returns:
            Dictionary with analysis results
        """
        start_time = datetime.now()
        
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Ensure RGB format
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            logger.info(f"Analyzing image: {image.size[0]}x{image.size[1]}")
            
            # Step 1: Detect objects
            detections = self.detect_objects(image, confidence_threshold)
            
            if not detections:
                return {
                    "success": False,
                    "message": "No relevant objects detected in image",
                    "crime_type": None,
                    "confidence": 0.0,
                    "processing_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Step 2: Detect poses and actions (Phase 2)
            pose_data = None
            if include_pose_analysis and self.pose_service:
                try:
                    poses = self.pose_service.detect_poses(image)
                    if poses:
                        interaction_analysis = self.pose_service.analyze_interaction(poses)
                        pose_data = {
                            "poses_detected": len(poses),
                            "actions": [p["action"] for p in poses],
                            "threat_levels": [p["threat_level"] for p in poses],
                            "interaction": interaction_analysis
                        }
                        logger.info(f"Detected {len(poses)} pose(s) with actions: {pose_data['actions']}")
                except Exception as e:
                    logger.warning(f"Pose detection failed (continuing without it): {str(e)}")
            elif include_pose_analysis and not self.pose_service:
                logger.debug("Pose detection requested but service not available")
            
            # Step 2.5: Classify scene and environment (Phase 3)
            scene_data = None
            if include_scene_analysis and self.scene_service:
                try:
                    scene_data = self.scene_service.classify_scene(image)
                    logger.info(f"Scene classified: {scene_data['scene_type']} (risk: {scene_data['risk_level']}, lighting: {scene_data['lighting_condition']})")
                except Exception as e:
                    logger.warning(f"Scene classification failed (continuing without it): {str(e)}")
            elif include_scene_analysis and not self.scene_service:
                logger.debug("Scene classification requested but service not available")
            
            # Step 3: Classify crime (Phase 4: ML Fusion Decision Engine)
            crime_type, confidence, details = self.classify_crime(
                detections, 
                pose_data, 
                scene_data,
                use_ml_fusion=use_ml_fusion
            )
            
            if not crime_type:
                return {
                    "success": False,
                    "message": details.get("reason", "Unable to classify crime"),
                    "detected_objects": details.get("detected_objects", []),
                    "pose_analysis": pose_data,
                    "scene_analysis": scene_data,
                    "crime_type": None,
                    "confidence": 0.0,
                    "processing_time": (datetime.now() - start_time).total_seconds()
                }
            
            # Step 4: Generate report content (enhanced with pose and scene data)
            title = self.generate_title(crime_type, details, pose_data, scene_data)
            description = self.generate_description(crime_type, details, confidence, pose_data, scene_data)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Determine which model version/engine was used
            if use_ml_fusion and self.decision_engine:
                model_version = "yolov9c+mediapipe+clip+ml_fusion"  # Phase 4
                decision_engine = details.get("decision_engine", "ml_fusion_v1")
            else:
                model_version = "yolov9c+mediapipe+clip"  # Phase 3
                decision_engine = "rule_based"
            
            result = {
                "success": True,
                "crime_type": crime_type,
                "confidence": round(confidence, 3),
                "title": title,
                "description": description,
                "severity": details["severity"],
                "details": {
                    # Extract from nested 'inputs' dict for ML Fusion, or top-level for legacy
                    "detected_objects": (
                        details.get("inputs", {}).get("detected_objects") or
                        details.get("all_objects") or
                        details.get("detected_objects", [])
                    ),
                    "person_count": (
                        details.get("inputs", {}).get("person_count") or
                        details.get("person_count", 0)
                    ),
                    "total_detections": (
                        details.get("inputs", {}).get("object_count") or
                        details.get("total_detections", len(detections))
                    ),
                    "matched_objects": details.get("matched_objects", [])
                },
                "pose_analysis": pose_data,  # Phase 2 data
                "scene_analysis": scene_data,  # Phase 3 data
                "decision_engine": decision_engine,  # Phase 4 info - NEW
                "fusion_signals": details.get("signals"),  # Phase 4 signal breakdown - NEW
                "processing_time": round(processing_time, 2),
                "model_version": model_version,  # Updated: Phase 4
                "confidence_threshold": confidence_threshold
            }
            
            logger.info(f"✅ Analysis complete in {processing_time:.2f}s: {crime_type} ({confidence:.1%})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error analyzing image: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Error analyzing image: {str(e)}",
                "crime_type": None,
                "confidence": 0.0,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }


# Global service instance
_crime_vision_service: Optional[CrimeVisionService] = None


def get_crime_vision_service() -> CrimeVisionService:
    """Get or create the global crime vision service instance."""
    global _crime_vision_service
    
    if _crime_vision_service is None:
        _crime_vision_service = CrimeVisionService()
        
        # Auto-load models
        if not _crime_vision_service.model_loaded:
            success = _crime_vision_service.load_models()
            if not success:
                logger.warning("Failed to auto-load models. Call /models/status to retry.")
    
    return _crime_vision_service
