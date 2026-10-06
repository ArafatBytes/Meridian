"""
Crime Decision Fusion Engine - Phase 4
Intelligent ML-based fusion of object detection, pose analysis, and scene classification
to make accurate, confidence-calibrated crime classification decisions.
"""
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class CrimeDecisionEngine:
    """
    Advanced decision fusion engine that combines:
    - Phase 1: Object detection signals (rule-based)
    - Phase 2: Pose and action signals (behavior analysis)
    - Phase 3: Scene and environmental signals (context awareness)
    
    Uses weighted voting, confidence calibration, and contextual reasoning.
    """
    
    # Crime type definitions with multi-signal requirements
    CRIME_PROFILES = {
        "assault": {
            "severity": "high",
            "weights": {
                "objects": 0.30,      # 30% weight on objects
                "pose": 0.45,         # 45% weight on actions (critical)
                "scene": 0.25         # 25% weight on environment
            },
            "object_signals": {
                "strong": ["knife", "gun", "baseball bat"],
                "moderate": ["person", "thrown object"],
                "context": ["broken window", "blood"]
            },
            "pose_signals": {
                "strong": ["punching", "kicking", "physical_altercation"],
                "moderate": ["hands_raised", "fallen", "threatening_behavior"],
                "weak": ["reaching", "running"]
            },
            "scene_signals": {
                "high_risk": ["dark alley", "empty road", "isolated"],
                "time_factors": ["nighttime", "dim lighting"],
                "crowd_factors": ["empty", "few people"]
            },
            "min_confidence_threshold": 0.40,
            "cross_validation": {
                "pose_required_if_no_weapon": True,
                "scene_boost_multiplier": 1.3
            }
        },
        
        "robbery": {
            "severity": "high",
            "weights": {
                "objects": 0.40,      # 40% weight on weapons
                "pose": 0.35,         # 35% weight on threatening behavior
                "scene": 0.25         # 25% weight on location
            },
            "object_signals": {
                "strong": ["gun", "knife"],
                "moderate": ["person", "handbag", "backpack"],
                "context": ["car", "money"]
            },
            "pose_signals": {
                "strong": ["hands_raised", "threatening_behavior"],
                "moderate": ["reaching", "running"],
                "weak": ["standing"]
            },
            "scene_signals": {
                "high_risk": ["dark alley", "parking lot", "empty road"],
                "time_factors": ["nighttime"],
                "crowd_factors": ["empty", "few people"]
            },
            "min_confidence_threshold": 0.45,
            "cross_validation": {
                "weapon_or_threat_required": True,
                "scene_boost_multiplier": 1.25
            }
        },
        
        "theft": {
            "severity": "medium",
            "weights": {
                "objects": 0.35,      # 35% weight on stolen items
                "pose": 0.40,         # 40% weight on suspicious actions
                "scene": 0.25         # 25% weight on opportunity
            },
            "object_signals": {
                "strong": ["handbag", "backpack", "laptop", "cell phone"],
                "moderate": ["person"],
                "context": ["car", "bicycle"]
            },
            "pose_signals": {
                "strong": ["reaching", "running"],
                "moderate": ["hands_raised", "crouching"],
                "weak": ["standing"]
            },
            "scene_signals": {
                "high_risk": ["parking lot", "public transport", "crowded"],
                "time_factors": [],  # Can happen anytime
                "crowd_factors": ["crowded", "moderate crowd"]  # Pickpockets in crowds
            },
            "min_confidence_threshold": 0.35,
            "cross_validation": {
                "suspicious_action_required": True,
                "scene_boost_multiplier": 1.2
            }
        },
        
        "burglary": {
            "severity": "high",
            "weights": {
                "objects": 0.40,      # 40% weight on entry signs
                "pose": 0.30,         # 30% weight on suspicious behavior
                "scene": 0.30         # 30% weight on location/time
            },
            "object_signals": {
                "strong": ["broken window", "door", "crowbar"],
                "moderate": ["person", "backpack"],
                "context": ["window", "building"]
            },
            "pose_signals": {
                "strong": ["crouching", "reaching"],
                "moderate": ["standing"],
                "weak": []
            },
            "scene_signals": {
                "high_risk": ["residential area", "building interior", "isolated"],
                "time_factors": ["nighttime", "dim lighting"],
                "crowd_factors": ["empty"]
            },
            "min_confidence_threshold": 0.40,
            "cross_validation": {
                "entry_sign_or_night_required": True,
                "scene_boost_multiplier": 1.35
            }
        },
        
        "harassment": {
            "severity": "medium",
            "weights": {
                "objects": 0.20,      # 20% weight on objects (less important)
                "pose": 0.50,         # 50% weight on behavior (critical)
                "scene": 0.30         # 30% weight on context
            },
            "object_signals": {
                "strong": [],
                "moderate": ["person"],
                "context": []
            },
            "pose_signals": {
                "strong": ["threatening_behavior", "confrontation"],
                "moderate": ["hands_raised", "reaching"],
                "weak": ["standing"]
            },
            "scene_signals": {
                "high_risk": ["public transport", "street"],
                "time_factors": ["nighttime"],
                "crowd_factors": ["few people", "empty"]
            },
            "min_confidence_threshold": 0.30,
            "cross_validation": {
                "interaction_required": True,
                "scene_boost_multiplier": 1.15
            }
        },
        
        "vandalism": {
            "severity": "low",
            "weights": {
                "objects": 0.60,      # 60% weight on damage evidence
                "pose": 0.20,         # 20% weight on actions
                "scene": 0.20         # 20% weight on location
            },
            "object_signals": {
                "strong": ["graffiti", "broken window", "damaged property"],
                "moderate": ["person", "spray paint"],
                "context": ["building", "car"]
            },
            "pose_signals": {
                "strong": ["reaching", "hands_raised"],
                "moderate": ["standing"],
                "weak": []
            },
            "scene_signals": {
                "high_risk": ["dark alley", "empty road"],
                "time_factors": ["nighttime"],
                "crowd_factors": ["empty"]
            },
            "min_confidence_threshold": 0.35,
            "cross_validation": {
                "damage_evidence_required": True,
                "scene_boost_multiplier": 1.1
            }
        }
    }
    
    def __init__(self):
        """Initialize the decision fusion engine."""
        logger.info("🧠 Initializing Crime Decision Fusion Engine (Phase 4)")
        self.decision_count = 0
        self.calibration_params = self._initialize_calibration()
        logger.info("✅ Decision engine initialized with ML fusion algorithms")
    
    def _initialize_calibration(self) -> Dict:
        """Initialize confidence calibration parameters."""
        return {
            "base_threshold": 0.25,
            "high_confidence_bar": 0.75,
            "multi_signal_bonus": 0.10,
            "single_signal_penalty": 0.15,
            "cross_validation_bonus": 0.12
        }
    
    def fuse_decision(
        self,
        object_detections: List[Dict],
        pose_data: Optional[Dict] = None,
        scene_data: Optional[Dict] = None
    ) -> Tuple[Optional[str], float, Dict]:
        """
        Main fusion method: Combines all AI signals into final decision.
        
        Args:
            object_detections: List of detected objects with confidence
            pose_data: Pose and action analysis results
            scene_data: Scene classification and environmental context
        
        Returns:
            Tuple of (crime_type, confidence, decision_details)
        """
        self.decision_count += 1
        start_time = datetime.now()
        
        logger.info(f"🔍 Starting decision fusion #{self.decision_count}")
        logger.info(f"   • Objects: {len(object_detections)} detections")
        logger.info(f"   • Pose data: {'✓' if pose_data else '✗'}")
        logger.info(f"   • Scene data: {'✓' if scene_data else '✗'}")
        
        # Step 1: Compute individual signal scores for each crime type
        crime_scores = {}
        
        for crime_type, profile in self.CRIME_PROFILES.items():
            scores = self._compute_multi_signal_score(
                crime_type,
                profile,
                object_detections,
                pose_data,
                scene_data
            )
            
            if scores["total_score"] > 0:
                crime_scores[crime_type] = scores
        
        # Step 2: Check if any crimes detected
        if not crime_scores:
            return self._no_crime_detected(object_detections)
        
        # Step 3: Select best candidate
        best_candidate = self._select_best_candidate(crime_scores)
        
        # Step 4: Cross-validate decision
        validated = self._cross_validate_decision(
            best_candidate["crime_type"],
            best_candidate["scores"],
            object_detections,
            pose_data,
            scene_data
        )
        
        if not validated["is_valid"]:
            # Try second-best candidate
            second_best = self._get_second_best(crime_scores, best_candidate["crime_type"])
            if second_best:
                logger.info(f"⚠️ First choice failed validation, trying: {second_best['crime_type']}")
                validated = self._cross_validate_decision(
                    second_best["crime_type"],
                    second_best["scores"],
                    object_detections,
                    pose_data,
                    scene_data
                )
                if validated["is_valid"]:
                    best_candidate = second_best
                else:
                    return self._no_crime_detected(object_detections, "validation_failed")
            else:
                return self._no_crime_detected(object_detections, "validation_failed")
        
        # Step 5: Calibrate final confidence
        final_confidence = self._calibrate_confidence(
            best_candidate["scores"],
            validated,
            pose_data is not None,
            scene_data is not None
        )
        
        # Step 6: Build decision details
        decision_time = (datetime.now() - start_time).total_seconds()
        details = self._build_decision_details(
            best_candidate,
            validated,
            final_confidence,
            decision_time,
            object_detections,
            pose_data,
            scene_data
        )
        
        crime_type = best_candidate["crime_type"]
        logger.info(f"✅ Decision: {crime_type} (confidence: {final_confidence:.1%}, time: {decision_time:.3f}s)")
        logger.info(f"   • Object score: {best_candidate['scores']['object_score']:.1f}")
        logger.info(f"   • Pose score: {best_candidate['scores']['pose_score']:.1f}")
        logger.info(f"   • Scene score: {best_candidate['scores']['scene_score']:.1f}")
        logger.info(f"   • Fusion score: {best_candidate['scores']['total_score']:.1f}")
        
        return crime_type, final_confidence, details
    
    def _compute_multi_signal_score(
        self,
        crime_type: str,
        profile: Dict,
        object_detections: List[Dict],
        pose_data: Optional[Dict],
        scene_data: Optional[Dict]
    ) -> Dict:
        """Compute weighted scores from all signals."""
        
        # Object signal score
        object_score = self._score_object_signals(
            profile["object_signals"],
            object_detections
        )
        
        # Pose signal score
        pose_score = self._score_pose_signals(
            profile["pose_signals"],
            pose_data
        ) if pose_data else 0.0
        
        # Scene signal score
        scene_score = self._score_scene_signals(
            profile["scene_signals"],
            scene_data
        ) if scene_data else 0.0
        
        # Apply weighted fusion
        weights = profile["weights"]
        
        # If a signal is missing, redistribute its weight
        available_signals = []
        if object_score > 0:
            available_signals.append("objects")
        if pose_data and pose_score > 0:
            available_signals.append("pose")
        if scene_data and scene_score > 0:
            available_signals.append("scene")
        
        # Normalize weights for available signals
        total_weight = sum(weights[sig] for sig in available_signals)
        if total_weight > 0:
            normalized_weights = {sig: weights[sig] / total_weight for sig in available_signals}
        else:
            normalized_weights = weights
        
        # Compute weighted score
        weighted_score = 0.0
        if "objects" in available_signals:
            weighted_score += object_score * normalized_weights.get("objects", 0)
        if "pose" in available_signals:
            weighted_score += pose_score * normalized_weights.get("pose", 0)
        if "scene" in available_signals:
            weighted_score += scene_score * normalized_weights.get("scene", 0)
        
        return {
            "object_score": object_score,
            "pose_score": pose_score,
            "scene_score": scene_score,
            "weighted_score": weighted_score,
            "total_score": weighted_score,
            "signals_used": len(available_signals),
            "weights_applied": normalized_weights
        }
    
    def _score_object_signals(self, signals: Dict, detections: List[Dict]) -> float:
        """Score based on object detections."""
        if not detections:
            return 0.0
        
        score = 0.0
        detected_objects = [d["object"] for d in detections]
        
        # Strong signals (high impact)
        for obj in signals.get("strong", []):
            if obj in detected_objects:
                score += 35.0
                # Add confidence boost
                for det in detections:
                    if det["object"] == obj:
                        score += det["confidence"] * 15.0
                        break
        
        # Moderate signals (medium impact)
        for obj in signals.get("moderate", []):
            if obj in detected_objects:
                score += 20.0
                for det in detections:
                    if det["object"] == obj:
                        score += det["confidence"] * 8.0
                        break
        
        # Context signals (low impact, but supportive)
        for obj in signals.get("context", []):
            if obj in detected_objects:
                score += 10.0
        
        # Multiple object bonus
        if len(set(detected_objects)) >= 3:
            score *= 1.15
        
        return min(score, 100.0)  # Cap at 100
    
    def _score_pose_signals(self, signals: Dict, pose_data: Dict) -> float:
        """Score based on pose and action analysis."""
        if not pose_data:
            return 0.0
        
        score = 0.0
        actions = pose_data.get("actions", [])
        threat_levels = pose_data.get("threat_levels", [])
        interaction = pose_data.get("interaction")
        
        # Strong action signals
        for action in signals.get("strong", []):
            if action in actions:
                score += 40.0
            # Check if it's an interaction type
            if interaction and action == interaction.get("interaction_type"):
                score += 45.0
        
        # Moderate action signals
        for action in signals.get("moderate", []):
            if action in actions:
                score += 25.0
        
        # Weak action signals
        for action in signals.get("weak", []):
            if action in actions:
                score += 12.0
        
        # Threat level boost
        high_threats = sum(1 for t in threat_levels if t == "high")
        medium_threats = sum(1 for t in threat_levels if t == "medium")
        
        score += high_threats * 20.0
        score += medium_threats * 10.0
        
        # Interaction risk boost
        if interaction:
            risk_level = interaction.get("risk_level")
            if risk_level == "high":
                score += 25.0
            elif risk_level == "medium":
                score += 15.0
        
        # Multi-person interaction bonus
        if pose_data.get("poses_detected", 0) >= 2:
            score *= 1.2
        
        return min(score, 100.0)  # Cap at 100
    
    def _score_scene_signals(self, signals: Dict, scene_data: Dict) -> float:
        """Score based on scene and environmental context."""
        if not scene_data:
            return 0.0
        
        score = 0.0
        scene_type = scene_data.get("scene_type", "")
        lighting = scene_data.get("lighting_condition", "")
        crowd = scene_data.get("crowd_density", "")
        risk_level = scene_data.get("risk_level", "")
        isolation = scene_data.get("isolation_level", "")
        
        # High-risk locations
        for location in signals.get("high_risk", []):
            if location in scene_type or location == isolation:
                score += 30.0
        
        # Time/lighting factors
        for time_factor in signals.get("time_factors", []):
            if time_factor in lighting:
                score += 20.0
        
        # Crowd factors (can be positive or negative depending on crime)
        for crowd_factor in signals.get("crowd_factors", []):
            if crowd_factor in crowd:
                score += 15.0
        
        # Overall risk level
        if risk_level == "high":
            score += 25.0
        elif risk_level == "medium":
            score += 12.0
        
        # Scene confidence boost
        scene_conf = scene_data.get("scene_confidence", 0.5)
        score *= (0.8 + scene_conf * 0.4)  # Scale by confidence
        
        return min(score, 100.0)  # Cap at 100
    
    def _select_best_candidate(self, crime_scores: Dict) -> Dict:
        """Select the crime type with highest fusion score."""
        best = max(
            crime_scores.items(),
            key=lambda x: x[1]["total_score"]
        )
        
        return {
            "crime_type": best[0],
            "scores": best[1]
        }
    
    def _get_second_best(self, crime_scores: Dict, exclude: str) -> Optional[Dict]:
        """Get second-best candidate for fallback."""
        remaining = {k: v for k, v in crime_scores.items() if k != exclude}
        if not remaining:
            return None
        
        best = max(
            remaining.items(),
            key=lambda x: x[1]["total_score"]
        )
        
        return {
            "crime_type": best[0],
            "scores": best[1]
        }
    
    def _cross_validate_decision(
        self,
        crime_type: str,
        scores: Dict,
        object_detections: List[Dict],
        pose_data: Optional[Dict],
        scene_data: Optional[Dict]
    ) -> Dict:
        """Cross-validate decision using crime-specific rules."""
        profile = self.CRIME_PROFILES[crime_type]
        validation = profile.get("cross_validation", {})
        
        is_valid = True
        validation_notes = []
        bonus_multiplier = 1.0
        
        detected_objects = [d["object"] for d in object_detections]
        
        # Check pose requirement if no weapon
        if validation.get("pose_required_if_no_weapon"):
            has_weapon = any(obj in detected_objects for obj in ["knife", "gun", "baseball bat"])
            has_pose_signals = pose_data and len(pose_data.get("actions", [])) > 0
            
            if not has_weapon and not has_pose_signals:
                is_valid = False
                validation_notes.append("Requires weapon OR pose signals")
            elif has_pose_signals:
                bonus_multiplier *= 1.1
                validation_notes.append("Pose signals confirm no-weapon assault")
        
        # Check weapon or threat requirement
        if validation.get("weapon_or_threat_required"):
            has_weapon = any(obj in detected_objects for obj in ["knife", "gun"])
            has_threat = pose_data and any(
                action in ["hands_raised", "threatening_behavior"]
                for action in pose_data.get("actions", [])
            )
            
            if not (has_weapon or has_threat):
                is_valid = False
                validation_notes.append("Requires weapon OR threatening behavior")
        
        # Check suspicious action requirement
        if validation.get("suspicious_action_required"):
            if not pose_data or len(pose_data.get("actions", [])) == 0:
                is_valid = False
                validation_notes.append("Requires suspicious action detected")
            else:
                bonus_multiplier *= 1.08
        
        # Check entry sign requirement
        if validation.get("entry_sign_or_night_required"):
            has_entry_sign = any(obj in detected_objects for obj in ["broken window", "door"])
            is_night = scene_data and "night" in scene_data.get("lighting_condition", "")
            
            if not (has_entry_sign or is_night):
                is_valid = False
                validation_notes.append("Requires entry sign OR nighttime")
        
        # Check interaction requirement
        if validation.get("interaction_required"):
            has_interaction = pose_data and pose_data.get("interaction") is not None
            
            if not has_interaction:
                is_valid = False
                validation_notes.append("Requires person-to-person interaction")
        
        # Check damage evidence requirement
        if validation.get("damage_evidence_required"):
            has_damage = any(
                obj in detected_objects
                for obj in ["graffiti", "broken window", "damaged property"]
            )
            
            if not has_damage:
                is_valid = False
                validation_notes.append("Requires visible damage evidence")
        
        # Scene boost multiplier
        if scene_data and scene_data.get("risk_level") == "high":
            bonus_multiplier *= validation.get("scene_boost_multiplier", 1.0)
            validation_notes.append(f"Scene boost: {validation.get('scene_boost_multiplier', 1.0):.2f}x")
        
        # Check minimum confidence threshold
        min_threshold = profile.get("min_confidence_threshold", 0.25)
        raw_confidence = scores["total_score"] / 100.0
        
        if raw_confidence < min_threshold:
            is_valid = False
            validation_notes.append(f"Below threshold: {raw_confidence:.2f} < {min_threshold:.2f}")
        
        return {
            "is_valid": is_valid,
            "validation_notes": validation_notes,
            "bonus_multiplier": bonus_multiplier,
            "min_threshold": min_threshold
        }
    
    def _calibrate_confidence(
        self,
        scores: Dict,
        validation: Dict,
        has_pose: bool,
        has_scene: bool
    ) -> float:
        """Calibrate final confidence score with bonuses/penalties."""
        
        # Start with normalized weighted score
        base_confidence = scores["total_score"] / 100.0
        
        # Apply validation bonus
        confidence = base_confidence * validation["bonus_multiplier"]
        
        # Multi-signal bonus
        signals_used = scores["signals_used"]
        if signals_used == 3:
            confidence += self.calibration_params["multi_signal_bonus"]
        elif signals_used == 1:
            confidence -= self.calibration_params["single_signal_penalty"]
        
        # Cross-validation bonus
        if validation["is_valid"]:
            confidence += self.calibration_params["cross_validation_bonus"]
        
        # Normalize to realistic range
        confidence = max(0.25, min(0.95, confidence))
        
        # Apply sigmoid-like calibration curve for more realistic distribution
        # This prevents over-confidence and under-confidence
        confidence = self._sigmoid_calibration(confidence)
        
        return round(confidence, 3)
    
    def _sigmoid_calibration(self, raw_conf: float) -> float:
        """Apply sigmoid calibration for realistic confidence distribution."""
        # Transform to make middle range more common
        if raw_conf < 0.5:
            return 0.25 + (raw_conf - 0.25) * 0.8
        else:
            return 0.45 + (raw_conf - 0.5) * 0.9
    
    def _build_decision_details(
        self,
        candidate: Dict,
        validation: Dict,
        final_confidence: float,
        decision_time: float,
        object_detections: List[Dict],
        pose_data: Optional[Dict],
        scene_data: Optional[Dict]
    ) -> Dict:
        """Build comprehensive decision details for transparency."""
        
        crime_type = candidate["crime_type"]
        scores = candidate["scores"]
        profile = self.CRIME_PROFILES[crime_type]
        
        return {
            "crime_type": crime_type,
            "confidence": final_confidence,
            "severity": profile["severity"],
            "decision_engine": "ml_fusion_v1",
            "signals": {
                "object_score": round(scores["object_score"], 2),
                "pose_score": round(scores["pose_score"], 2),
                "scene_score": round(scores["scene_score"], 2),
                "weighted_score": round(scores["weighted_score"], 2),
                "signals_used": scores["signals_used"],
                "weights_applied": scores["weights_applied"]
            },
            "validation": {
                "is_valid": validation["is_valid"],
                "bonus_multiplier": round(validation["bonus_multiplier"], 2),
                "notes": validation["validation_notes"]
            },
            "inputs": {
                "object_count": len(object_detections),
                "detected_objects": list(set(d["object"] for d in object_detections)),
                "person_count": sum(1 for d in object_detections if d["object"] == "person"),
                "has_pose_data": pose_data is not None,
                "has_scene_data": scene_data is not None
            },
            "processing": {
                "decision_time_ms": round(decision_time * 1000, 2),
                "decision_number": self.decision_count
            }
        }
    
    def _no_crime_detected(
        self,
        object_detections: List[Dict],
        reason: str = "no_indicators"
    ) -> Tuple[None, float, Dict]:
        """Return no crime detected result."""
        
        detected_objects = list(set(d["object"] for d in object_detections))
        
        logger.info(f"❌ No crime detected: {reason}")
        
        return None, 0.0, {
            "reason": reason,
            "detected_objects": detected_objects,
            "object_count": len(object_detections),
            "decision_engine": "ml_fusion_v1"
        }
    
    def get_engine_stats(self) -> Dict:
        """Get engine statistics."""
        return {
            "total_decisions": self.decision_count,
            "crime_types_supported": len(self.CRIME_PROFILES),
            "engine_version": "ml_fusion_v1",
            "calibration_active": True
        }
