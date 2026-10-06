# Migration to expo-video for SOS Feature

## Issue
`expo-av` is deprecated and will be removed in SDK 54. We need to migrate to `expo-video` for video recording.

## Installation

```bash
npx expo install expo-video expo-camera
```

## Implementation Guide

### 1. Remove expo-av dependency (if not used elsewhere)
```bash
npm uninstall expo-av
```

### 2. Update SOS Screen to use expo-camera for video recording

```tsx
import { Camera, CameraView } from 'expo-camera';
import * as FileSystem from 'expo-file-system';

// Request permissions
const { status } = await Camera.requestCameraPermissionsAsync();
const { status: audioStatus } = await Camera.requestMicrophonePermissionsAsync();

// Start recording
const video = await cameraRef.current?.recordAsync({
  maxDuration: 30, // 30 seconds max
  quality: '720p', // Lower quality to keep under 25MB
});

// Get file size
const fileInfo = await FileSystem.getInfoAsync(video.uri);
const fileSizeMB = fileInfo.size / (1024 * 1024);

if (fileSizeMB > 25) {
  // Compress or reject
  Alert.alert('Video too large', 'Please record a shorter video');
  return;
}

// Upload to backend
const formData = new FormData();
formData.append('latitude', location.latitude);
formData.append('longitude', location.longitude);
formData.append('video', {
  uri: video.uri,
  type: 'video/mp4',
  name: 'sos_video.mp4',
});

await fetch(`${API_URL}/sos/trigger`, {
  method: 'POST',
  body: formData,
  headers: {
    'Authorization': `Bearer ${token}`,
  },
});
```

### 3. Video Compression Tips

To keep video under 25MB:
- Use 720p quality (not 1080p)
- Limit duration to 30 seconds
- Use H.264 codec
- Consider using `expo-video-thumbnails` for preview

### 4. Alternative: Use expo-media-library

For selecting existing videos:
```tsx
import * as ImagePicker from 'expo-image-picker';

const result = await ImagePicker.launchCameraAsync({
  mediaTypes: ImagePicker.MediaTypeOptions.Videos,
  quality: 0.5, // Compress to 50%
  videoMaxDuration: 30,
});
```

## Testing Checklist

- [ ] Video recording works
- [ ] Video size is under 25MB
- [ ] Video uploads successfully
- [ ] Email is received with video attachment
- [ ] Video plays in email client

## Notes

- The backend already handles video size validation (25MB max)
- Email providers typically support up to 25MB attachments
- Consider adding a progress indicator during upload
- Add error handling for network failures
