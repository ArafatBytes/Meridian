"""
Download and setup AI models for crime detection.
Run this once during initial setup.
"""
import os
import sys
from pathlib import Path
from ultralytics import YOLO

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def download_models():
    """Download YOLOv9 and other required models."""
    
    # Create models directory
    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🚀 Downloading AI Models for Crime Detection")
    print("=" * 60)
    
    # Download YOLOv9
    print("\n📦 Step 1/2: Downloading YOLOv9 model...")
    print("   Size: ~12 MB")
    print("   This may take 2-5 minutes depending on your connection...")
    
    try:
        # This will automatically download the model
        model = YOLO('yolov9c.pt')  # YOLOv9 compact model
        
        # Verify model works
        print("✅ YOLOv9 model downloaded successfully!")
        print(f"   Location: {model.ckpt_path}")
        
        # Test inference on dummy image
        print("\n🧪 Step 2/2: Testing model...")
        import numpy as np
        from PIL import Image
        
        # Create a dummy test image
        dummy_image = Image.fromarray(np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8))
        results = model(dummy_image, verbose=False)
        
        print("✅ Model test passed!")
        print(f"   Model can detect {len(model.names)} classes")
        
        print("\n" + "=" * 60)
        print("✅ Setup Complete!")
        print("=" * 60)
        print("\n📋 Next Steps:")
        print("   1. Start the backend server: uvicorn app.main:app --reload")
        print("   2. Test the API: POST /crime-ai/analyze-image")
        print("   3. Check model status: GET /crime-ai/models/status")
        print("\n💡 Tip: The model is cached and won't be re-downloaded.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error downloading models: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check your internet connection")
        print("   2. Ensure you have ~500MB free disk space")
        print("   3. Try running: pip install ultralytics --upgrade")
        print("   4. Check firewall settings")
        return False

if __name__ == "__main__":
    success = download_models()
    sys.exit(0 if success else 1)
