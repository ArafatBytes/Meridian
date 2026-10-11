/**
 * The only module that touches `expo-speech-recognition`. B8 / S18.
 *
 * It exists because of a crash, and the crash is worth writing down because the
 * mistake is easy to repeat with any native module.
 *
 * ## The crash
 *
 * ```
 * ERROR  [runtime not ready]: Error: Cannot find native module 'ExpoSpeechRecognition'
 * ```
 *
 * The app would not open **at all** in Expo Go. Not the voice feature — the whole
 * app, at boot, before any screen rendered.
 *
 * `expo-speech-recognition`'s entry point is three lines, and the first one runs
 * on import:
 *
 * ```js
 * export const ExpoSpeechRecognitionModule = requireNativeModule("ExpoSpeechRecognition");
 * ```
 *
 * `requireNativeModule` **throws** when the native side is absent, and it does so
 * at *module evaluation*, not at first call. So a plain
 * `import { ExpoSpeechRecognitionModule } from 'expo-speech-recognition'` is a
 * throw at import time on any runtime without the native module compiled in —
 * which is exactly Expo Go.
 *
 * And because `App.tsx` → `RootNavigator` → `ProfileNavigator` →
 * `SOSHotWordsScreen` → `VoiceSosPanel` is a chain of **static** imports, that
 * throw happened while the bundle was still being evaluated. Every careful
 * capability check in `useHotWordListener` was downstream of an import that had
 * already killed the app.
 *
 * The lesson generalises: a capability check cannot live behind a static import
 * of the thing whose absence it is checking for.
 *
 * ## The fix
 *
 * `require()` inside a `try`, once, cached. Metro's `require` evaluates a module
 * on first call rather than at bundle time, so the throw is catchable here
 * instead of fatal at boot. Everything else in `features/voice/` goes through
 * `getRecognizer()` and gets `null` on a runtime that cannot do this.
 *
 * `null` is then a first-class answer all the way up: `useHotWordListener`'s
 * preflight returns `no-native-module`, the panel says the feature needs the
 * development build, and the manual SOS button is right there. Which is the same
 * shape as the on-device refusal the feature already had — one more reason the
 * device cannot listen, reported the same way, rather than a special case.
 *
 * ## Why not check `Constants.executionEnvironment === StoreClient`
 *
 * Because it answers a different question. Expo Go is *a* runtime without the
 * module; it is not the only one. A development build made before this
 * dependency was added, a bare build where autolinking did not pick it up, a web
 * bundle — all have no native module and none of them are Expo Go. Asking
 * "can I load it?" is the actual question, and the answer is the attempt.
 */

/**
 * The module's type, taken from the package without importing it at runtime.
 *
 * `typeof import(...)` in a *type* position is erased by the compiler, so this
 * costs nothing at runtime — which is the whole point, since an actual import is
 * what crashed the app. The package does not re-export
 * `ExpoSpeechRecognitionModuleType` from its index, and reaching into
 * `expo-speech-recognition/build/...` for it would couple us to its build layout.
 */
type Recognizer = typeof import('expo-speech-recognition')['ExpoSpeechRecognitionModule'];

/**
 * `undefined` = not tried yet. `null` = tried, unavailable.
 *
 * Three states rather than two, so a genuinely absent module is not re-required
 * on every call — `require` is cheap after the first evaluation, but the throw
 * is not, and `getRecognizer()` is called from a render path.
 */
let cached: Recognizer | null | undefined;

/**
 * The native module, or `null` on a runtime that does not have it.
 *
 * Never throws. Callers must handle `null` — and the type says so, which is what
 * makes every call site's guard a compile-time obligation rather than a habit.
 */
export function getRecognizer(): Recognizer | null {
  if (cached !== undefined) return cached;
  try {
    // `require`, not `import`. See the module docstring: a static import of this
    // package is a throw at bundle-evaluation time when the native module is
    // absent, and it took the whole app down with it.
    //
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('expo-speech-recognition');
    cached = (mod?.ExpoSpeechRecognitionModule ?? null) as Recognizer | null;
  } catch {
    // The expected path in Expo Go. Not logged as an error: it is a correct
    // answer about this runtime, and a scary line in the console would send the
    // next person looking for a bug.
    cached = null;
  }
  return cached;
}

/** Whether this runtime can do speech recognition at all. */
export function isRecognizerAvailable(): boolean {
  return getRecognizer() !== null;
}

/**
 * Subscribe to one recogniser event, or get a no-op unsubscribe.
 *
 * Wraps `addListener` so callers do not each repeat the null check. The module
 * inherits `addListener` from expo's `NativeModule`; the package's only
 * documented subscription API is the `useSpeechRecognitionEvent` **hook**, which
 * is no use here for two reasons: it cannot be called inside a promise
 * (`dictate.ts` needs that), and it imports the module statically — so using it
 * would reintroduce the boot crash this file exists to prevent.
 */
export function onRecognizerEvent(
  event: 'result' | 'end' | 'error' | 'start' | 'volumechange',
  handler: (payload: never) => void,
): () => void {
  const recognizer = getRecognizer();
  if (!recognizer) return () => {};
  // @ts-expect-error - the event map is keyed per event name and the union of
  // payloads is not expressible here without duplicating the package's types.
  const subscription = recognizer.addListener(event, handler);
  return () => subscription.remove();
}

/**
 * Ask Android to download an offline language pack.
 *
 * The remedy for "no offline language pack is installed", which is the common
 * reason a phone that *can* do on-device recognition still refuses to listen.
 *
 * On Android 13 this opens a system dialog and emits nothing afterwards
 * (`opened_dialog`), so the caller has to tell the user to come back and try
 * again rather than waiting for a result that will never arrive.
 */
export async function downloadOfflineModel(
  locale = 'en-US',
): Promise<{ status: string; message: string }> {
  const recognizer = getRecognizer();
  if (!recognizer) {
    throw new Error(
      'This needs the Meridian development build — Expo Go cannot load the speech ' +
        'recogniser.',
    );
  }
  return recognizer.androidTriggerOfflineModelDownload({ locale });
}
