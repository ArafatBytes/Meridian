"""
Pose Detection Service using MediaPipe
Analyzes human poses and actions for crime detection
"""
import logging
import numpy as np
import mediapipe as mp
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import cv2

logger = logging.getLogger(__name__)


class PoseDetectionService:
    """
    Service for detecting human poses and analyzing actions using MediaPipe
    """
    
    def __init__(self):
        """Initialize MediaPipe Pose detector"""
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose_detector = self.mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            enable_segmentation=False,
            min_detection_confidence=0.5
        )
        logger.info("✅ Pose Detection Service initialized successfully")
    
    def detect_poses(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Detect all human poses in the image
        
        Args:
            image: PIL Image object
            
        Returns:
            List of pose detections with landmarks and actions
        """
        try:
            # Convert PIL Image to OpenCV format
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            image_rgb = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)
            
            # Process image with MediaPipe
            results = self.pose_detector.process(image_rgb)
            
            poses = []
            
            if results.pose_landmarks:
                # Extract pose landmarks
                landmarks = self._extract_landmarks(results.pose_landmarks)
                
                # Analyze pose for actions
                action = self._analyze_action(landmarks)
                
                # Determine threat level
                threat_level = self._calculate_threat_level(action, landmarks)
                
                poses.append({
                    "landmarks": landmarks,
                    "action": action,
                    "threat_level": threat_level,
                    "confidence": results.pose_landmarks.landmark[0].visibility
                })
            
            return poses
            
        except Exception as e:
            logger.error(f"Error detecting poses: {str(e)}")
            return []
    
    def _extract_landmarks(self, pose_landmarks) -> Dict[str, Dict[str, float]]:
        """
        Extract pose landmarks into a structured format
        
        Args:
            pose_landmarks: MediaPipe pose landmarks
            
        Returns:
            Dictionary of landmark positions
        """
        landmarks = {}
        landmark_names = [
            "nose", "left_eye_inner", "left_eye", "left_eye_outer",
            "right_eye_inner", "right_eye", "right_eye_outer",
            "left_ear", "right_ear", "mouth_left", "mouth_right",
            "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_pinky", "right_pinky",
            "left_index", "right_index", "left_thumb", "right_thumb",
            "left_hip", "right_hip", "left_knee", "right_knee",
            "left_ankle", "right_ankle", "left_heel", "right_heel",
            "left_foot_index", "right_foot_index"
        ]
        
        for idx, landmark in enumerate(pose_landmarks.landmark):
            if idx < len(landmark_names):
                landmarks[landmark_names[idx]] = {
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z,
                    "visibility": landmark.visibility
                }
        
        return landmarks
    
    def _analyze_action(self, landmarks: Dict[str, Dict[str, float]]) -> str:
        """
        Analyze pose to determine the action being performed
        
        Args:
            landmarks: Dictionary of pose landmarks
            
        Returns:
            String describing the detected action
        """
        try:
            # Get key landmarks
            left_shoulder = landmarks.get("left_shoulder", {})
            right_shoulder = landmarks.get("right_shoulder", {})
            left_elbow = landmarks.get("left_elbow", {})
            right_elbow = landmarks.get("right_elbow", {})
            left_wrist = landmarks.get("left_wrist", {})
            right_wrist = landmarks.get("right_wrist", {})
            left_hip = landmarks.get("left_hip", {})
            right_hip = landmarks.get("right_hip", {})
            left_knee = landmarks.get("left_knee", {})
            right_knee = landmarks.get("right_knee", {})
            
            # Check for raised hands (surrender/threat)
            if self._are_hands_raised(left_shoulder, left_wrist, right_shoulder, right_wrist):
                return "hands_raised"
            
            # Check for punching pose
            if self._is_punching(left_shoulder, left_elbow, left_wrist, right_shoulder, right_elbow, right_wrist):
                return "punching"
            
            # Check for kicking pose
            if self._is_kicking(left_hip, left_knee, right_hip, right_knee):
                return "kicking"
            
            # Check for grabbing/reaching
            if self._is_reaching(left_shoulder, left_wrist, right_shoulder, right_wrist):
                return "reaching"
            
            # Check for crouching/hiding
            if self._is_crouching(left_shoulder, left_hip, left_knee):
                return "crouching"
            
            # Check for running
            if self._is_running(left_hip, left_knee, right_hip, right_knee):
                return "running"
            
            # Check for fallen/lying down
            if self._is_fallen(left_shoulder, left_hip):
                return "fallen"
            
            return "standing"
            
        except Exception as e:
            logger.error(f"Error analyzing action: {str(e)}")
            return "unknown"
    
    def _are_hands_raised(self, left_shoulder: Dict, left_wrist: Dict, 
                          right_shoulder: Dict, right_wrist: Dict) -> bool:
        """Check if hands are raised above shoulders"""
        if not all([left_shoulder, left_wrist, right_shoulder, right_wrist]):
            return False
        
        left_raised = left_wrist.get("y", 1) < left_shoulder.get("y", 0) - 0.1
        right_raised = right_wrist.get("y", 1) < right_shoulder.get("y", 0) - 0.1
        
        return left_raised or right_raised
    
    def _is_punching(self, left_shoulder: Dict, left_elbow: Dict, left_wrist: Dict,
                     right_shoulder: Dict, right_elbow: Dict, right_wrist: Dict) -> bool:
        """Check if person is in punching pose"""
        if not all([left_shoulder, left_elbow, left_wrist, right_shoulder, right_elbow, right_wrist]):
            return False
        
        # Check if arm is extended forward
        left_extended = (
            left_wrist.get("x", 0) > left_elbow.get("x", 0) and
            left_elbow.get("x", 0) > left_shoulder.get("x", 0)
        )
        
        right_extended = (
            right_wrist.get("x", 1) < right_elbow.get("x", 1) and
            right_elbow.get("x", 1) < right_shoulder.get("x", 1)
        )
        
        return left_extended or right_extended
    
    def _is_kicking(self, left_hip: Dict, left_knee: Dict, 
                    right_hip: Dict, right_knee: Dict) -> bool:
        """Check if person is kicking"""
        if not all([left_hip, left_knee, right_hip, right_knee]):
            return False
        
        # Check if leg is raised
        left_leg_raised = left_knee.get("y", 1) < left_hip.get("y", 0) - 0.1
        right_leg_raised = right_knee.get("y", 1) < right_hip.get("y", 0) - 0.1
        
        return left_leg_raised or right_leg_raised
    
    def _is_reaching(self, left_shoulder: Dict, left_wrist: Dict,
                     right_shoulder: Dict, right_wrist: Dict) -> bool:
        """Check if person is reaching forward"""
        if not all([left_shoulder, left_wrist, right_shoulder, right_wrist]):
            return False
        
        # Check if hands are extended forward at shoulder level
        left_reaching = (
            abs(left_wrist.get("y", 0) - left_shoulder.get("y", 0)) < 0.15 and
            left_wrist.get("x", 0) > left_shoulder.get("x", 0) + 0.2
        )
        
        right_reaching = (
            abs(right_wrist.get("y", 0) - right_shoulder.get("y", 0)) < 0.15 and
            right_wrist.get("x", 1) < right_shoulder.get("x", 1) - 0.2
        )
        
        return left_reaching or right_reaching
    
    def _is_crouching(self, left_shoulder: Dict, left_hip: Dict, left_knee: Dict) -> bool:
        """Check if person is crouching"""
        if not all([left_shoulder, left_hip, left_knee]):
            return False
        
        # Check if body is compressed vertically
        torso_height = abs(left_shoulder.get("y", 0) - left_hip.get("y", 1))
        return torso_height < 0.3
    
    def _is_running(self, left_hip: Dict, left_knee: Dict,
                    right_hip: Dict, right_knee: Dict) -> bool:
        """Check if person is running (legs in motion)"""
        if not all([left_hip, left_knee, right_hip, right_knee]):
            return False
        
        # Check if legs are in asymmetric position (one forward, one back)
        left_knee_x = left_knee.get("x", 0)
        right_knee_x = right_knee.get("x", 0)
        
        return abs(left_knee_x - right_knee_x) > 0.15
    
    def _is_fallen(self, left_shoulder: Dict, left_hip: Dict) -> bool:
        """Check if person has fallen down"""
        if not all([left_shoulder, left_hip]):
            return False
        
        # Check if shoulders and hips are at similar height (horizontal body)
        height_diff = abs(left_shoulder.get("y", 0) - left_hip.get("y", 0))
        return height_diff < 0.2 and left_shoulder.get("y", 0) > 0.7
    
    def _calculate_threat_level(self, action: str, landmarks: Dict) -> str:
        """
        Calculate threat level based on detected action
        
        Args:
            action: Detected action string
            landmarks: Pose landmarks
            
        Returns:
            Threat level: "high", "medium", "low"
        """
        high_threat_actions = ["punching", "kicking", "reaching"]
        medium_threat_actions = ["hands_raised", "running", "crouching"]
        low_threat_actions = ["standing", "fallen"]
        
        if action in high_threat_actions:
            return "high"
        elif action in medium_threat_actions:
            return "medium"
        elif action in low_threat_actions:
            return "low"
        else:
            return "unknown"
    
    def analyze_interaction(self, poses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze interactions between multiple detected poses
        
        Args:
            poses: List of detected poses
            
        Returns:
            Dictionary with interaction analysis
        """
        if len(poses) < 2:
            return {
                "interaction_detected": False,
                "interaction_type": "none",
                "risk_level": "low"
            }
        
        # Check proximity between people
        proximity = self._check_proximity(poses)
        
        # Analyze combined actions
        actions = [pose["action"] for pose in poses]
        threat_levels = [pose["threat_level"] for pose in poses]
        
        # Determine interaction type
        if proximity == "close":
            if "punching" in actions or "kicking" in actions:
                interaction_type = "physical_altercation"
                risk_level = "high"
            elif "reaching" in actions:
                interaction_type = "confrontation"
                risk_level = "medium"
            elif "hands_raised" in actions:
                interaction_type = "threatening_behavior"
                risk_level = "medium"
            else:
                interaction_type = "close_interaction"
                risk_level = "low"
        else:
            interaction_type = "distant"
            risk_level = "low"
        
        return {
            "interaction_detected": True,
            "interaction_type": interaction_type,
            "risk_level": risk_level,
            "person_count": len(poses),
            "actions": actions,
            "proximity": proximity
        }
    
    def _check_proximity(self, poses: List[Dict[str, Any]]) -> str:
        """
        Check proximity between detected poses
        
        Args:
            poses: List of detected poses
            
        Returns:
            Proximity level: "close", "medium", "far"
        """
        if len(poses) < 2:
            return "none"
        
        # Calculate distance between first two people
        pose1_center = self._get_pose_center(poses[0]["landmarks"])
        pose2_center = self._get_pose_center(poses[1]["landmarks"])
        
        distance = np.sqrt(
            (pose1_center[0] - pose2_center[0])**2 + 
            (pose1_center[1] - pose2_center[1])**2
        )
        
        if distance < 0.3:
            return "close"
        elif distance < 0.6:
            return "medium"
        else:
            return "far"
    
    def _get_pose_center(self, landmarks: Dict[str, Dict[str, float]]) -> Tuple[float, float]:
        """
        Calculate center point of a pose
        
        Args:
            landmarks: Pose landmarks
            
        Returns:
            (x, y) coordinates of pose center
        """
        # Use torso landmarks for center calculation
        key_points = ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]
        
        x_coords = []
        y_coords = []
        
        for point in key_points:
            if point in landmarks:
                x_coords.append(landmarks[point]["x"])
                y_coords.append(landmarks[point]["y"])
        
        if not x_coords:
            return (0.5, 0.5)
        
        return (np.mean(x_coords), np.mean(y_coords))
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'pose_detector'):
            self.pose_detector.close()
