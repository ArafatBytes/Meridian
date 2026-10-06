// App-wide constants for Meridian

export const APP_NAME = 'Meridian';
export const APP_VERSION = '1.0.0';

// API Configuration
// Use your machine's local IP address for physical device testing
// Run 'ifconfig' (Mac/Linux) or 'ipconfig' (Windows) to find it
// Don't use 'localhost' for Android emulator or physical device
export const API_BASE_URL = 'http://192.168.0.103:8000/api/v1';

// For Android Emulator, use:
// export const API_BASE_URL = 'http://10.0.2.2:8000/api/v1';
// For Production, use:
// export const API_BASE_URL = 'https://api.Meridian.com/api/v1';

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

// Emergency Contacts
export const MAX_EMERGENCY_CONTACTS = 5;
export const MIN_EMERGENCY_CONTACTS = 1;

// Route Configuration
export const ROUTE_PREFERENCES = ['Safest', 'Fastest', 'Balanced'] as const;

export const MAX_ROUTE_ALTERNATIVES = 3;

// Notification Configuration
export const NOTIFICATION_CHANNELS = {
  DANGER_ZONE: 'danger_zone',
  SOS_ALERT: 'sos_alert',
  CRIME_REPORT: 'crime_report',
  SYSTEM: 'system',
};

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
