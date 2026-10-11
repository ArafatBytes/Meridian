/**
 * The theme, switchable at runtime, without rewriting thirty files on day one.
 *
 * ## Two APIs, one palette — and why both still exist
 *
 * `useTheme()` is the real API. Every screen now uses it, directly or through
 * `useStyles(makeStyles)`, so the whole app follows the light/dark toggle.
 *
 * `colors` is still exported from `theme/index.ts`, and still has every key the
 * inherited screens read. Its *values* were repointed at the Aurora palette,
 * which is what recoloured the app in a single edit before any screen had been
 * converted. It is now down to a handful of consumers and is kept as the floor
 * under the migration: the keys are pinned by `theme.test.ts`, because a missing
 * one is a runtime `undefined` passed to a style prop, which React Native
 * silently ignores rather than erroring.
 *
 * **New work uses `useTheme()`.** `colors` cannot know the mode — it is a module
 * constant, evaluated at import time, long before a React tree exists. That one
 * fact is the whole reason `useStyles` exists; see the note in that file.
 *
 * ## Why `system` is a stored value and not just a boolean
 *
 * Three states, not two: follow the phone, force light, force dark. "Follow the
 * phone" has to be the default and has to be distinguishable from "the user
 * chose light", or changing the OS theme at dusk stops working for anyone who
 * ever touched the toggle.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SystemUI from 'expo-system-ui';

import { gradientsFor, palettes, type Gradients, type Mode, type Palette } from './palette';
import { radius, space, type } from './type';

export type ThemePreference = Mode | 'system';

const STORAGE_KEY = 'meridian.theme.v1';

export interface Theme {
  /** Colour tokens for the resolved mode. */
  t: Palette;
  /** Named gradients for the resolved mode. */
  g: Gradients;
  /** Type scale. Mode-independent. */
  type: typeof type;
  space: typeof space;
  radius: typeof radius;
  /** What is actually on screen. */
  mode: Mode;
  /** What the user asked for, which may be `system`. */
  preference: ThemePreference;
  setPreference: (next: ThemePreference) => void;
  /** Light → dark → light. What the toggle button calls. */
  toggle: () => void;
  isDark: boolean;
}

const ThemeContext = createContext<Theme | null>(null);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const system = useColorScheme();
  const [preference, setPreferenceState] = useState<ThemePreference>('system');

  // Restored asynchronously, so the first frame is whatever the OS says. That
  // is the right default to flash: it matches every other app on the phone, and
  // a user who has chosen otherwise sees their choice a frame later rather than
  // seeing white when they asked for dark.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await AsyncStorage.getItem(STORAGE_KEY);
        if (!cancelled && (stored === 'light' || stored === 'dark' || stored === 'system')) {
          setPreferenceState(stored);
        }
      } catch {
        // A readable theme is not worth an error path. `system` stands.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    // Fire and forget: the UI has already changed, and a failed write costs the
    // preference next launch, not this one.
    void AsyncStorage.setItem(STORAGE_KEY, next).catch(() => {});
  }, []);

  const mode: Mode = preference === 'system' ? (system === 'dark' ? 'dark' : 'light') : preference;

  // The window behind React Native, repainted when the mode changes.
  //
  // This is not belt-and-braces. Every translucent surface in the app composites
  // over whatever is below it, and below the React tree is the Android window,
  // whose background is `android:windowBackground` on MainActivity -- owned by
  // `expo-splash-screen` and, before this, a white drawable with no `-night`
  // variant. In dark mode that white showed through the glass borders and
  // through every `Modal`, which gets its own window and so has no `Aurora`
  // painting over it.
  //
  // `app.json` now sets the night colour so the *launch* is right; this makes
  // the toggle right too, because a user switching to dark at runtime does not
  // get a new window.
  useEffect(() => {
    // Fire and forget. A window background is cosmetic, and on web the module
    // is a no-op that still resolves.
    void SystemUI.setBackgroundColorAsync(palettes[mode].bg).catch(() => {});
  }, [mode]);

  // `toggle` resolves to the opposite of what is **currently shown**, not the
  // opposite of the preference. Tapping it while on `system` must flip the
  // screen, which is what the user is asking for; leaving them on `system` and
  // doing nothing visible would read as a broken button.
  const toggle = useCallback(() => {
    setPreference(mode === 'dark' ? 'light' : 'dark');
  }, [mode, setPreference]);

  const value = useMemo<Theme>(() => {
    const t = palettes[mode];
    return {
      t,
      g: gradientsFor(t),
      type,
      space,
      radius,
      mode,
      preference,
      setPreference,
      toggle,
      isDark: mode === 'dark',
    };
  }, [mode, preference, setPreference, toggle]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

/**
 * The theme. Throws outside the provider.
 *
 * Throwing rather than falling back to light: a silent fallback means a screen
 * that renders correctly in light mode and is quietly dead in dark mode, which
 * is exactly the bug this file is supposed to prevent.
 */
export function useTheme(): Theme {
  const theme = useContext(ThemeContext);
  if (!theme) {
    throw new Error(
      'useTheme() outside <ThemeProvider>. It is mounted at the app root, above ' +
        'the navigator — see App.tsx.',
    );
  }
  return theme;
}

/**
 * Screens still reading the legacy `colors` object, and therefore light-only.
 *
 * Kept as a list rather than a comment because it is the migration's only
 * progress marker, and because the gap between this and the file tree is the
 * honest answer to "is dark mode done".
 *
 * It is currently empty: every screen and component under `src/` resolves its
 * colours through `useTheme()`. `colors` survives for its keys, not its
 * consumers — see the note at the top of this file.
 */
export const LIGHT_ONLY: readonly string[] = [];
