// Light Mode Theme with Snow Background
export const colors = {
  // Primary - Modern Blue/Purple gradient
  primary: '#6366F1', // Indigo
  primaryLight: '#818CF8',
  primaryDark: '#4F46E5',

  // Secondary - Accent colors
  secondary: '#EC4899', // Pink
  secondaryLight: '#F472B6',

  // Background - Snow theme
  background: '#FFFAFA', // Snow white
  backgroundLight: '#FFFFFF',
  backgroundCard: 'rgba(255, 255, 255, 0.9)', // Semi-transparent white

  // Glass effect - Light mode
  glass: 'rgba(255, 255, 255, 0.7)',
  glassDark: 'rgba(0, 0, 0, 0.05)',

  // Text - Dark text for light background
  text: '#1F2937',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',
  textPrimary: '#1F2937', // Alias for compatibility

  // Status colors
  success: '#10B981',
  successLight: '#34D399',
  warning: '#F59E0B',
  warningLight: '#FBBF24',
  danger: '#EF4444',
  dangerLight: '#F87171',
  error: '#EF4444', // Alias for compatibility
  info: '#3B82F6',

  // Surface colors - Light surfaces
  surface: 'rgba(255, 255, 255, 0.95)',
  surfaceHover: 'rgba(249, 250, 251, 1)',
  surfaceVariant: 'rgba(243, 244, 246, 1)',

  // Border - Subtle borders for light mode
  border: 'rgba(229, 231, 235, 1)',
  borderLight: 'rgba(243, 244, 246, 1)',
  divider: 'rgba(229, 231, 235, 0.5)',

  // Shadow
  shadow: 'rgba(0, 0, 0, 0.1)',
  shadowDark: 'rgba(0, 0, 0, 0.2)',

  // White/Black
  white: '#FFFFFF',
  black: '#000000',

  // Gray scale
  gray50: '#F9FAFB',
  gray100: '#F3F4F6',
  gray200: '#E5E7EB',
  gray300: '#D1D5DB',
  gray400: '#9CA3AF',
  gray500: '#6B7280',
  gray600: '#4B5563',
  gray700: '#374151',
  gray800: '#1F2937',
  gray900: '#111827',

  // Overlay
  overlay: 'rgba(0, 0, 0, 0.5)',
  overlayLight: 'rgba(0, 0, 0, 0.3)',

  // Transparent
  transparent: 'transparent',
};

// Gradient definitions - Light mode gradients
export const gradients = {
  primary: ['#6366F1', '#8B5CF6', '#EC4899'],
  primaryVertical: ['#6366F1', '#4F46E5'],
  danger: ['#EF4444', '#DC2626'],
  success: ['#10B981', '#059669'],
  background: ['#FFFAFA', '#FFFFFF'], // Snow gradient
  card: ['rgba(255, 255, 255, 0.95)', 'rgba(249, 250, 251, 1)'],
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const borderRadius = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const fontSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const fontWeight = {
  light: '300' as const,
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
  bold: '700' as const,
};

// Typography system
export const typography = {
  h1: {
    fontSize: 32,
    fontWeight: '700' as const,
    lineHeight: 40,
  },
  h2: {
    fontSize: 28,
    fontWeight: '700' as const,
    lineHeight: 36,
  },
  h3: {
    fontSize: 24,
    fontWeight: '600' as const,
    lineHeight: 32,
  },
  h4: {
    fontSize: 20,
    fontWeight: '600' as const,
    lineHeight: 28,
  },
  body: {
    fontSize: 16,
    fontWeight: '400' as const,
    lineHeight: 24,
  },
  bodyLarge: {
    fontSize: 18,
    fontWeight: '400' as const,
    lineHeight: 26,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: '400' as const,
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    fontWeight: '400' as const,
    lineHeight: 16,
  },
};

export const shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 8,
  },
  xl: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.25,
    shadowRadius: 24,
    elevation: 12,
  },
  // Aliases for compatibility
  small: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  medium: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  large: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 8,
  },
};

// Glass effect style - Light mode
export const glassEffect = {
  backgroundColor: 'rgba(255, 255, 255, 0.7)',
  borderWidth: 1,
  borderColor: 'rgba(229, 231, 235, 0.8)',
};

export const theme = {
  colors,
  gradients,
  spacing,
  borderRadius,
  fontSize,
  fontWeight,
  typography,
  shadows,
  glassEffect,
};

export type Theme = typeof theme;

export default theme;
