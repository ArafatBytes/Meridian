// User related types
export interface User {
  id: string;
  email: string;
  name: string;
  phone: string | null;
  avatar_url: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  phone: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType?: string;
  expiresIn?: number;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// Emergency Contact types
export interface EmergencyContact {
  id: string;
  user_id: string;
  name: string;
  phone: string;
  email: string;
  created_at: string;
  updated_at: string;
}

export interface EmergencyContactCreate {
  name: string;
  phone: string;
  email: string;
}

// SOS Hot Words types
export interface SOSHotWord {
  id: string;
  user_id: string;
  hot_word: string;
  created_at: string;
}

export interface SOSHotWordCreate {
  hot_word: string;
}

// Location types
export interface Coordinates {
  latitude: number;
  longitude: number;
}

export interface LocationData extends Coordinates {
  accuracy?: number;
  altitude?: number;
  heading?: number;
  speed?: number;
  timestamp?: number;
}

// Crime related types
export type CrimeCategory =
  | 'Theft'
  | 'Robbery'
  | 'Assault'
  | 'Harassment'
  | 'Vandalism'
  | 'Burglary'
  | 'Fraud'
  | 'Other';

export type CrimeSeverity = 'Low' | 'Medium' | 'High' | 'Critical';

export interface CrimeReport {
  id: string;
  userId: string;
  category: CrimeCategory;
  severity: CrimeSeverity;
  description: string;
  location: Coordinates;
  address?: string;
  mediaUrls: string[];
  isVerified: boolean;
  verificationCount: number;
  timestamp: string;
  createdAt: string;
}

export interface CrimeReportCreate {
  category: CrimeCategory;
  severity: CrimeSeverity;
  description: string;
  location: Coordinates;
  mediaFiles?: {
    uri: string;
    type: string;
    name: string;
  }[];
}

export interface NearbyCrime {
  crime: CrimeReport;
  distance: number; // in meters
}

// Route related types
export type RoutePreference = 'Safest' | 'Fastest' | 'Balanced';

export interface RoutePoint {
  latitude: number;
  longitude: number;
}

export interface RouteSegment {
  points: RoutePoint[];
  distance: number; // in meters
  duration: number; // in seconds
  safetyScore: number;
}

export interface Route {
  id: string;
  origin: Coordinates;
  destination: Coordinates;
  segments: RouteSegment[];
  totalDistance: number;
  totalDuration: number;
  averageSafetyScore: number;
  dangerZones: DangerZone[];
  preference: RoutePreference;
}

export interface DangerZone {
  center: Coordinates;
  radius: number;
  crimeScore: number;
  crimeCount: number;
  recentCrimes: CrimeReport[];
}

// SOS related types
export interface EmergencyContact {
  id: string;
  name: string;
  phone: string;
  relationship: string;
  isPrimary: boolean;
}

export interface SOSIncident {
  id: string;
  userId: string;
  location: Coordinates;
  address?: string;
  timestamp: string;
  audioUrl?: string;
  videoUrl?: string;
  status: 'active' | 'resolved' | 'cancelled';
  notifiedContacts: string[];
  responseTime?: number;
}

export interface SOSAlert {
  user: User;
  location: Coordinates;
  address?: string;
  message: string;
  timestamp: string;
  audioUrl?: string;
  videoUrl?: string;
}

// Tracking types
export interface LocationUpdate {
  userId: string;
  location: Coordinates;
  accuracy: number;
  timestamp: string;
  isBackground: boolean;
}

export interface UserTracking {
  userId: string;
  trackingId: string;
  startTime: string;
  endTime?: string;
  locations: LocationUpdate[];
  totalDistance: number;
  averageSpeed: number;
}

// Notification types
export interface NotificationData {
  type: 'danger_zone' | 'sos_alert' | 'crime_report' | 'system';
  title: string;
  body: string;
  data?: Record<string, any>;
}

export interface PushNotification extends NotificationData {
  id: string;
  timestamp: string;
  isRead: boolean;
}

// API Response types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  errors?: Record<string, string[]>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// Error types
export interface ApiError {
  message: string;
  statusCode?: number;
  errors?: Record<string, string[]>;
}

// Navigation types
export type RootStackParamList = {
  Splash: undefined;
  Onboarding: undefined;
  Auth: undefined;
  Main: undefined;
};

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
  VerifyOTP: { email: string };
  ResetPassword: { token: string };
};

export type MainTabParamList = {
  Home: undefined;
  Map: undefined;
  Reports: undefined;
  Profile: undefined;
};

export type HomeStackParamList = {
  Dashboard: undefined;
  RouteSearch: undefined;
  RouteDetails: { routeId: string };
  NearbyCrimes: { location: Coordinates };
  CrimeDetails: { crimeId: string };
};

export type MapStackParamList = {
  MapView: undefined;
  CrimeReport: { location?: Coordinates };
  ReportDetails: { reportId: string };
};

export type ReportsStackParamList = {
  MyReports: undefined;
  AddReport: undefined;
  ReportDetails: { reportId: string };
};

export type ProfileStackParamList = {
  ProfileView: undefined;
  EditProfile: undefined;
  EmergencyContacts: undefined;
  SOSHotWords: undefined;
  Settings: undefined;
  TrackingHistory: undefined;
  About: undefined;
};

// Form types
export interface LoginFormData {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RegisterFormData {
  fullName: string;
  email: string;
  phone: string;
  password: string;
  confirmPassword: string;
  agreeToTerms: boolean;
}

export interface CrimeReportFormData {
  category: CrimeCategory;
  severity: CrimeSeverity;
  description: string;
  location: Coordinates;
  photos: string[];
  video?: string;
  isAnonymous: boolean;
}

export interface EmergencyContactFormData {
  name: string;
  phone: string;
  email: string;
  relationship: string;
  isPrimary: boolean;
}

// Settings types
export interface AppSettings {
  theme: 'light' | 'dark' | 'auto';
  language: string;
  notifications: {
    enabled: boolean;
    dangerZone: boolean;
    sosAlerts: boolean;
    crimeReports: boolean;
  };
  location: {
    backgroundTracking: boolean;
    updateInterval: number;
  };
  privacy: {
    shareLocation: boolean;
    anonymousReporting: boolean;
  };
}
