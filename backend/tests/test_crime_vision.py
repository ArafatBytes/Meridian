"""
Test suite for Crime Vision AI Service
Run: pytest tests/test_crime_vision.py -v
"""
import pytest
import sys
from pathlib import Path
from PIL import Image
import numpy as np
import io

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.ai.crime_vision_service import CrimeVisionService, get_crime_vision_service


@pytest.fixture
def service():
    """Create a CrimeVisionService instance for testing."""
    svc = CrimeVisionService()
    svc.load_models()
    return svc


@pytest.fixture
def dummy_image():
    """Create a dummy test image."""
    # Create a 640x640 RGB image with random pixels
    img_array = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


@pytest.fixture
def image_bytes(dummy_image):
    """Convert image to bytes."""
    img_byte_arr = io.BytesIO()
    dummy_image.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    return img_byte_arr.read()


class TestCrimeVisionService:
    """Test suite for CrimeVisionService."""
    
    def test_service_initialization(self):
        """Test that service initializes correctly."""
        service = CrimeVisionService()
        assert service is not None
        assert service.model_loaded is False
    
    def test_model_loading(self, service):
        """Test that models load successfully."""
        assert service.model_loaded is True
        assert service.model is not None
    
    def test_get_service_singleton(self):
        """Test singleton pattern for service."""
        service1 = get_crime_vision_service()
        service2 = get_crime_vision_service()
        assert service1 is service2
    
    def test_object_detection(self, service, dummy_image):
        """Test object detection on image."""
        detections = service.detect_objects(dummy_image, confidence=0.25)
        assert isinstance(detections, list)
        # Random image may or may not have detections
        for detection in detections:
            assert 'object' in detection
            assert 'confidence' in detection
            assert 'bbox' in detection
    
    def test_crime_classification_no_objects(self, service):
        """Test classification with no detections."""
        crime_type, confidence, details = service.classify_crime([])
        assert crime_type is None
        assert confidence == 0.0
        assert 'reason' in details
    
    def test_crime_classification_with_person(self, service):
        """Test classification with person detected."""
        detections = [
            {'object': 'person', 'confidence': 0.9},
            {'object': 'person', 'confidence': 0.85}
        ]
        crime_type, confidence, details = service.classify_crime(detections)
        # Should detect harassment or assault
        assert crime_type in ['harassment', 'assault'] or crime_type is None
        assert isinstance(confidence, float)
    
    def test_crime_classification_with_weapon(self, service):
        """Test classification with weapon detected."""
        detections = [
            {'object': 'person', 'confidence': 0.9},
            {'object': 'knife', 'confidence': 0.85},
            {'object': 'person', 'confidence': 0.8}
        ]
        crime_type, confidence, details = service.classify_crime(detections)
        # Should detect assault or robbery
        assert crime_type in ['assault', 'robbery']
        assert confidence > 0.5
        assert 'knife' in details['matched_objects']
    
    def test_crime_classification_theft(self, service):
        """Test classification for theft."""
        detections = [
            {'object': 'person', 'confidence': 0.9},
            {'object': 'handbag', 'confidence': 0.85},
            {'object': 'backpack', 'confidence': 0.8}
        ]
        crime_type, confidence, details = service.classify_crime(detections)
        assert crime_type in ['theft', 'robbery', None]
    
    def test_title_generation_assault(self, service):
        """Test title generation for assault."""
        details = {
            'matched_objects': ['person', 'knife'],
            'person_count': 2
        }
        title = service.generate_title('assault', details)
        assert 'assault' in title.lower()
        assert 'knife' in title.lower()
        assert '2' in title
    
    def test_title_generation_theft(self, service):
        """Test title generation for theft."""
        details = {
            'matched_objects': ['person', 'handbag'],
            'person_count': 1
        }
        title = service.generate_title('theft', details)
        assert 'theft' in title.lower()
        assert 'handbag' in title.lower()
    
    def test_description_generation(self, service):
        """Test description generation."""
        details = {
            'all_objects': ['person', 'knife'],
            'person_count': 2,
            'severity': 'high'
        }
        description = service.generate_description('assault', details, 0.85)
        assert 'assault' in description.lower()
        assert 'knife' in description.lower()
        assert 'person' in description.lower()
        assert '85' in description  # Confidence percentage
        assert 'high' in description.lower()
        assert 'AI' in description
    
    @pytest.mark.asyncio
    async def test_analyze_image_integration(self, service, image_bytes):
        """Test full image analysis pipeline."""
        result = await service.analyze_crime_image(
            image_data=image_bytes,
            confidence_threshold=0.25
        )
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'processing_time' in result
        assert 'confidence' in result
        
        # Random image may or may not detect crime
        if result['success']:
            assert 'crime_type' in result
            assert 'title' in result
            assert 'description' in result
            assert 'severity' in result
            assert result['confidence'] >= 0.0
            assert result['processing_time'] > 0
    
    def test_severity_estimation(self, service):
        """Test severity estimation."""
        assert service._estimate_severity('assault', {}) == 'high'
        assert service._estimate_severity('theft', {}) == 'medium'
        assert service._estimate_severity('vandalism', {}) == 'low'
        assert service._estimate_severity('robbery', {}) == 'high'
    
    def test_yolo_to_crime_mapping(self, service):
        """Test YOLO class to crime object mapping."""
        assert service.YOLO_TO_CRIME_MAP['knife'] == 'knife'
        assert service.YOLO_TO_CRIME_MAP['person'] == 'person'
        assert service.YOLO_TO_CRIME_MAP['car'] == 'car'
        assert 'handbag' in service.YOLO_TO_CRIME_MAP
    
    def test_crime_rules_structure(self, service):
        """Test that crime rules are properly structured."""
        for crime_type, rules in service.CRIME_RULES.items():
            assert 'objects' in rules
            assert 'severity' in rules
            assert isinstance(rules['objects'], list)
            assert rules['severity'] in ['low', 'medium', 'high']
            if 'min_persons' in rules:
                assert isinstance(rules['min_persons'], int)
    
    def test_confidence_threshold(self, service, dummy_image):
        """Test different confidence thresholds."""
        detections_low = service.detect_objects(dummy_image, confidence=0.1)
        detections_high = service.detect_objects(dummy_image, confidence=0.7)
        
        # Higher threshold should have fewer or equal detections
        assert len(detections_high) <= len(detections_low)
    
    @pytest.mark.asyncio
    async def test_empty_image_handling(self, service):
        """Test handling of empty/corrupted image."""
        with pytest.raises(Exception):
            await service.analyze_crime_image(
                image_data=b'',
                confidence_threshold=0.25
            )
    
    def test_confidence_score_range(self, service):
        """Test that confidence scores are in valid range."""
        detections = [
            {'object': 'person', 'confidence': 0.9},
            {'object': 'knife', 'confidence': 0.85}
        ]
        crime_type, confidence, details = service.classify_crime(detections)
        
        if crime_type is not None:
            assert 0.0 <= confidence <= 1.0


class TestCrimeRules:
    """Test crime classification rules."""
    
    def test_assault_rules(self):
        """Test assault detection rules."""
        service = CrimeVisionService()
        rules = service.CRIME_RULES['assault']
        
        assert 'knife' in rules['objects'] or 'gun' in rules['objects']
        assert rules['severity'] == 'high'
        assert rules['min_persons'] >= 1
    
    def test_theft_rules(self):
        """Test theft detection rules."""
        service = CrimeVisionService()
        rules = service.CRIME_RULES['theft']
        
        assert 'person' in rules['objects']
        assert rules['severity'] in ['medium', 'low']
    
    def test_all_crimes_have_severity(self):
        """Test that all crimes have severity defined."""
        service = CrimeVisionService()
        
        for crime_type, rules in service.CRIME_RULES.items():
            assert 'severity' in rules
            assert rules['severity'] in ['low', 'medium', 'high']


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
