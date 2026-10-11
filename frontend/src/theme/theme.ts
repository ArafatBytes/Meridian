import { fontFamily } from './type';

/**
 * The legacy token names, pointed at the new Aurora palette.
 *
 * ## Why this file still exists
 *
 * 26 screens and components do `import { colors } from '../theme'` and read it
 * as a module constant. The real theme is now `palette.ts` behind `useTheme()`,
 * which is what dark mode needs — a hook, so components re-render on a change.
 *
 * Rewriting 26 files at once, with a demo days away, is how you end up with a
 * half-migrated theme and a screen nobody noticed was broken. So instead the
 * *values* here were replaced while every *key* was kept. Consequences:
 *
 * * Every un-migrated screen stopped being purple the moment this file changed,
 *   with no edit of its own. That was the point — one file, whole-app recolour.
 * * Those screens were light-only for as long as they read `colors`, because a
 *   module constant cannot know the mode. They have since been converted to
 *   `useStyles(makeStyles)`, so this object is now kept for its *keys* rather
 *   than its consumers — `LIGHT_ONLY` in `ThemeProvider.tsx` tracks what is
 *   left, and it is empty.
 *
 * **Do not add keys here.** New work uses `useTheme()`. This is the floor under
 * the migration, not a palette to build on.
 *
 * ## The mapping
 *
 * `primary` was indigo `#6366F1`, `secondary` was pink `#EC4899`. They are now
 * the Aurora sky and cyan stops. Two deliberate choices in the translation:
 *
 * * **The grays went cool.** The inherited scale was Tailwind's warm gray
 *   (`#6B7280`), which under a cyan chrome reads as dirty. These are slate, the
 *   same family as the Aurora text tokens, so borders and placeholders sit in
 *   the same colour world as everything else.
 * * **`secondary` became cyan, not coral.** Coral is the Aurora accent, and the
 *   accent is reserved for one action per screen. `secondary` is used as a
 *   decorative fill in five places; pointing it at the accent would have made
 *   the accent decoration and destroyed the thing it is for.
 */
export const colors = {
  // Primary — Aurora sky. The middle gradient stop, used as the solid brand.
  primary: '#0EA5E9',
  primaryLight: '#38BDF8',
  primaryDark: '#0369A1',

  // Secondary — Aurora cyan. Decorative only; see the note above.
  secondary: '#22D3EE',
  secondaryLight: '#67E8F9',

  // Background — a faintly cool ground, not white. Pure white beside a cyan
  // gradient looks like a missing background.
  background: '#F6F9FC',
  backgroundLight: '#FFFFFF',
  backgroundCard: 'rgba(255, 255, 255, 0.9)',

  // Glass
  glass: 'rgba(255, 255, 255, 0.7)',
  glassDark: 'rgba(15, 23, 42, 0.05)',

  // Text — slate, matching the Aurora text ramp.
  text: '#0F172A',
  textSecondary: '#475569',
  textMuted: '#94A3B8',
  textPrimary: '#0F172A', // Alias for compatibility

  // Status colors. Unchanged in meaning, nudged to the palette's versions.
  // These are the only warm colours in the system, which is what lets amber and
  // red mean "something is happening" wherever they appear.
  success: '#059669',
  successLight: '#34D399',
  warning: '#D97706',
  warningLight: '#FBBF24',
  danger: '#DC2626',
  dangerLight: '#F87171',
  error: '#DC2626', // Alias for compatibility
  info: '#0284C7',

  // Surfaces
  surface: 'rgba(255, 255, 255, 0.95)',
  surfaceHover: 'rgba(241, 245, 249, 1)',
  surfaceVariant: 'rgba(241, 245, 249, 1)',

  // Borders — cool, and lighter than the originals. A glass-heavy UI wants its
  // divisions suggested rather than drawn.
  border: 'rgba(15, 23, 42, 0.10)',
  borderLight: 'rgba(15, 23, 42, 0.06)',
  divider: 'rgba(15, 23, 42, 0.08)',

  // Shadow
  shadow: 'rgba(15, 23, 42, 0.10)',
  shadowDark: 'rgba(15, 23, 42, 0.20)',

  white: '#FFFFFF',
  black: '#000000',

  // Gray scale — slate, not Tailwind gray.
  gray50: '#F8FAFC',
  gray100: '#F1F5F9',
  gray200: '#E2E8F0',
  gray300: '#CBD5E1',
  gray400: '#94A3B8',
  gray500: '#64748B',
  gray600: '#475569',
  gray700: '#334155',
  gray800: '#1E293B',
  gray900: '#0F172A',

  // Overlay
  overlay: 'rgba(15, 23, 42, 0.45)',
  overlayLight: 'rgba(15, 23, 42, 0.28)',

  transparent: 'transparent',
};

/**
 * Gradients. `primary` is the Aurora ramp and is what replaced
 * indigo → violet → pink everywhere at once.
 *
 * Three stops that differ in luminance as much as in hue, so the fill reads as
 * light falling across a surface rather than as two colours meeting.
 */
export const gradients = {
  primary: ['#22D3EE', '#0EA5E9', '#2563EB'],
  primaryVertical: ['#0EA5E9', '#2563EB'],
  // The one warm gradient in the app: SOS, and nothing else.
  danger: ['#FB7185', '#E11D48'],
  success: ['#10B981', '#059669'],
  background: ['#F6F9FC', '#FFFFFF'],
  card: ['rgba(255, 255, 255, 0.95)', 'rgba(248, 250, 252, 1)'],
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

/**
 * The legacy typography scale, now carrying the real faces.
 *
 * Styles across the app spread these (`...typography.h4`), so naming the font
 * family here is what puts Sora and Inter on every screen that was never
 * individually converted — the same one-file leverage as the colours above.
 *
 * **`fontWeight` is deliberately absent from every entry.** On Android, React
 * Native resolves a custom family by asset name: given `fontFamily: 'Sora_700Bold'`
 * and `fontWeight: 'bold'` together it looks for a bold *variant* of that asset,
 * finds none, and falls back unpredictably — on the one platform this app is
 * demoed on. The weight lives in the family name, which is why five separate
 * font files are bundled instead of one with four weights.
 *
 * Display sizes (h1–h3) get Sora; everything read in quantity gets Inter. h4 at
 * 20px is the boundary and goes to Inter SemiBold, because at that size Sora
 * starts to look like a label rather than a heading.
 */
export const typography = {
  h1: {
    fontFamily: fontFamily.display,
    fontSize: 32,
    lineHeight: 40,
    letterSpacing: -0.6,
  },
  h2: {
    fontFamily: fontFamily.display,
    fontSize: 28,
    lineHeight: 36,
    letterSpacing: -0.5,
  },
  h3: {
    fontFamily: fontFamily.display,
    fontSize: 24,
    lineHeight: 32,
    letterSpacing: -0.4,
  },
  h4: {
    fontFamily: fontFamily.bodySemi,
    fontSize: 20,
    lineHeight: 28,
    letterSpacing: -0.2,
  },
  body: {
    fontFamily: fontFamily.body,
    fontSize: 16,
    lineHeight: 24,
  },
  bodyLarge: {
    fontFamily: fontFamily.body,
    fontSize: 18,
    lineHeight: 26,
  },
  bodySmall: {
    fontFamily: fontFamily.body,
    fontSize: 14,
    lineHeight: 20,
  },
  caption: {
    fontFamily: fontFamily.body,
    fontSize: 12,
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
