/**
 * Font loading. Five files, and a hard rule about what happens if they fail.
 *
 * ## The rule: a font can never stop the app from starting
 *
 * The usual Expo pattern is `if (!loaded) return null;` — hold the whole tree
 * until `useFonts` resolves. In a safety app that is the wrong trade. This app's
 * reason to exist is that a user in trouble can open it and hit SOS; "the app
 * showed a blank screen because a 60 KB typeface did not decode" is not a
 * failure mode worth accepting for nicer letterforms.
 *
 * So `useAppFonts` reports `ready` when the fonts have loaded **or** when it has
 * given up, and the app renders either way:
 *
 * * loaded → Sora and Inter.
 * * failed or slow → React Native falls back to the platform UI face (Roboto /
 *   SF) for every unresolved `fontFamily`. Sizes, weights-by-role, spacing and
 *   colour are all unchanged, because they live in `type.ts` and not in the font
 *   file. The app looks ordinary instead of looking broken.
 *
 * `FONT_TIMEOUT_MS` exists for the slow case rather than the failed case:
 * `useFonts` rejects quickly on a bad file, but a cold start on a loaded device
 * can leave it pending. 2.5 s is past a normal load and well short of where a
 * user starts tapping the icon again.
 *
 * ## Why the weights are imported one subpath at a time
 *
 * `import { Sora_700Bold } from '@expo-google-fonts/sora'` pulls the package
 * index, which `require`s **all eight** weights — Metro bundles every one of
 * them, eight for Sora and nine for Inter, for the five we use. Importing
 * `@expo-google-fonts/sora/700Bold` bundles exactly that file.
 *
 * The five are the ones `type.ts` names. Adding a sixth means adding it in both
 * places, which is deliberate friction: see the note there about weights.
 */

import { useEffect, useState } from 'react';
import { useFonts } from 'expo-font';

import { Sora_600SemiBold } from '@expo-google-fonts/sora/600SemiBold';
import { Sora_700Bold } from '@expo-google-fonts/sora/700Bold';
import { Inter_400Regular } from '@expo-google-fonts/inter/400Regular';
import { Inter_500Medium } from '@expo-google-fonts/inter/500Medium';
import { Inter_600SemiBold } from '@expo-google-fonts/inter/600SemiBold';

/** How long to wait before starting without them. */
export const FONT_TIMEOUT_MS = 2_500;

export interface FontState {
  /** Safe to render. True on success, on failure, and on timeout. */
  ready: boolean;
  /** True only when the real faces are registered. For diagnostics. */
  loaded: boolean;
  /** Set if loading rejected. Surfaced nowhere in the UI — it is not the user's problem. */
  error: Error | null;
}

/**
 * Load the app's five faces.
 *
 * The keys are the strings `type.ts` puts in `fontFamily`. They have to match
 * exactly; a typo is invisible on Android, which silently substitutes the
 * default face rather than warning.
 */
export function useAppFonts(): FontState {
  const [loaded, error] = useFonts({
    Sora_600SemiBold,
    Sora_700Bold,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
  });

  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (loaded || error) return;
    const timer = setTimeout(() => setTimedOut(true), FONT_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [loaded, error]);

  useEffect(() => {
    if (error) {
      // Logged, not thrown, and not shown. The app is fully usable in the
      // fallback face and the user can do nothing about this.
      console.warn('[fonts] falling back to the system face:', error.message);
    }
  }, [error]);

  return {
    ready: loaded || Boolean(error) || timedOut,
    loaded,
    error: error ?? null,
  };
}
