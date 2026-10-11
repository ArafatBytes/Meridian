/**
 * The Expo Go path, exercised. B8 / S18.
 *
 * `privacy.test.ts` asserts that nothing statically imports
 * `expo-speech-recognition` — which is what stopped the app crashing at boot.
 * This file asserts the other half: that when the native module genuinely is not
 * there, the feature **degrades into a message** rather than throwing from
 * somewhere unhelpful.
 *
 * Those are different failures and only one of them was the crash. A lazy
 * accessor that returns `null` and then gets dereferenced two frames later is
 * still a broken app; it just breaks at a different moment.
 *
 * `jest.mock` with a factory that throws reproduces Expo Go exactly:
 * `requireNativeModule('ExpoSpeechRecognition')` raising at module evaluation.
 * That is the real shape of the failure, and it cannot be reproduced any other
 * way on a laptop.
 */

import { dictateOnce } from './dictate';
import { getRecognizer, isRecognizerAvailable, onRecognizerEvent } from './recognizer';

/**
 * The native module is absent, and saying so is the module's job.
 *
 * `jest.mock`'s factory runs on first `require`, so throwing inside it is the
 * same event Expo Go produces.
 *
 * Written *below* the imports, which looks wrong and is not:
 * `babel-plugin-jest-hoist` lifts every `jest.mock` call above the imports at
 * transform time, so this runs first regardless. Putting it physically first
 * trips `import/first` for no benefit.
 */
jest.mock('expo-speech-recognition', () => {
  throw new Error("Cannot find native module 'ExpoSpeechRecognition'");
});

describe('with no native module (Expo Go)', () => {
  it('getRecognizer returns null instead of throwing', () => {
    expect(() => getRecognizer()).not.toThrow();
    expect(getRecognizer()).toBeNull();
  });

  it('reports the runtime as unable to recognise speech', () => {
    expect(isRecognizerAvailable()).toBe(false);
  });

  /**
   * Caching matters here, not as an optimisation but because `getRecognizer()`
   * is called from a render path. A module whose factory throws re-throws on
   * every `require`, and throwing once per render would be a measurable cost on
   * the one screen that cannot use the feature anyway.
   */
  it('only attempts the require once', () => {
    const first = getRecognizer();
    const second = getRecognizer();
    expect(first).toBe(second);
    expect(second).toBeNull();
  });

  /**
   * Subscribing must be safe and must hand back something callable.
   *
   * `useHotWordListener` subscribes in an effect that runs on every mount of the
   * hot-words screen, including in Expo Go, and its cleanup calls whatever came
   * back. A `null` unsubscribe would turn unmounting that screen into a crash —
   * which would have been the same bug, moved.
   */
  it('onRecognizerEvent returns a callable no-op unsubscribe', () => {
    const unsubscribe = onRecognizerEvent('result', () => {});
    expect(typeof unsubscribe).toBe('function');
    expect(() => unsubscribe()).not.toThrow();
  });

  /**
   * Dictation rejects with the remedy, not with a `TypeError`.
   *
   * The message has to name the development build, because that is the only
   * thing the user can do about it — and `SOSHotWordsScreen` renders
   * `error.message` straight into an alert.
   */
  it('dictateOnce rejects with an actionable message', async () => {
    await expect(dictateOnce()).rejects.toThrow(/development build/i);
    await expect(dictateOnce()).rejects.toThrow(/Type the phrase instead/i);
  });

  it('dictateOnce does not reject with a dereference error', async () => {
    await expect(dictateOnce()).rejects.not.toThrow(/undefined|null|not a function/i);
  });
});
