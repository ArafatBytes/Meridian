# Google Cloud Speech-to-Text Setup Guide

This guide will help you set up Google Cloud Speech-to-Text API for the Meridian backend.

## Prerequisites

- Google Cloud account
- Credit card for billing (free tier available)
- Python 3.11+ installed

## Step-by-Step Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name: `Meridian` (or your preferred name)
4. Click "Create"

### 2. Enable Speech-to-Text API

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Cloud Speech-to-Text API"
3. Click on it and press "Enable"
4. Wait for the API to be enabled (~30 seconds)

### 3. Create Service Account

1. Go to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
3. Enter details:
   - **Name**: `Meridian-speech`
   - **Description**: `Service account for speech-to-text in Meridian`
4. Click "Create and Continue"
5. Grant roles:
   - Select "Cloud Speech Client" role
   - Click "Continue"
6. Click "Done"

### 4. Generate Credentials JSON

1. Find your newly created service account in the list
2. Click on it
3. Go to "Keys" tab
4. Click "Add Key" → "Create new key"
5. Choose "JSON" format
6. Click "Create"
7. **IMPORTANT**: Save the downloaded JSON file securely
8. Rename it to `google-cloud-credentials.json`

### 5. Setup Backend

1. **Place credentials file**:

   ```bash
   # Copy the JSON file to backend directory
   cp /path/to/downloaded-file.json ./google-cloud-credentials.json
   ```

2. **Update .env file**:

   ```bash
   # Copy example env
   cp .env.example .env

   # Edit .env and update these values:
   GOOGLE_CLOUD_PROJECT_ID=your-project-id-here
   GOOGLE_CLOUD_CREDENTIALS_PATH=./google-cloud-credentials.json
   GOOGLE_CLOUD_REGION=us-central1
   SPEECH_RECOGNITION_LANGUAGE=en-US
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Test the setup**:

   ```bash
   # Start the server
   python -m app.main

   # Visit http://localhost:8000/api/docs
   # Look for the "/ai/speech-to-text" endpoint
   ```

### 6. Security Best Practices

⚠️ **IMPORTANT**: Never commit credentials to Git!

Add to `.gitignore`:

```
google-cloud-credentials.json
*.json
!package.json
```

For production:

1. Use Google Cloud Secret Manager
2. Or use environment variables for credentials
3. Set up proper IAM roles
4. Enable audit logging

## Pricing

### Free Tier (Monthly)

- First 60 minutes: **FREE**
- Additional minutes: $0.006 per 15 seconds

### Example Costs

- 100 users × 10 recordings/month × 5 seconds each = 83 minutes
- Cost: First 60 min FREE + 23 min = **$0.55/month**

### Cost Optimization Tips

1. Cache common transcriptions
2. Limit recording duration (max 30 seconds)
3. Use appropriate audio quality (not too high)
4. Monitor usage via Google Cloud Console

## Supported Languages

The API supports 100+ languages including:

- English (en-US, en-GB, en-IN, etc.)
- Bengali (bn-BD, bn-IN)
- Hindi (hi-IN)
- Spanish (es-ES, es-MX)
- French (fr-FR)
- Arabic (ar-SA)
- And many more...

## Testing

### Using cURL:

```bash
curl -X POST "http://localhost:8000/api/v1/ai/speech-to-text" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@test-audio.m4a" \
  -F "language=en-US"
```

### Using the API docs:

1. Go to http://localhost:8000/api/docs
2. Find "AI & Machine Learning" section
3. Try the `/ai/speech-to-text` endpoint
4. Upload an audio file
5. See the transcription result

## Troubleshooting

### Error: "Could not load credentials"

- Check if `google-cloud-credentials.json` exists
- Verify the path in `.env` file
- Ensure the file is valid JSON

### Error: "Permission denied"

- Verify service account has "Cloud Speech Client" role
- Check if Speech-to-Text API is enabled

### Error: "Audio format not supported"

- Supported formats: M4A, MP3, WAV, FLAC, OGG
- Convert audio using pydub if needed
- Check file is not corrupted

### Low accuracy

- Use clear audio with minimal background noise
- Speak clearly and at normal pace
- Use correct language code
- Check microphone quality

## API Endpoints

### POST /api/v1/ai/speech-to-text

Convert speech audio to text

**Request:**

- `audio` (file): Audio file (M4A, MP3, WAV, etc.)
- `language` (string): Language code (default: en-US)

**Response:**

```json
{
  "success": true,
  "data": {
    "text": "Hello, this is a test",
    "confidence": 0.95,
    "language": "en-US",
    "word_count": 5
  },
  "message": "Audio transcribed successfully"
}
```

### GET /api/v1/ai/supported-languages

Get list of supported languages

### GET /api/v1/ai/health

Check AI service health status

## Next Steps

1. Test with real audio recordings
2. Integrate with frontend React Native app
3. Add error handling and retries
4. Monitor usage and costs
5. Optimize audio quality settings

## Support

- [Google Cloud Speech-to-Text Docs](https://cloud.google.com/speech-to-text/docs)
- [Pricing Calculator](https://cloud.google.com/products/calculator)
- [API Reference](https://cloud.google.com/speech-to-text/docs/reference)

---

**Status**: ✅ Backend speech-to-text service is ready!
**Next**: Integrate with React Native frontend
