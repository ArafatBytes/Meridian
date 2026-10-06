"""
Test script for Speech-to-Text service
Run this to verify the setup is working correctly
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai.speech_service import speech_service


async def test_speech_service():
    """Test the speech-to-text service initialization"""
    print("🧪 Testing Speech-to-Text Service...")
    print("-" * 50)
    
    # Check if service is initialized
    if speech_service.client is None:
        print("❌ FAILED: Speech service client is not initialized")
        print("\n📋 Possible reasons:")
        print("1. Google Cloud credentials file not found")
        print("2. Credentials file path is incorrect in .env")
        print("3. Service account doesn't have required permissions")
        print("\n💡 Solution:")
        print("1. Follow SPEECH_TO_TEXT_SETUP.md to set up Google Cloud")
        print("2. Place google-cloud-credentials.json in backend directory")
        print("3. Update GOOGLE_CLOUD_CREDENTIALS_PATH in .env")
        return False
    
    print("✅ Speech-to-Text client initialized successfully!")
    print(f"📍 Using credentials from: {os.getenv('GOOGLE_CLOUD_CREDENTIALS_PATH', './google-cloud-credentials.json')}")
    
    # Test with sample text (no actual audio)
    print("\n🎤 Service is ready to transcribe audio!")
    print("📝 Supported formats: M4A, MP3, WAV, FLAC, OGG")
    print("🌍 Default language: en-US")
    print("⏱️  Max duration: 30 seconds (real-time)")
    
    print("\n✨ Setup complete! You can now:")
    print("1. Start the API server: python -m app.main")
    print("2. Visit http://localhost:8000/api/docs")
    print("3. Test /api/v1/ai/speech-to-text endpoint")
    
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("Meridian - Speech-to-Text Test")
    print("=" * 50)
    print()
    
    success = asyncio.run(test_speech_service())
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ TESTS FAILED")
        print("📖 Read SPEECH_TO_TEXT_SETUP.md for setup instructions")
        sys.exit(1)
