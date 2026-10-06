# Voice-Activated SOS Feature

## Overview
The app now supports automatic SOS triggering when users scream specific "hot words" like "help", "bachao", "save me", or "police".

## How It Works

### 1. Database Schema
- Added `hot_words` column to `users` table
- Stores JSON array of trigger words per user
- Default words: ["help", "bachao", "save me", "police"]

### 2. Backend Processing
- **Endpoint**: `POST /api/v1/voice/analyze`
- Receives audio recordings from frontend
- Uses Google Speech-to-Text API (when configured)
- Checks transcript against user's hot words
- Returns `trigger: true` if match found

### 3. Frontend Monitoring
- Continuously records 3-second audio samples every 5 seconds
- Sends samples to backend for analysis
- Automatically triggers SOS if hot word detected
- Runs in background while app is active

### 4. Multi-Trigger System
The app now has THREE ways to trigger SOS:
1. **Manual**: Press the SOS button
2. **Motion**: Violent shake (>6.0g acceleration)
3. **Voice**: Scream hot words

## Configuration

### Customizing Hot Words
Users can customize their hot words by updating the database:
```sql
UPDATE users 
SET hot_words = '["custom", "word", "list"]'::json 
WHERE id = 'user_id';
```

### Google Speech API Setup (Optional)
To enable actual speech recognition:
1. Set up Google Cloud Speech-to-Text
2. Add credentials to backend
3. Uncomment speech recognition code in `voice.py`

## Current Implementation
- Voice monitoring: ✅ Active
- Audio recording: ✅ Working
- Backend endpoint: ✅ Created
- Hot word detection: ⚠️ Placeholder (needs Google Speech API)

## Next Steps
For production deployment, configure Google Cloud Speech-to-Text API credentials to enable actual word recognition.
