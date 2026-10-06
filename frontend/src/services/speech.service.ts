import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import apiService from './api.service';
import { ApiResponse } from '../types';

export interface TranscriptionResult {
  text: string;
  confidence: number;
  language: string;
  word_count: number;
}

export interface SpeechRecognitionOptions {
  language?: string;
  maxDurationSeconds?: number;
}

class SpeechService {
  private recording: Audio.Recording | null = null;
  private isRecording = false;

  /**
   * Request audio recording permissions
   */
  async requestPermissions(): Promise<boolean> {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      return status === 'granted';
    } catch (error) {
      console.error('Error requesting audio permissions:', error);
      return false;
    }
  }

  /**
   * Start recording audio
   */
  async startRecording(): Promise<void> {
    try {
      if (this.isRecording) {
        console.warn('Recording already in progress');
        return;
      }

      // Request permissions
      const hasPermission = await this.requestPermissions();
      if (!hasPermission) {
        throw new Error('Audio recording permission not granted');
      }

      // Configure audio mode
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // Create and start recording
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
      );

      this.recording = recording;
      this.isRecording = true;
      console.log('Recording started');
    } catch (error) {
      console.error('Failed to start recording:', error);
      throw error;
    }
  }

  /**
   * Stop recording and return the audio file URI
   */
  async stopRecording(): Promise<string | null> {
    try {
      if (!this.recording || !this.isRecording) {
        console.warn('No recording in progress');
        return null;
      }

      await this.recording.stopAndUnloadAsync();
      const uri = this.recording.getURI();

      this.recording = null;
      this.isRecording = false;

      console.log('Recording stopped, URI:', uri);
      return uri;
    } catch (error) {
      console.error('Failed to stop recording:', error);
      throw error;
    }
  }

  /**
   * Cancel recording without saving
   */
  async cancelRecording(): Promise<void> {
    try {
      if (this.recording && this.isRecording) {
        await this.recording.stopAndUnloadAsync();
        this.recording = null;
        this.isRecording = false;
        console.log('Recording cancelled');
      }
    } catch (error) {
      console.error('Failed to cancel recording:', error);
      throw error;
    }
  }

  /**
   * Get recording status
   */
  getIsRecording(): boolean {
    return this.isRecording;
  }

  /**
   * Get recording duration in milliseconds
   */
  async getRecordingDuration(): Promise<number> {
    if (!this.recording) {
      return 0;
    }

    try {
      const status = await this.recording.getStatusAsync();
      return status.durationMillis || 0;
    } catch (error) {
      console.error('Failed to get recording duration:', error);
      return 0;
    }
  }

  /**
   * Transcribe audio file using backend API
   */
  async transcribeAudio(
    audioUri: string,
    options: SpeechRecognitionOptions = {},
  ): Promise<TranscriptionResult> {
    try {
      const { language = 'en-US', maxDurationSeconds = 30 } = options;

      // Get file info
      const fileInfo = await FileSystem.getInfoAsync(audioUri);
      if (!fileInfo.exists) {
        throw new Error('Audio file does not exist');
      }

      // Check file size (max 10MB)
      const maxSizeBytes = 10 * 1024 * 1024;
      if (fileInfo.size && fileInfo.size > maxSizeBytes) {
        throw new Error('Audio file is too large (max 10MB)');
      }

      // Create FormData
      const formData = new FormData();

      // Add audio file
      const filename = audioUri.split('/').pop() || 'recording.m4a';
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `audio/${match[1]}` : 'audio/m4a';

      formData.append('audio', {
        uri: audioUri,
        name: filename,
        type: type,
      } as any);

      // Add language
      formData.append('language', language);

      // Send to backend
      console.log('Sending audio to backend for transcription...');
      const response: ApiResponse<TranscriptionResult> =
        await apiService.uploadFile('/ai/speech-to-text', formData);

      if (!response.success || !response.data) {
        throw new Error(response.message || 'Transcription failed');
      }

      console.log('Transcription successful:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('Transcription error:', error);
      throw new Error(
        error.message || 'Failed to transcribe audio. Please try again.',
      );
    }
  }

  /**
   * Record and transcribe in one step
   */
  async recordAndTranscribe(
    options: SpeechRecognitionOptions = {},
  ): Promise<TranscriptionResult | null> {
    let audioUri: string | null = null;

    try {
      // Start recording
      await this.startRecording();

      // Wait for user to stop (this should be controlled by UI)
      // For now, we'll just return null and let the UI handle the flow
      return null;
    } catch (error) {
      console.error('Record and transcribe error:', error);
      if (audioUri) {
        // Clean up the temporary file
        await FileSystem.deleteAsync(audioUri, { idempotent: true });
      }
      throw error;
    }
  }

  /**
   * Get list of supported languages from backend
   */
  async getSupportedLanguages(): Promise<
    Array<{ code: string; name: string }>
  > {
    try {
      const response = await apiService.get<
        Array<{ code: string; name: string }>
      >('/ai/supported-languages');

      if (!response.success || !response.data) {
        throw new Error('Failed to fetch supported languages');
      }

      return response.data;
    } catch (error) {
      console.error('Error fetching supported languages:', error);
      // Return default languages if API fails
      return [
        { code: 'en-US', name: 'English (US)' },
        { code: 'bn-BD', name: 'Bengali (Bangladesh)' },
        { code: 'hi-IN', name: 'Hindi (India)' },
      ];
    }
  }

  /**
   * Check if speech service is available
   */
  async checkServiceHealth(): Promise<boolean> {
    try {
      const response = await apiService.get('/ai/health');
      return response.success;
    } catch (error) {
      console.error('Speech service health check failed:', error);
      return false;
    }
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    if (this.isRecording) {
      await this.cancelRecording();
    }
  }
}

export default new SpeechService();
