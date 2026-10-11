// App-wide constants for Meridian

export const APP_NAME = 'Meridian';
export const APP_VERSION = '1.0.0';

// API Configuration
//
// Set EXPO_PUBLIC_API_BASE_URL in frontend/.env. `scripts/run.ps1` and
// `scripts/run.sh` detect your LAN IP and set it automatically, which is the
// point: this used to be a hardcoded 192.168.0.103 that was only ever correct
// on one machine, so the app silently could not reach the backend on any other.
//
// Never 'localhost' for a physical device or an Android emulator — that
// resolves to the device itself, not your machine.
//   Physical device  → http://<your-LAN-IP>:8000/api/v1
//   Android emulator → http://10.0.2.2:8000/api/v1
//   iOS simulator    → http://localhost:8000/api/v1
//   Production       → https://api.meridian.app/api/v1
//
// The fallback keeps the historical value so an unset env var behaves as before
// rather than failing in a new way.
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://192.168.0.103:8000/api/v1';

export const API_TIMEOUT = 30000; // 30 seconds

// Location Configuration
export const LOCATION_UPDATE_INTERVAL = 60000; // 60 seconds
export const LOCATION_FASTEST_INTERVAL = 30000; // 30 seconds
export const LOCATION_DISTANCE_FILTER = 10; // meters
export const BACKGROUND_LOCATION_INTERVAL = 300000; // 5 minutes

// Map Configuration
export const DEFAULT_MAP_REGION = {
  latitude: 23.8103,
  longitude: 90.4125,
  latitudeDelta: 0.0922,
  longitudeDelta: 0.0421,
};

export const DHAKA_COORDINATES = {
  latitude: 23.8103,
  longitude: 90.4125,
};

// Crime Configuration
export const CRIME_CATEGORIES = [
  'Theft',
  'Robbery',
  'Assault',
  'Harassment',
  'Kidnapping',
  'Murder',
  'Rape',
  'Drug Related',
  'Vandalism',
  'Burglary',
  'Other',
] as const;

export const CRIME_SEVERITY = ['Low', 'Medium', 'High', 'Critical'] as const;

export const DANGER_ZONE_THRESHOLD = 7.0; // Crime score threshold
export const NEARBY_CRIMES_RADIUS = 1000; // meters

// SOS Configuration
export const SOS_ACTIVATION_PHRASE = 'Meridian Emergency';
export const SOS_COUNTDOWN_SECONDS = 5;
export const SOS_AUTO_CALL_DELAY = 10000; // 10 seconds

// SOS evidence video.
//
// These exist because of a measurement, not a guess. A 10-second clip recorded at
// an iPhone's default quality came out at 16.45 MB; base64-encoded as an email
// attachment that is ~22 MB, just under Gmail's 25 MB limit, and it took 2 minutes
// 34 seconds to send. An emergency alert that takes two and a half minutes to
// leave the building is not an emergency alert.
//
// At 1.2 Mbps a 10-second clip is about 1.5 MB plus audio, which sends in seconds
// and is still perfectly legible as evidence of what was happening.
export const SOS_VIDEO_DURATION_SECONDS = 10;

/** Target bitrate in bits per second. iOS additionally needs the codec set on recordAsync. */
export const SOS_VIDEO_BITRATE = 1_200_000;

/**
 * Hard ceiling on the recording, in bytes. Recording stops here.
 *
 * A backstop, not the mechanism: at the bitrate above a 10-second clip is nowhere
 * near this. It matters if bitrate control is ignored on some device, where it
 * turns "16 MB and a two-minute send" into "a shorter clip that actually sends".
 * Partial evidence that arrives beats complete evidence that does not.
 *
 * Well under the backend's own 25 MB limit (SOS_VIDEO_MAX_SIZE_MB).
 */
export const SOS_VIDEO_MAX_BYTES = 8 * 1024 * 1024; // 8MB

// Emergency Contacts
export const MAX_EMERGENCY_CONTACTS = 5;
export const MIN_EMERGENCY_CONTACTS = 1;

// Route Configuration
export const ROUTE_PREFERENCES = ['Safest', 'Fastest', 'Balanced'] as const;

export const MAX_ROUTE_ALTERNATIVES = 3;

// Notification Configuration
// Android notification channel ids used to live here as NOTIFICATION_CHANNELS.
// B6a moved them to `src/features/alerts/channels.ts`, which is now the single
// source of truth -- `backend/tests/invariants/test_alert_channels_match_the_client.py`
// reads that file and asserts the backend never sends a channelId the app did not
// create, because a mismatch is silent on both sides and costs the notification
// its importance and its sound.
//
// Not re-exported from here: this module is plain constants with no native
// imports, and `channels.ts` pulls in `expo-notifications` and `react-native`.
// Re-exporting would make every importer of app.constants.ts depend on the
// native notification module, which is exactly the coupling `app.constants.test.ts`
// runs without.
//
// Two of the four original ids are gone rather than moved. `danger_zone` is the
// framing the product abandoned -- a channel name is a user-visible string in
// Android's settings list, so "Danger Zone Alerts" would have put the one word
// concept document §9 forbids into the OS settings screen, where nothing in
// framing.py can reach it. `crime_report` never had a sender.

// Storage Keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'auth_token',
  REFRESH_TOKEN: 'refresh_token',
  USER_DATA: 'user_data',
  EMERGENCY_CONTACTS: 'emergency_contacts',
  ROUTE_PREFERENCE: 'route_preference',
  THEME: 'theme',
  LANGUAGE: 'language',
  ONBOARDING_COMPLETE: 'onboarding_complete',
  FCM_TOKEN: 'fcm_token',
};

// Camera Configuration
export const MAX_VIDEO_DURATION = 60; // seconds
export const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5MB
export const IMAGE_QUALITY = 0.8;

// Voice Recognition
export const VOICE_RECOGNITION_TIMEOUT = 10000; // 10 seconds
export const VOICE_RECOGNITION_LANGUAGE = 'en-US';

// Permissions
export const REQUIRED_PERMISSIONS = {
  LOCATION: 'Location',
  CAMERA: 'Camera',
  MICROPHONE: 'Microphone',
  NOTIFICATIONS: 'Notifications',
  CONTACTS: 'Contacts',
} as const;

// Time Constants
export const REFRESH_TOKEN_THRESHOLD = 300000; // 5 minutes before expiry
export const SESSION_TIMEOUT = 3600000; // 1 hour

// Validation
export const PASSWORD_MIN_LENGTH = 8;
export const PHONE_NUMBER_LENGTH = 11; // Bangladesh
export const OTP_LENGTH = 6;

// Pagination
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

// Error Messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network connection error. Please check your internet.',
  SERVER_ERROR: 'Server error. Please try again later.',
  UNAUTHORIZED: 'Session expired. Please login again.',
  LOCATION_PERMISSION: 'Location permission is required for this feature.',
  CAMERA_PERMISSION: 'Camera permission is required to take photos.',
  MICROPHONE_PERMISSION:
    'Microphone permission is required for voice commands.',
  INVALID_CREDENTIALS: 'Invalid email or password.',
  WEAK_PASSWORD:
    'Password must be at least 8 characters with letters and numbers.',
};

// Success Messages
export const SUCCESS_MESSAGES = {
  LOGIN_SUCCESS: 'Login successful',
  LOGOUT_SUCCESS: 'Logout successful',
  CRIME_REPORTED: 'Crime report submitted successfully',
  SOS_ACTIVATED: 'SOS alert sent to emergency contacts',
  PROFILE_UPDATED: 'Profile updated successfully',
  CONTACT_ADDED: 'Emergency contact added',
  CONTACT_REMOVED: 'Emergency contact removed',
};

// Colors (for use in theme)
export const COLORS = {
  PRIMARY: '#1E88E5',
  SECONDARY: '#26A69A',
  DANGER: '#E53935',
  WARNING: '#FFA726',
  SUCCESS: '#66BB6A',
  INFO: '#42A5F5',
  BACKGROUND: '#FFFFFF',
  SURFACE: '#F5F5F5',
  TEXT_PRIMARY: '#212121',
  TEXT_SECONDARY: '#757575',
  BORDER: '#E0E0E0',
};

// Animation Durations
export const ANIMATION_DURATION = {
  SHORT: 200,
  MEDIUM: 300,
  LONG: 500,
};
