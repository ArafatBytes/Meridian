import type { CrimeCategory } from './contracts/crime';

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
// Mirrors the `emergency_contacts` table and
// backend/app/models/emergency_contact.py. A second, conflicting declaration
// used to exist in the SOS section below with `relationship` required and an
// `isPrimary` field that exists in no table and is read by no screen.
// TypeScript merges duplicate interfaces rather than erroring, so the live type
// was the union of both with every field required -- which is why
// EmergencyContactCreate never satisfied it. Defect 12.
export interface EmergencyContact {
  id: string;
  user_id: string;
  name: string;
  phone: string;
  email: string;
  /** Nullable in the schema; the app does not currently write it. */
  relationship?: string | null;
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
//
// CrimeCategory is defined in ./contracts/crime and re-exported here so existing
// imports keep working. It used to be a capitalised union declared inline, which
// did not match the lowercase `public.crime_category` enum the database actually
// stores — every CRIME_COLORS lookup in MapScreen missed, and no crime marker on
// the map had a colour. That was defect 3. The values now live in exactly one
// place, with the colour table typed against them so the two cannot drift apart
// again.
// Only the type is re-exported. The value exports (CRIME_CATEGORIES, the colour
// and label tables) are imported from './contracts/crime' directly, because
// `constants/app.constants.ts` already exports a different, longer CRIME_CATEGORIES
// for a UI picker, and two same-named exports reachable through two barrels is how
// the original mismatch became hard to see.
export type { CrimeCategory };

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
  // D09. The articles behind the pins currently on screen — a drill-down from the
  // map, not a section of its own. `CrimeReport` and `ReportDetails` above have
  // been declared since D01 with no screen behind either; see MapNavigator.
  News: undefined;
};

export type ReportsStackParamList = {
  MyReports: undefined;
  AddReport: undefined;
  ReportDetails: { reportId: string };
  // D08. The General Diary lives under Reports because that is where the
  // report it is drafted from lives.
  GdDraft: { reportId: string };
  GdProfile: undefined;
};

export type ProfileStackParamList = {
  ProfileView: undefined;
  EditProfile: undefined;
  EmergencyContacts: undefined;
  SOSHotWords: undefined;
  // D09, beat 9's second half. Declaring a route here is not shipping it -- the
  // three below have been declared and unregistered since D01 -- so this also has
  // a row on the profile menu and a screen in ProfileNavigator.
  SOSHistory: undefined;
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
