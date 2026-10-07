/**
 * Speech-to-text transcription.
 *
 * Recording used to live here too, built on `expo-av`'s imperative
 * `Audio.Recording` API with mutable state held in a module-level singleton.
 * SDK 57 removed `expo-av`, and `expo-audio` only exposes recording through the
 * `useAudioRecorder` hook, so capture moved to `src/hooks/useVoiceRecorder.ts`.
 *
 * That turned out to be the right boundary anyway: recording is tied to a
 * component's lifecycle, transcription is a stateless network call. The old
 * singleton meant two screens recording at once would have silently clobbered
 * each other's `this.recording`.
 *
 * Also removed: `recordAndTranscribe()`, which started a recording and then
 * returned `null` unconditionally with a comment explaining that the UI was
 * meant to handle the rest. It could not work, and nothing called it.
 */
import * as FileSystem from 'expo-file-system';
import apiService from './api.service';
import { ApiResponse } from '../types';

export interface TranscriptionResult {
  text: string;
  confidence: number;
  language: string;
  word_count: number;
}

export interface TranscribeOptions {
  /** BCP-47 tag. The backend supports bn-BD for Bangla. */
  language?: string;
}

/** Backend cap (ai.py rejects larger uploads). */
const MAX_AUDIO_BYTES = 10 * 1024 * 1024;

class SpeechService {
  /**
   * Upload a recorded audio file and return its transcription.
   *
   * @param audioUri Local file URI, from `useVoiceRecorder().stop()`.
   */
  async transcribeAudio(
    audioUri: string,
    options: TranscribeOptions = {},
  ): Promise<TranscriptionResult> {
    const { language = 'en-US' } = options;

    const info = await FileSystem.getInfoAsync(audioUri);
    if (!info.exists) {
      throw new Error('Recording file is missing.');
    }
    if (info.size === 0) {
      // Usually means the audio session was never put into recording mode.
      throw new Error('Recording is empty. Check microphone permissions.');
    }
    if (info.size > MAX_AUDIO_BYTES) {
      throw new Error(
        `Recording is ${(info.size / 1024 / 1024).toFixed(1)} MB. Maximum is 10 MB.`,
      );
    }

    const filename = audioUri.split('/').pop() || 'recording.m4a';
    const extension = /\.(\w+)$/.exec(filename)?.[1] ?? 'm4a';

    const formData = new FormData();
    formData.append('audio', {
      uri: audioUri,
      name: filename,
      type: `audio/${extension}`,
    } as never);
    formData.append('language', language);

    const response: ApiResponse<TranscriptionResult> =
      await apiService.uploadFile('/ai/speech-to-text', formData);

    if (!response.success || !response.data) {
      throw new Error(response.message || 'Transcription failed.');
    }
    return response.data;
  }

  /** Languages the backend will accept, with a local fallback if it is down. */
  async getSupportedLanguages(): Promise<{ code: string; name: string }[]> {
    try {
      const response =
        await apiService.get<{ code: string; name: string }[]>('/ai/supported-languages');
      if (response.success && response.data) return response.data;
    } catch {
      // Fall through to the defaults below.
    }
    return [
      { code: 'en-US', name: 'English (US)' },
      { code: 'bn-BD', name: 'Bengali (Bangladesh)' },
      { code: 'hi-IN', name: 'Hindi (India)' },
    ];
  }

  /**
   * Whether the backend's speech pipeline is usable.
   *
   * NOTE: this currently reports availability of the Google Cloud client, and
   * the backend's `_convert_audio_format` is still broken for some formats.
   * Treat a true here as "the endpoint exists", not "transcription works".
   */
  async checkServiceHealth(): Promise<boolean> {
    try {
      const response = await apiService.get('/ai/health');
      return response.success;
    } catch {
      return false;
    }
  }
}

export default new SpeechService();
