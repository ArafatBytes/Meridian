"""
Speech-to-Text Service using Google Cloud Speech-to-Text API
"""
import os
import io
import logging
from typing import Optional, Dict, Any
from google.cloud import speech_v1
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError
# from pydub import AudioSegment

from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """
    Service for converting speech audio to text using Google Cloud Speech-to-Text API
    """

    def __init__(self):
        """Initialize the Speech-to-Text service with Google Cloud credentials"""
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Google Cloud Speech client with credentials"""
        try:
            # Check if credentials file exists
            if os.path.exists(settings.GOOGLE_CLOUD_CREDENTIALS_PATH):
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CLOUD_CREDENTIALS_PATH
                )
                self.client = speech_v1.SpeechClient(credentials=credentials)
                logger.info("✅ Google Cloud Speech-to-Text client initialized successfully")
            else:
                # Try to use default credentials (for cloud environments)
                self.client = speech_v1.SpeechClient()
                logger.info("✅ Google Cloud Speech-to-Text client initialized with default credentials")
        except Exception as e:
            logger.warning(f"⚠️  Speech-to-Text client not available: {str(e)}")
            logger.info("ℹ️  Speech-to-Text features will be disabled until credentials are configured")
            self.client = None

    def _convert_audio_format(
        self, 
        audio_content: bytes, 
        input_format: str = "m4a"
    ) -> bytes:
        """
        Convert audio to the format required by Google Cloud Speech-to-Text
        
        Args:
            audio_content: Raw audio bytes
            input_format: Input audio format (m4a, mp3, wav, etc.)
            
        Returns:
            Converted audio bytes in LINEAR16 format
        """
        try:
            # Load audio using pydub
            audio = AudioSegment.from_file(
                io.BytesIO(audio_content), 
                format=input_format
            )
            
            # Convert to required format
            # - Set sample rate to 16000 Hz
            # - Convert to mono
            # - Export as WAV (LINEAR16)
            audio = audio.set_frame_rate(settings.SPEECH_SAMPLE_RATE)
            audio = audio.set_channels(1)
            
            # Export to bytes
            output = io.BytesIO()
            audio.export(output, format="wav")
            output.seek(0)
            
            return output.read()
        except Exception as e:
            logger.error(f"Audio conversion failed: {str(e)}")
            raise ValueError(f"Failed to convert audio format: {str(e)}")

    async def transcribe_audio(
        self,
        audio_content: bytes,
        language_code: str = None,
        audio_format: str = "m4a",
        enable_automatic_punctuation: bool = True,
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text using Google Cloud Speech-to-Text
        
        Args:
            audio_content: Audio file content as bytes
            language_code: Language code (e.g., 'en-US', 'bn-BD')
            audio_format: Format of input audio (m4a, mp3, wav, etc.)
            enable_automatic_punctuation: Whether to add punctuation
            
        Returns:
            Dictionary containing:
                - text: Transcribed text
                - confidence: Confidence score (0-1)
                - language: Detected language
                
        Raises:
            ValueError: If client is not initialized or audio is invalid
            GoogleAPIError: If API request fails
        """
        if not self.client:
            raise ValueError(
                "Speech-to-Text client is not initialized. "
                "Please configure Google Cloud credentials."
            )

        try:
            # Use default language if not specified
            if language_code is None:
                language_code = settings.SPEECH_RECOGNITION_LANGUAGE

            # Convert audio to required format
            logger.info(f"Converting audio from {audio_format} to WAV...")
            converted_audio = self._convert_audio_format(audio_content, audio_format)

            # Create audio object
            audio = speech_v1.RecognitionAudio(content=converted_audio)

            # Configure recognition settings
            config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=settings.SPEECH_SAMPLE_RATE,
                language_code=language_code,
                enable_automatic_punctuation=enable_automatic_punctuation,
                model="default",  # Use 'default' for general speech
                use_enhanced=True,  # Use enhanced model for better accuracy
            )

            # Perform recognition
            logger.info(f"Transcribing audio with language: {language_code}")
            response = self.client.recognize(config=config, audio=audio)

            # Process results
            if not response.results:
                logger.warning("No speech detected in audio")
                return {
                    "text": "",
                    "confidence": 0.0,
                    "language": language_code,
                    "message": "No speech detected in audio"
                }

            # Get the best transcript
            transcripts = []
            confidences = []
            
            for result in response.results:
                alternative = result.alternatives[0]
                transcripts.append(alternative.transcript)
                confidences.append(alternative.confidence)

            # Combine all transcripts
            final_text = " ".join(transcripts)
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            logger.info(f"✅ Transcription successful: '{final_text[:50]}...' (confidence: {average_confidence:.2f})")

            return {
                "text": final_text,
                "confidence": average_confidence,
                "language": language_code,
                "word_count": len(final_text.split())
            }

        except GoogleAPIError as e:
            logger.error(f"Google Cloud API error: {str(e)}")
            raise ValueError(f"Speech-to-Text API error: {str(e)}")
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise ValueError(f"Failed to transcribe audio: {str(e)}")

    async def transcribe_long_audio(
        self,
        audio_uri: str,
        language_code: str = None,
    ) -> Dict[str, Any]:
        """
        Transcribe long audio files (>60 seconds) using asynchronous recognition
        Audio must be stored in Google Cloud Storage
        
        Args:
            audio_uri: GCS URI (gs://bucket/path/to/audio.wav)
            language_code: Language code
            
        Returns:
            Transcription results
        """
        if not self.client:
            raise ValueError("Speech-to-Text client is not initialized")

        try:
            if language_code is None:
                language_code = settings.SPEECH_RECOGNITION_LANGUAGE

            audio = speech_v1.RecognitionAudio(uri=audio_uri)
            config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=settings.SPEECH_SAMPLE_RATE,
                language_code=language_code,
                enable_automatic_punctuation=True,
            )

            # Asynchronous recognition for long audio
            operation = self.client.long_running_recognize(config=config, audio=audio)
            logger.info(f"Long audio transcription started. Waiting for completion...")

            response = operation.result(timeout=300)  # 5 minute timeout

            # Process results
            transcripts = []
            for result in response.results:
                transcripts.append(result.alternatives[0].transcript)

            final_text = " ".join(transcripts)

            return {
                "text": final_text,
                "language": language_code,
                "word_count": len(final_text.split())
            }

        except Exception as e:
            logger.error(f"Long audio transcription failed: {str(e)}")
            raise ValueError(f"Failed to transcribe long audio: {str(e)}")


# Create singleton instance
speech_service = SpeechToTextService()
