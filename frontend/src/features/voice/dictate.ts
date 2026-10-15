/**
 * One-shot on-device dictation, for filling in a hot-word field. B8 / S18.
 *
 * Replaces the round trip the hot-words screen used to make: record a clip with
 * `expo-audio`, upload it to `/ai/speech-to-text`, wait, show the result. Three
 * things were wrong with that, in increasing order of seriousness:
 *
 * 1. It needed a stop button, a duration counter and a 30-second cap — all to
 *    bound a recording that only existed in order to be uploaded.
 * 2. The endpoint behind it did not work. `app/services/ai/speech_service.py`
 *    had its `pydub` import commented out while still calling `AudioSegment`, so
 *    it raised `NameError` on every request. That was **defect 2**, and it was
 *    closed on 2026-10-15 by **deleting** the endpoint and the service rather
 *    than repairing them — this file is why there was nothing left to repair.
 * 3. It sent a recording of somebody's voice to a server to fill in a text
 *    field. On the screen whose entire subject is a phrase you will shout in an
 *    emergency.
 *
 * This does the same job with the recogniser already on the phone, and — like
 * `useHotWordListener` — **refuses rather than falling back** when the device
 * cannot do it without the network. The text field was always the primary way to
 * enter a phrase, so refusing costs the user a tap of the keyboard rather than
 * the feature.
 *
 * ## Why a promise rather than the hook
 *
 * `useHotWordListener` is a long-lived armed session with restarts, a countdown
 * and a trigger. This is "listen once, give me the words, stop" — closer to a
 * function call than to a piece of state, and the call site is an `onPress`
 * handler that wants to `await` it. Sharing the hook would have meant a second
 * mode flag through all of its branches.
 *
 * Events come from the module's `addListener`, which it inherits from expo's
 * `NativeModule`. The package's only documented subscription API is the
 * `useSpeechRecognitionEvent` hook, which is unusable here twice over: a hook
 * cannot be called inside a promise, and it imports the native module
 * statically — which is what crashed the app at boot in Expo Go. The module
 * itself comes from `getRecognizer()`; see `recognizer.ts`.
 */

import { Platform } from 'react-native';

import { getRecognizer } from './recognizer';

export interface DictationResult {
  transcript: string;
  /** 0–1, or -1 when the engine does not report one. */
  confidence: number;
}

/**
 * How long to wait before giving up.
 *
 * The recogniser normally ends by itself when speech stops. This is the backstop
 * for when it does not — a stuck session would otherwise leave the screen
 * showing "Listening…" with a disabled button and no way out.
 */
const TIMEOUT_MS = 15_000;

/**
 * Listen once and return what was said.
 *
 * Rejects with a message fit to show the user:
 *
 * * the platform has no recogniser;
 * * the device cannot recognise speech without the network — refused, not
 *   downgraded, for the reason in `useHotWordListener`'s docstring;
 * * permission was declined;
 * * nothing was heard before the timeout.
 */
export async function dictateOnce(): Promise<DictationResult> {
  if (Platform.OS !== 'android' && Platform.OS !== 'ios') {
    throw new Error('Dictation is only available on Android and iOS.');
  }
  // Before every other check, because they are all methods on this object, and
  // in Expo Go there is no object. See `recognizer.ts`.
  const recognizer = getRecognizer();
  if (!recognizer) {
    throw new Error(
      'Dictation needs the Meridian development build — Expo Go cannot load the ' +
        'speech recogniser. Type the phrase instead.',
    );
  }
  if (!recognizer.isRecognitionAvailable()) {
    throw new Error('This phone has no speech recogniser available.');
  }
  // The same refusal the listener makes, for the same reason:
  // `requiresOnDeviceRecognition` is silently ignored on a device that cannot do
  // it, so without this check "on-device dictation" would quietly upload audio.
  if (!recognizer.supportsOnDeviceRecognition()) {
    throw new Error(
      'This phone cannot recognise speech without sending audio to a server, so ' +
        'Meridian will not use the microphone here. Type the phrase instead.',
    );
  }

  const permission = await recognizer.requestPermissionsAsync();
  if (!permission.granted) {
    throw new Error('Microphone access is needed to dictate a phrase.');
  }

  return new Promise<DictationResult>((resolve, reject) => {
    let best: DictationResult | null = null;
    let settled = false;

    // Every listener is removed on every exit path. A leaked native listener
    // fires into a resolved promise on the *next* dictation, which shows up as
    // the field filling in with the previous attempt's words.
    const subscriptions: { remove: () => void }[] = [];
    const cleanup = () => {
      clearTimeout(timer);
      subscriptions.forEach(subscription => subscription.remove());
      try {
        recognizer.abort();
      } catch {
        // Already stopped.
      }
    };

    const finish = (result: DictationResult) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(result);
    };
    const fail = (message: string) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new Error(message));
    };

    const timer = setTimeout(() => {
      // A partial result is better than nothing: the user can edit it. Only a
      // completely empty session is a failure.
      if (best?.transcript) finish(best);
      else fail('Nothing was heard. Try again, or type the phrase.');
    }, TIMEOUT_MS);

    subscriptions.push(
      recognizer.addListener('result', event => {
        const first = event.results?.[0];
        if (!first?.transcript) return;
        // Interim results are kept as `best` rather than resolved on, so a
        // half-heard phrase is available if the session dies before finalising.
        best = { transcript: first.transcript, confidence: first.confidence ?? -1 };
        if (event.isFinal) finish(best);
      }),
    );

    subscriptions.push(
      recognizer.addListener('end', () => {
        if (best?.transcript) finish(best);
        else fail('Nothing was heard. Try again, or type the phrase.');
      }),
    );

    subscriptions.push(
      recognizer.addListener('error', event => {
        if (event.error === 'aborted') return; // our own cleanup
        if (best?.transcript) {
          finish(best);
          return;
        }
        fail(
          event.error === 'no-speech'
            ? 'Nothing was heard. Try again, or type the phrase.'
            : `Could not dictate: ${event.message || event.error}`,
        );
      }),
    );

    try {
      recognizer.start({
        lang: 'en-US',
        requiresOnDeviceRecognition: true,
        // One utterance, not a session. The opposite of the hot-word listener.
        continuous: false,
        interimResults: true,
        maxAlternatives: 1,
        addsPunctuation: false,
        recordingOptions: { persist: false },
      });
    } catch (problem: any) {
      fail(problem?.message ?? 'Could not start the recogniser.');
    }
  });
}
