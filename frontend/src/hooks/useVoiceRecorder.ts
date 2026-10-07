/**
 * Microphone recording, as a hook.
 *
 * Replaces the recording half of `speech.service.ts`, which used `expo-av`'s
 * imperative `Audio.Recording` API inside a singleton class. SDK 57 removes
 * `expo-av`, and `expo-audio`'s supported entry point is the `useAudioRecorder`
 * hook: `AudioRecorder` is exported from the package root as a *type only*
 * (`export type * from './AudioModule.types'`), and its runtime constructor
 * lives on `NativeAudioModule`, which is marked `@hidden`. Reaching for that
 * would mean depending on a private API.
 *
 * The split that fell out of this is better than what was there: recording is
 * bound to a component's lifecycle, so it belongs in a hook, while
 * transcription is a stateless network call, so it stays in the service. The
 * old service held mutable recording state in a module-level singleton, which
 * meant two screens recording at once would have silently fought over it.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

/** Matches the backend's SPEECH_MAX_DURATION_SECONDS. */
export const MAX_RECORDING_SECONDS = 30;

export interface VoiceRecorder {
  /** True while audio is being captured. */
  isRecording: boolean;
  /** Elapsed seconds, for a live counter in the UI. */
  durationSeconds: number;
  /** Request permission and begin. Throws if permission is denied. */
  start: () => Promise<void>;
  /** Stop and resolve the recorded file's URI, or null if nothing was captured. */
  stop: () => Promise<string | null>;
  /** Stop and discard. Safe to call when not recording. */
  cancel: () => Promise<void>;
}

export function useVoiceRecorder(): VoiceRecorder {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  // Polls the native recorder; this is what drives the live duration counter.
  const state = useAudioRecorderState(recorder);
  const [isStarting, setIsStarting] = useState(false);

  // `recorder.uri` is cleared once a new recording is prepared, so capture it
  // at stop time rather than reading it later.
  const lastUri = useRef<string | null>(null);

  const start = useCallback(async () => {
    const { granted } = await requestRecordingPermissionsAsync();
    if (!granted) {
      throw new Error(
        'Microphone permission is required for voice input. Enable it in Settings.',
      );
    }

    // Without allowsRecording the iOS session stays in playback mode and
    // capture silently produces an empty file.
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });

    setIsStarting(true);
    try {
      await recorder.prepareToRecordAsync();
      recorder.record();
      lastUri.current = null;
    } finally {
      setIsStarting(false);
    }
  }, [recorder]);

  const stop = useCallback(async (): Promise<string | null> => {
    if (!state.isRecording) return null;
    await recorder.stop();
    lastUri.current = recorder.uri ?? null;
    // Release the audio session so other audio is not ducked afterwards.
    await setAudioModeAsync({ allowsRecording: false });
    return lastUri.current;
  }, [recorder, state.isRecording]);

  const cancel = useCallback(async () => {
    if (!state.isRecording) return;
    try {
      await recorder.stop();
    } catch {
      // Already stopped, or the session was reset by the system. Either way
      // there is nothing to clean up and nothing useful to report.
    }
    lastUri.current = null;
    await setAudioModeAsync({ allowsRecording: false });
  }, [recorder, state.isRecording]);

  // Hard stop at the cap. The old implementation drove this from a setInterval
  // that it stashed on the function object (`startVoiceInput.intervalId`) and
  // never reliably cleared, so a recording could outlive the screen.
  useEffect(() => {
    if (state.isRecording && state.durationMillis >= MAX_RECORDING_SECONDS * 1000) {
      void recorder.stop();
    }
  }, [state.isRecording, state.durationMillis, recorder]);

  // Never leave the microphone open when the screen goes away.
  useEffect(() => {
    return () => {
      if (recorder.isRecording) {
        void recorder.stop();
      }
      void setAudioModeAsync({ allowsRecording: false });
    };
  }, [recorder]);

  return {
    isRecording: state.isRecording || isStarting,
    durationSeconds: Math.floor(state.durationMillis / 1000),
    start,
    stop,
    cancel,
  };
}
