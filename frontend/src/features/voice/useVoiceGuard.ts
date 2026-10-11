/**
 * Listening for a **shouted** hot word, app-wide. B8 / S18.
 *
 * The brief: *"a background voice detection agent running in the app which will
 * work all the time to detect any voice above a certain decibel (so that SOS
 * enables only by shouting) and if it matches any of the saved hotwords in his
 * account then SOS will be triggered automatically."*
 *
 * This is that, with one limit stated honestly below.
 *
 * ## The shout gate
 *
 * Loudness comes from the recogniser's `volumechange` event, a float from **−2
 * to 10** (Android's `onRmsChanged` RMS value; anything at or below 0 is
 * inaudible). It is **not** decibels, and it is not comparable between handsets
 * — microphone, case and grip all move it. So the threshold is a user setting
 * with a live meter beside it, not a constant: `guardianStore` carries it and
 * the Guardian screen is where it gets calibrated.
 *
 * A match is accepted only if the **peak loudness within
 * `SHOUT_WINDOW_MS` before it** cleared the threshold. A window, not an
 * instantaneous reading, because the loud part of "help me" is the first
 * syllable and the transcript arrives a beat later — comparing the volume at
 * match time would reject every genuine shout.
 *
 * ## The limit: this runs while the app is open, not with it closed
 *
 * It cannot be otherwise, and the reason is the platform rather than this code.
 * Android has restricted microphone access for apps that are not in the
 * foreground since Android 9, and `SpeechRecognizer` — which every React Native
 * speech library wraps, this one included — simply stops returning results.
 * Holding the mic with the app closed needs a **foreground service** of type
 * `microphone`, which means a permanent notification and a native service class;
 * no Expo module provides one, so it is a config-plugin-and-Kotlin job, not a
 * JS one.
 *
 * What is delivered: armed from any screen, surviving navigation between tabs,
 * running with the screen on and the app in front. What is not: the phone in a
 * pocket with Meridian closed. **The Guardian screen says exactly that**, in
 * those words, because a safety feature that implies it is listening when it is
 * not is worse than one that says plainly what it does — and because the shake
 * trigger *does* keep working in that case, which is the honest answer to give.
 *
 * ## Why the session restarts itself
 *
 * `continuous: true` still ends: on a long silence, on an audio-focus change,
 * when another app takes the microphone. Restarting is what makes "armed" mean
 * armed rather than "listened once". The failure counter stops that becoming an
 * infinite retry loop against a microphone that is genuinely unavailable.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

import { useAuthStore } from '../../store';
import { supabase } from '../../lib/supabase';
import { useGuardianStore } from '../guardian/guardianStore';
import { useLiveMeters } from '../guardian/liveMeters';
import { matchHotWord } from './hotwords';
import { getRecognizer, onRecognizerEvent } from './recognizer';

/**
 * How far back a shout counts, in milliseconds.
 *
 * 2.5 seconds. The loudness peak of a shouted phrase lands on its first
 * syllable; the transcript that contains the phrase arrives when the recogniser
 * has heard enough of it, typically a second or two later. Comparing the
 * instantaneous volume at match time would reject every real shout and accept
 * only someone who happened to still be loud.
 */
export const SHOUT_WINDOW_MS = 2500;

/** How long after the recogniser ends before restarting a segment. */
const RESTART_DELAY_MS = 400;

/**
 * How long to wait after an SOS finishes before listening again.
 *
 * Two seconds. The camera releases the microphone on its own schedule and a
 * recogniser started into a still-closing audio session fails with `busy`,
 * which then counts against the restart-failure limit and disarms the guard
 * for a reason that has nothing to do with the user.
 */
const RESUME_AFTER_TRIGGER_MS = 2000;

/** Consecutive restart failures before giving up. */
const MAX_CONSECUTIVE_FAILURES = 3;

/** Volume sampling interval. 150 ms is ~7 readings a second — enough for a peak. */
const VOLUME_INTERVAL_MS = 150;

const PREFERRED_LOCALES = ['en-US', 'en-IN', 'en-GB', 'bn-BD', 'bn-IN'] as const;
const ANDROID_ON_DEVICE_SERVICE = 'com.google.android.as';

export interface VoiceGuardOptions {
  /** Called once per accepted shout. The guard stops listening first. */
  onTrigger: (phrase: string, loudness: number) => void;
  /**
   * True while an SOS is in flight (countdown, camera, upload).
   *
   * The guard stops listening the instant a phrase matches — it has to, or a
   * `continuous` session fires the trigger two or three times for one spoken
   * phrase. What it must also do is **start again afterwards**, and this is how
   * it knows when "afterwards" is.
   *
   * It cannot simply restart immediately: the SOS flow records a video, which
   * needs the microphone. Two things competing for it gives you a recogniser
   * that fails to start and a recording with no audio.
   *
   * Without this the guard went deaf after the first trigger while
   * `voiceArmed` stayed true — so the switch said "Listening on this device",
   * the microphone was closed, and shouting did nothing. That was the bug.
   */
  paused?: boolean;
}

export interface VoiceGuardState {
  /** Whether the recogniser is actually running right now. */
  listening: boolean;
  /** The last transcript seen. On screen only — never uploaded. */
  heard: string;
  // `loudness` and `peakLoudness` are deliberately absent. They change ~7x a
  // second, and this hook is mounted above the navigator in `GuardianProvider`
  // — returning them re-rendered the entire app at that rate for as long as
  // voice SOS was armed. Read them from `useLiveMeters`, which only the
  // Guardian screen subscribes to.
  /** The phrases being listened for, as stored. */
  phrases: string[];
  error: string | null;
  /** Why it cannot listen, when it cannot. */
  unavailable: string | null;
}

/**
 * The app-wide voice guard. Mount **once**, in `GuardianProvider`.
 *
 * Driven by `guardianStore.voiceArmed` rather than by a prop, so any screen can
 * arm it by setting one value and no screen has to own the session.
 */
export function useVoiceGuard({
  onTrigger,
  paused = false,
}: VoiceGuardOptions): VoiceGuardState {
  const armed = useGuardianStore(state => state.voiceArmed);
  const setVoiceArmed = useGuardianStore(state => state.setVoiceArmed);
  const shoutThreshold = useGuardianStore(state => state.shoutThreshold);
  // The id, not the whole user. Two reasons: the hook only needs to reload
  // phrases when the signed-in identity changes, and `[user?.id]` as a
  // dependency is an optional chain that React Compiler cannot match against
  // its inferred dependencies -- it refuses to memoize the hook at all and
  // says so as a lint error.
  const userId = useAuthStore(state => state.user?.id);

  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState('');
  const [phrases, setPhrases] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);

  // Loudness is DELIBERATELY NOT React state, and this is the most important
  // line in the file.
  //
  // `volumechange` fires about seven times a second while listening. This hook
  // runs inside `GuardianProvider`, which wraps the entire navigator — so
  // `setLoudness` on every sample re-rendered **the whole app seven times a
  // second** for as long as voice SOS was armed. Every screen, every list, every
  // map marker. That is not a tuning problem, it is the app spending its frame
  // budget redrawing itself instead of doing anything.
  //
  // It is written straight into the `liveMeters` store instead, which only the
  // Guardian screen subscribes to. Same reading on the meter, no render above it.

  const armedRef = useRef(false);
  const phrasesRef = useRef<string[]>([]);
  const thresholdRef = useRef(shoutThreshold);
  const onTriggerRef = useRef(onTrigger);
  const localeRef = useRef<string>('en-US');
  const triggeredRef = useRef(false);
  const failuresRef = useRef(0);
  const restartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Rolling `(timestamp, loudness)` samples, trimmed to the shout window. */
  const volumeTrail = useRef<{ at: number; value: number }[]>([]);

  useEffect(() => {
    phrasesRef.current = phrases;
    thresholdRef.current = shoutThreshold;
    onTriggerRef.current = onTrigger;
  }, [phrases, shoutThreshold, onTrigger]);

  // -----------------------------------------------------------------------
  // The phrases
  // -----------------------------------------------------------------------
  //
  // Read from `sos_hot_words` through Supabase, which is how the hot-words
  // screen writes them — RLS scopes the select to the signed-in user, so there
  // is nothing to filter here beyond having a user at all.
  const loadPhrases = useCallback(async () => {
    if (!userId) {
      setPhrases([]);
      return [];
    }
    try {
      const { data, error: queryError } = await supabase
        .from('sos_hot_words')
        .select('hot_word')
        .eq('user_id', userId);
      if (queryError) throw queryError;
      const list = (data ?? []).map(row => row.hot_word as string).filter(Boolean);
      setPhrases(list);
      // The ref is NOT written here. Mutating it inside this `useCallback` is
      // what made React Compiler refuse to memoize the whole hook ("existing
      // memoization could not be preserved"), and the sync effect above already
      // mirrors `phrases` into the ref. The arm path below sets it explicitly
      // from the returned list so it does not have to wait for that effect.
      return list;
    } catch (problem) {
      console.warn('Could not load hot words:', problem);
      return [];
    }
  }, [userId]);

  // Loaded whenever the signed-in user changes, so arming does not have to wait
  // on a round trip.
  useEffect(() => {
    void loadPhrases();
  }, [loadPhrases]);

  // -----------------------------------------------------------------------
  // Starting a segment
  // -----------------------------------------------------------------------

  const startSegment = useCallback((): boolean => {
    const recognizer = getRecognizer();
    if (!recognizer) return false;
    try {
      recognizer.start({
        lang: localeRef.current,
        // The privacy bar. Gated by `supportsOnDeviceRecognition()` in
        // `preflight` below, because on a device that cannot honour it this
        // option is silently ignored and the microphone is streamed to a server.
        requiresOnDeviceRecognition: true,
        continuous: true,
        // Matched too: in an emergency, waiting for the engine to finalise costs
        // a second or two, and the shout gate plus whole-word matching is what
        // keeps the extra sensitivity from buying false positives.
        interimResults: true,
        maxAlternatives: 1,
        addsPunctuation: false,
        recordingOptions: { persist: false },
        // The shout gate's input. Without this the whole feature is just
        // hot words again.
        volumeChangeEventOptions: { enabled: true, intervalMillis: VOLUME_INTERVAL_MS },
      });
      return true;
    } catch (problem) {
      console.warn('voice guard failed to start:', problem);
      return false;
    }
  }, []);

  /** Can this device listen privately? Returns a user-facing reason, or null. */
  const preflight = useCallback(async (): Promise<string | null> => {
    if (Platform.OS !== 'android' && Platform.OS !== 'ios') {
      return 'Voice SOS is only available on Android and iOS.';
    }
    const recognizer = getRecognizer();
    if (!recognizer) {
      return (
        'Voice SOS needs the Meridian development build — Expo Go cannot load the ' +
        'speech recogniser. Shake-to-SOS and the SOS button still work.'
      );
    }
    if (!recognizer.isRecognitionAvailable()) {
      return 'This phone has no speech recogniser available.';
    }
    // The refusal, not a downgrade. See the module docstring of `recognizer.ts`.
    if (!recognizer.supportsOnDeviceRecognition()) {
      return (
        'This phone cannot recognise speech without sending audio to a server, so ' +
        'Meridian will not listen. Use shake-to-SOS or the SOS button.'
      );
    }

    let installed: string[] = [];
    try {
      const supported = await recognizer.getSupportedLocales(
        Platform.OS === 'android'
          ? { androidRecognitionServicePackage: ANDROID_ON_DEVICE_SERVICE }
          : {},
      );
      installed = supported.installedLocales ?? [];
    } catch {
      installed = [];
    }
    const locale =
      PREFERRED_LOCALES.find(candidate => installed.includes(candidate)) ??
      (Platform.OS === 'ios' ? 'en-US' : null);
    if (!locale) {
      return 'No offline language pack is installed. Install one from the Guardian screen.';
    }
    localeRef.current = locale;

    const permission = await recognizer.requestPermissionsAsync();
    if (!permission.granted) {
      return 'Microphone access is needed to listen for your phrase.';
    }
    return null;
  }, []);

  const stop = useCallback(() => {
    armedRef.current = false;
    if (restartTimer.current) clearTimeout(restartTimer.current);
    restartTimer.current = null;
    volumeTrail.current = [];
    setListening(false);
    useLiveMeters.getState().set({ loudness: -2, peakLoudness: -2 });
    try {
      // `abort`, not `stop`: `stop` asks for a final result, which emits one more
      // transcript after the user has said to stop listening.
      getRecognizer()?.abort();
    } catch {
      // Already stopped.
    }
  }, []);

  // -----------------------------------------------------------------------
  // Arm / disarm, driven by the store
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!armed) {
      stop();
      setUnavailable(null);
      return;
    }

    // Release the microphone while an SOS is in flight.
    //
    // Not just a matter of politeness: the SOS flow records a video **with
    // audio**, and on Android two things cannot hold the microphone at once. A
    // shake-triggered SOS does not touch the voice guard, so without this the
    // recogniser kept the mic open while `recordAsync` tried to take it — and
    // the camera failed with "Video recording failed", which says nothing about
    // the cause.
    //
    // `armed` stays true throughout, so when `paused` clears this effect runs
    // again and listening resumes by itself.
    if (paused) {
      stop();
      return;
    }

    let cancelled = false;
    (async () => {
      const list = phrasesRef.current.length ? phrasesRef.current : await loadPhrases();
      if (cancelled) return;
      // Set from the returned list rather than relying on the sync effect: the
      // `result` handler reads this ref, and arming is the one moment where a
      // render has not necessarily happened yet.
      phrasesRef.current = list;
      if (list.length === 0) {
        setUnavailable('Add at least one hot word first — there is nothing to listen for.');
        setVoiceArmed(false);
        return;
      }
      const problem = await preflight();
      if (cancelled) return;
      if (problem) {
        setUnavailable(problem);
        // Disarmed in the store too, so the switch reflects reality rather than
        // sitting on while nothing listens.
        setVoiceArmed(false);
        return;
      }
      setUnavailable(null);
      setError(null);
      triggeredRef.current = false;
      failuresRef.current = 0;
      armedRef.current = true;
      if (startSegment()) {
        setListening(true);
      } else {
        armedRef.current = false;
        setVoiceArmed(false);
        setUnavailable('Could not start listening. Another app may be using the microphone.');
      }
    })();

    return () => {
      cancelled = true;
      stop();
    };
  }, [armed, paused, loadPhrases, preflight, setVoiceArmed, startSegment, stop]);

  // -----------------------------------------------------------------------
  // Resume after a trigger
  // -----------------------------------------------------------------------
  //
  // `triggeredRef` latches on a match so one shout cannot send three SOS alerts.
  // Nothing cleared it, so the guard stayed latched and deaf for the rest of the
  // session while the UI still showed it armed. This is the other half.
  //
  // Keyed on `paused` going false: the SOS flow owns the microphone while it
  // records, so this waits for it to finish rather than racing it.
  useEffect(() => {
    if (!armed || paused || !triggeredRef.current) return;
    const timer = setTimeout(() => {
      if (!armed || paused) return;
      triggeredRef.current = false;
      failuresRef.current = 0;
      armedRef.current = true;
      if (startSegment()) {
        setListening(true);
        setError(null);
      }
    }, RESUME_AFTER_TRIGGER_MS);
    return () => clearTimeout(timer);
  }, [armed, paused, startSegment]);

  // -----------------------------------------------------------------------
  // Native events
  // -----------------------------------------------------------------------
  //
  // One subscription set, never rebuilt — every mutable value is read from a
  // ref. Subscribed through `onRecognizerEvent`, which is a no-op when there is
  // no native module, so this is harmless in Expo Go.
  useEffect(() => {
    const unsubscribers = [
      onRecognizerEvent('volumechange', (event: { value: number }) => {
        const now = Date.now();
        const value = event.value ?? -2;
        const trail = volumeTrail.current;
        trail.push({ at: now, value });
        // Trimmed on every sample rather than on a timer: the array is the shout
        // window, and an untrimmed one would make `peak` the loudest moment
        // since arming instead of the loudest moment just now.
        while (trail.length && now - trail[0].at > SHOUT_WINDOW_MS) trail.shift();
        // Straight to the store. No provider render. See the note by the state
        // declarations above.
        useLiveMeters.getState().set({
          loudness: value,
          peakLoudness: trail.reduce((max, sample) => Math.max(max, sample.value), -2),
        });
      }),

      onRecognizerEvent('result', (event: { results?: { transcript: string }[] }) => {
        if (!armedRef.current || triggeredRef.current) return;
        const transcript = event.results?.[0]?.transcript ?? '';
        if (!transcript) return;
        setHeard(transcript);

        const matched = matchHotWord(transcript, phrasesRef.current);
        if (!matched) return;

        // THE shout gate. A hot word said at a conversational volume is somebody
        // talking about the app, not somebody in trouble — and this screen's
        // whole subject is a phrase people will say out loud while setting it up.
        const now = Date.now();
        const peak = volumeTrail.current
          .filter(sample => now - sample.at <= SHOUT_WINDOW_MS)
          .reduce((max, sample) => Math.max(max, sample.value), -2);
        if (peak < thresholdRef.current) {
          setError(
            `Heard "${matched}" but not loudly enough (${peak.toFixed(1)} of ` +
              `${thresholdRef.current.toFixed(1)}). Shout to trigger SOS.`,
          );
          return;
        }

        // Latched before anything else: a continuous session emits interim and
        // final results for one utterance, and the trigger sends an SOS.
        triggeredRef.current = true;
        stop();
        onTriggerRef.current(matched, peak);
      }),

      onRecognizerEvent('end', () => {
        if (!armedRef.current || triggeredRef.current) return;
        // The segment is over and the microphone is closed until a restart
        // succeeds. Say so, rather than leaving the UI claiming to be listening
        // through the gap -- and through a restart that never works.
        setListening(false);
        restartTimer.current = setTimeout(() => {
          if (!armedRef.current || triggeredRef.current) return;
          if (startSegment()) {
            failuresRef.current = 0;
            setListening(true);
            return;
          }
          failuresRef.current += 1;
          if (failuresRef.current >= MAX_CONSECUTIVE_FAILURES) {
            stop();
            setVoiceArmed(false);
            setUnavailable(
              'Listening stopped — the microphone is not available. Shake-to-SOS still works.',
            );
          }
        }, RESTART_DELAY_MS);
      }),

      onRecognizerEvent('error', (event: { error: string; message?: string }) => {
        if (!armedRef.current) return;
        // Nobody said anything. During an armed session that is the expected
        // state, and the `end` handler restarts — reporting it would fill the
        // screen with failures while the feature worked.
        if (event.error === 'no-speech' || event.error === 'speech-timeout') return;
        if (event.error === 'aborted') return; // our own stop

        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          stop();
          setVoiceArmed(false);
          setUnavailable('Microphone permission was withdrawn. Shake-to-SOS still works.');
          return;
        }
        setError(`Recogniser problem: ${event.message || event.error}`);
      }),
    ];

    return () => unsubscribers.forEach(unsubscribe => unsubscribe());
  }, [setVoiceArmed, startSegment, stop]);

  // Published for the Guardian screen's meters. It cannot call this hook
  // itself -- a second instance would open a second session on the same
  // microphone -- so it observes the one running inside GuardianProvider.
  useEffect(() => {
    // Loudness is absent on purpose -- the `volumechange` handler writes it
    // directly. Only the low-frequency fields go through a render.
    useLiveMeters.getState().set({ listening, heard, error, unavailable });
  }, [listening, heard, error, unavailable]);

  return { listening, heard, phrases, error, unavailable };
}
