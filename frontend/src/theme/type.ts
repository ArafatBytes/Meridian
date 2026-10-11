/**
 * Typography. Two families, one scale.
 *
 * ## The pairing, and why two families rather than one
 *
 * **Sora** for anything that is a *statement* — screen titles, numbers you read
 * at a glance, the countdown. It is geometric with slightly flared terminals, so
 * at large sizes it looks engineered rather than generic, and it has a real
 * ExtraBold that holds up on a gradient.
 *
 * **Inter** for everything that is *read* — body copy, labels, list rows, the
 * mobility statements. It was drawn for screens at small sizes: tall x-height,
 * open apertures, and digits that do not wobble.
 *
 * One family for both jobs forces a compromise. A geometric display face set at
 * 13px for a list row reads cold and gets cramped; a UI face set at 34px for a
 * title reads like a settings screen. Using each where it is strong is most of
 * what "premium" means in a typeface — the rest is restraint about weights.
 *
 * ## Only four weights ship
 *
 * Inter 400/500/600 and Sora 600/700. Every extra weight is a font file in the
 * bundle and one more decision per label. If something needs emphasis and 600 is
 * not enough, the answer is size or colour, not 800.
 *
 * ## Numbers are tabular wherever they change
 *
 * A countdown or a live meter that shifts sideways as digits change looks
 * broken. `tabular` is on the styles used for those.
 */

import { Platform, type TextStyle } from 'react-native';

/** PostScript-ish names registered with `useFonts`. Must match `fonts.ts`. */
export const fontFamily = {
  display: 'Sora_700Bold',
  displaySemi: 'Sora_600SemiBold',
  body: 'Inter_400Regular',
  bodyMedium: 'Inter_500Medium',
  bodySemi: 'Inter_600SemiBold',
} as const;

/**
 * Tabular figures, so changing digits do not shift the layout.
 *
 * `fontVariant` is honoured on iOS; on Android it depends on the font exposing
 * the `tnum` feature, which Inter does. Harmless where unsupported.
 */
const tabular: TextStyle = { fontVariant: ['tabular-nums'] };

/**
 * The scale. Deliberately short — eight steps, no in-between sizes.
 *
 * Letter-spacing tightens as size grows, which is what keeps large text from
 * looking like it was scaled up rather than designed: display faces need
 * negative tracking at headline sizes and none at caption sizes.
 */
export const type = {
  /** One per screen, at the top. Nothing else is this big. */
  hero: {
    fontFamily: fontFamily.display,
    fontSize: 34,
    lineHeight: 40,
    letterSpacing: -0.8,
  } as TextStyle,

  /** Section heads inside a screen. */
  title: {
    fontFamily: fontFamily.display,
    fontSize: 24,
    lineHeight: 30,
    letterSpacing: -0.5,
  } as TextStyle,

  /** Card headings, nav titles. */
  heading: {
    fontFamily: fontFamily.displaySemi,
    fontSize: 18,
    lineHeight: 24,
    letterSpacing: -0.2,
  } as TextStyle,

  /** Default body. The mobility statements are set in this. */
  body: {
    fontFamily: fontFamily.body,
    fontSize: 15,
    lineHeight: 22,
  } as TextStyle,

  bodyStrong: {
    fontFamily: fontFamily.bodySemi,
    fontSize: 15,
    lineHeight: 22,
  } as TextStyle,

  /** Secondary copy, row subtitles, help text. */
  small: {
    fontFamily: fontFamily.body,
    fontSize: 13,
    lineHeight: 19,
  } as TextStyle,

  /** Buttons and tab labels. */
  label: {
    fontFamily: fontFamily.bodySemi,
    fontSize: 13,
    lineHeight: 16,
    letterSpacing: 0.1,
  } as TextStyle,

  /** Metadata, timestamps, the smallest readable size. */
  caption: {
    fontFamily: fontFamily.bodyMedium,
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 0.2,
  } as TextStyle,

  /** Over-line labels above a section. Uppercase is applied by the component. */
  overline: {
    fontFamily: fontFamily.bodySemi,
    fontSize: 10,
    lineHeight: 14,
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  } as TextStyle,

  // ---- Numeric ---------------------------------------------------------

  /** Big live numbers: the countdown, a safety score. */
  metric: {
    fontFamily: fontFamily.display,
    fontSize: 44,
    lineHeight: 48,
    letterSpacing: -1.2,
    ...tabular,
  } as TextStyle,

  /** Inline numbers that update — meters, counters. */
  metricSmall: {
    fontFamily: fontFamily.displaySemi,
    fontSize: 16,
    lineHeight: 20,
    ...tabular,
  } as TextStyle,
} as const;

export type TypeToken = keyof typeof type;

/**
 * Nudge for a label sitting on the Aurora gradient.
 *
 * Light text on a mid-tone gradient loses its edges, and the usual fix — going
 * bolder — makes the type heavy. A very soft shadow restores the edge without
 * being visible as a shadow. Android renders `textShadow*` on `Text` reliably;
 * iOS needs the radius to be non-zero or it is ignored.
 */
export const onGradient: TextStyle = {
  textShadowColor: 'rgba(2, 10, 24, 0.28)',
  textShadowOffset: { width: 0, height: 1 },
  textShadowRadius: Platform.OS === 'ios' ? 3 : 2,
};

/** Spacing, on a 4px grid. */
export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  huge: 48,
} as const;

/**
 * Corner radii.
 *
 * `card` is 20 rather than the more common 12: a glass panel needs a larger
 * radius before it reads as a pane of material instead of a box with a
 * translucent fill. `pill` is deliberately huge so it always fully rounds.
 */
export const radius = {
  sm: 10,
  md: 14,
  card: 20,
  sheet: 28,
  pill: 999,
} as const;
