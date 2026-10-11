/**
 * Invariant: **no audio leaves the device, and no silent fallback can make that false.**
 *
 * B8 / S18, and Phase 3's exit criterion *"No continuous audio upload anywhere in
 * the app"*.
 *
 * This test reads the voice feature's own source. That is crude, and it is the
 * only way to check the thing that actually matters here, because the failure is
 * not a wrong value — it is a **missing option**.
 *
 * ## The failure it exists to prevent
 *
 * `expo-speech-recognition` documents `requiresOnDeviceRecognition` as
 * *"prevent device from sending audio over the network"*, and in the next breath
 * as *"**only enabled if the device supports it**"*.
 *
 * Read together, those mean: on a device without on-device recognition, passing
 * `requiresOnDeviceRecognition: true` is **silently ignored** and the microphone
 * is streamed to a third party. No error, no event, no way for the app to know
 * after the fact. And if somebody simply *forgets* the option on a new `start()`
 * call, the default is `false` — network recognition, by default, with nothing
 * to say so.
 *
 * So two things have to be true of every `start()` call in this feature, and
 * neither is visible in a running app:
 *
 * 1. it passes `requiresOnDeviceRecognition: true`;
 * 2. the module checked `supportsOnDeviceRecognition()` first and refused when
 *    false — because (1) alone is a request, not a guarantee.
 *
 * A unit test of behaviour cannot check either: the recogniser is native, the
 * difference between on-device and network recognition is invisible from JS, and
 * a mock would assert what the mock does. Reading the source is what is left.
 *
 * ## Why it also forbids a fallback
 *
 * `IMPLEMENTATION_PLAN.md` S18: *"**If no library meets the privacy bar, ship a
 * prominent manual SOS and say so in `PROGRESS.md` — do not ship a fake.**"*
 *
 * The tempting "improvement" to this feature is to offer network recognition
 * when on-device is unavailable, behind a warning. That would be the fake: a
 * safety feature whose privacy property depends on a dialog the user tapped
 * through weeks ago. The refusal is the product decision, so the refusal is what
 * is pinned.
 */

import { readFileSync } from 'fs';
import { join } from 'path';

const VOICE_DIR = __dirname;

const read = (file: string): string => readFileSync(join(VOICE_DIR, file), 'utf8');

/**
 * Every module in this feature that starts the recogniser.
 *
 * `useHotWordListener.ts` and `VoiceSosPanel.tsx` were deleted when listening
 * moved app-wide: the recogniser session has to exist **exactly once** for the
 * whole app, and a per-screen hook plus a panel that each started one meant two
 * sessions on one microphone as soon as both were mounted.
 * `useVoiceGuard.ts`, mounted in `GuardianProvider`, replaces both.
 */
const RECOGNISER_MODULES = ['useVoiceGuard.ts', 'dictate.ts'] as const;

/**
 * Source with comments and docstrings stripped.
 *
 * Necessary, not fastidious: these files *discuss* network recognition at
 * length, so a naive search for the word "network" matches the very comments
 * explaining why it is refused. Only executable code is checked.
 */
function codeOnly(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '') // block comments and JSDoc
    .replace(/^\s*\/\/.*$/gm, ''); // line comments
}

describe.each(RECOGNISER_MODULES)('%s', file => {
  const code = codeOnly(read(file));

  /**
   * Every `start()` must ask for on-device recognition.
   *
   * The default is `false`. A `start()` call that simply omits the option gets
   * network recognition, and nothing anywhere would report it — which is why
   * this counts the `start(` calls and the option occurrences and requires them
   * to match, rather than only checking the option appears somewhere in the file.
   */
  it('passes requiresOnDeviceRecognition: true on every start() call', () => {
    // `recognizer.start(` since the lazy-accessor refactor — the module is no
    // longer a static import. See `recognizer.ts`.
    const starts = code.match(/recognizer\.start\(/g) ?? [];
    expect(starts.length).toBeGreaterThan(0);

    const onDevice = code.match(/requiresOnDeviceRecognition:\s*true/g) ?? [];
    expect(onDevice.length).toBe(starts.length);
  });

  it('never passes requiresOnDeviceRecognition: false', () => {
    expect(code).not.toMatch(/requiresOnDeviceRecognition:\s*false/);
  });

  /**
   * The option is a request; this is the guarantee.
   *
   * Without this check the module would be asking politely and proceeding
   * regardless on a device that ignores the request.
   */
  it('refuses to start unless the device supports on-device recognition', () => {
    expect(code).toMatch(/supportsOnDeviceRecognition\(\)/);
    // Negated — `if (!supports...)` — because the check has to be a *guard* that
    // returns or throws, not a value that gets logged and then ignored.
    expect(code).toMatch(/!\s*recognizer\.supportsOnDeviceRecognition\(\)/);
  });

  /**
   * Audio must never be written to disk.
   *
   * `recordingOptions.persist` defaults to false, so this is belt and braces —
   * but a persisted recording of somebody shouting their SOS phrase, sitting in
   * the app's data directory with no retention policy, is exactly the kind of
   * thing that gets switched on while debugging and left on.
   */
  it('never persists a recording', () => {
    expect(code).not.toMatch(/persist:\s*true/);
    expect(code).toMatch(/persist:\s*false/);
  });

  /** No upload path in the voice feature at all. */
  it('does not upload anything', () => {
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/XMLHttpRequest/);
    expect(code).not.toMatch(/FormData/);
    expect(code).not.toMatch(/apiService/);
    expect(code).not.toMatch(/axios/);
  });
});

describe('the feature as a whole', () => {
  /**
   * No module here may import the HTTP client.
   *
   * The hot-word path is local by construction, and an import is how that stops
   * being true — someone adding "report which phrase triggered, for analytics"
   * would be sending a transcript of what somebody said in an emergency.
   */
  it.each(['dictate.ts', 'hotwords.ts', 'recognizer.ts'])(
    '%s does not import an HTTP client',
    file => {
      const code = codeOnly(read(file));
      expect(code).not.toMatch(/from\s+['"].*api\.service['"]/);
      expect(code).not.toMatch(/from\s+['"]axios['"]/);
      expect(code).not.toMatch(/from\s+['"].*lib\/supabase['"]/);
    },
  );

  /**
   * `useVoiceGuard` is the exception, and only for the phrase list.
   *
   * It reads `sos_hot_words` through Supabase — the same table the hot-words
   * screen writes, with RLS scoping the select to the signed-in user. That is a
   * read of the user's own settings, not a transmission of anything heard: no
   * transcript, no loudness reading and no audio may leave the device, so an
   * HTTP client is still forbidden and `apiService` must not appear.
   */
  it('useVoiceGuard.ts reads phrases but ships no HTTP client', () => {
    const code = codeOnly(read('useVoiceGuard.ts'));
    expect(code).not.toMatch(/from\s+['"].*api\.service['"]/);
    expect(code).not.toMatch(/from\s+['"]axios['"]/);
    // The only network call is the phrase SELECT.
    expect(code).toMatch(/from\(['"]sos_hot_words['"]\)/);
    // Nothing heard is sent anywhere.
    expect(code).not.toMatch(/\.insert\(/);
    expect(code).not.toMatch(/\.upsert\(/);
  });

  /**
   * The old upload path must stay deleted.
   *
   * `services/speech.service.ts` and `hooks/useVoiceRecorder.ts` recorded a clip
   * and posted it to `/ai/speech-to-text` so this screen could fill in a text
   * field. B8 removed both. Re-importing either would reintroduce the upload
   * through the back door, under a name that sounds harmless.
   */
  it('does not reach for the removed upload-based speech service', () => {
    for (const file of ['useVoiceGuard.ts', 'dictate.ts', 'recognizer.ts']) {
      const code = codeOnly(read(file));
      expect(code).not.toMatch(/speech\.service/);
      expect(code).not.toMatch(/useVoiceRecorder/);
    }
  });

  /**
   * The shout gate compares a *recent peak*, not an instantaneous reading.
   *
   * The loud part of "help me" is its first syllable and the transcript arrives
   * a beat later, so comparing the volume at match time would reject every
   * genuine shout. The window has to exist and has to be short — long enough to
   * cover the lag, short enough that a door slamming a minute ago does not
   * qualify somebody's quiet mention of the phrase.
   */
  it('gates a match on loudness within a bounded recent window', () => {
    // Read out of the source rather than imported. Importing the module pulls in
    // `expo-speech-recognition`, a native module, into a test whose whole job is
    // to read text -- and a dynamic import needs --experimental-vm-modules,
    // which this project's jest does not run with.
    // The session cap moved with listening: `useVoiceGuard` is armed from the
    // Guardian screen and stays armed until the user disarms it, so what is
    // pinned now is the shout window -- the span in which loudness must have
    // peaked for a match to count as a shout.
    const code = read('useVoiceGuard.ts');
    expect(code).toMatch(/export const SHOUT_WINDOW_MS = 2500;/);
  });
});

/**
 * Invariant: **the app must still open on a runtime that cannot do this.**
 *
 * Added after a crash, and the crash is the justification.
 *
 * ```
 * ERROR  [runtime not ready]: Error: Cannot find native module 'ExpoSpeechRecognition'
 * ```
 *
 * The whole app failed to open in Expo Go — not the voice feature, the app, at
 * boot, before a single screen rendered. `expo-speech-recognition`'s entry point
 * calls `requireNativeModule(...)` **at module evaluation**, and that throws when
 * the native side is absent. A static `import` of it is therefore a throw at
 * bundle-evaluation time, and `App.tsx → RootNavigator → ProfileNavigator →
 * SOSHotWordsScreen → VoiceSosPanel` is an unbroken chain of static imports.
 *
 * Every careful capability check in `useHotWordListener` sat downstream of an
 * import that had already killed the app. **A capability check cannot live behind
 * a static import of the thing whose absence it is checking for.**
 *
 * So exactly one module may name the package, and it uses `require()` in a
 * `try`. These tests are cheap and they pin the one thing that turns a disabled
 * feature into an unusable app.
 */
describe('the app survives a runtime without the native module', () => {
  const ALL_FEATURE_FILES = [
    'useVoiceGuard.ts',
    'dictate.ts',
    'hotwords.ts',
    'recognizer.ts',
  ] as const;

  it.each(ALL_FEATURE_FILES)('%s does not statically import the package', file => {
    const code = codeOnly(read(file));
    expect(code).not.toMatch(/^\s*import\s[^;]*from\s+['"]expo-speech-recognition['"]/m);
    expect(code).not.toMatch(/^\s*import\s+['"]expo-speech-recognition['"]/m);
  });

  /**
   * `recognizer.ts` is the single exception, and it earns it by using `require`
   * in a `try` — Metro evaluates a `require`d module on first call, so the throw
   * is catchable there instead of fatal at boot.
   */
  it('recognizer.ts loads the package lazily, inside a try', () => {
    const code = codeOnly(read('recognizer.ts'));
    expect(code).toMatch(/require\(['"]expo-speech-recognition['"]\)/);
    expect(code).toMatch(/try\s*\{/);
    expect(code).toMatch(/catch/);
    // A type-only import is erased by the compiler, so it is allowed — but a
    // value import here would be the original bug.
    expect(code).not.toMatch(/^\s*import\s+\{[^}]*\}\s*from\s+['"]expo-speech-recognition['"]/m);
  });

  /**
   * `null` has to be a reportable state, not an exception.
   *
   * The feature degrades by telling the user it needs the development build and
   * pointing at the manual SOS button — the same shape as the on-device refusal
   * it already had. If this status disappeared, the accessor returning `null`
   * would surface as some generic failure with no remedy attached.
   */
  it('reports a missing native module with an actionable message', () => {
    const code = read('useVoiceGuard.ts');
    expect(code).toMatch(/development build/);
    // And it names what still works, because "voice SOS is unavailable" with no
    // alternative is where a user gives up on the whole feature.
    expect(code).toMatch(/[Ss]hake-to-SOS/);
  });

  /**
   * Nothing may use `useSpeechRecognitionEvent`.
   *
   * It is the package's only documented subscription API and it imports the
   * module statically, so reaching for it reintroduces the boot crash — behind a
   * name that looks like the idiomatic choice, which is exactly why it needs a
   * test rather than a comment.
   */
  it.each(ALL_FEATURE_FILES)('%s does not use the package event hook', file => {
    expect(codeOnly(read(file))).not.toMatch(/useSpeechRecognitionEvent/);
  });
});
