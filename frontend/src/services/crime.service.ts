import { supabase } from '../lib/supabase';
import apiService from './api.service';

export interface CrimeReportData {
  category: string;
  title: string;
  description: string;
  incident_date_time: string; // ISO string
  latitude: string;
  longitude: string;
  location_name?: string;
  created_at?: string; // ISO string - manual timestamp
}

export interface CrimeAnalysisResult {
  success: boolean;
  crime_type?: string;
  confidence?: number;
  title?: string;
  description?: string;
  severity?: string;
  details?: {
    detected_objects: string[];
    person_count: number;
    total_detections: number;
    matched_objects: string[];
  };
  pose_analysis?: {
    poses_detected: number;
    actions: string[];
    threat_levels: string[];
    interaction?: {
      interaction_type: string;
      risk_level: string;
      proximity: string;
      involving_high_threat?: boolean;
    };
  };
  scene_analysis?: {
    scene_type: string;
    scene_confidence: number;
    lighting_condition: string;
    lighting_confidence: number;
    crowd_density: string;
    crowd_confidence: number;
    risk_level: string;
    time_of_day: string;
    isolation_level: string;
  };
  decision_engine?: string; // Phase 4: "ml_fusion_v1" or "rule_based"
  fusion_signals?: {
    // Phase 4: Signal breakdown
    object_score: number;
    pose_score: number;
    scene_score: number;
    weighted_score: number;
    signals_used: number;
    weights_applied: {
      [key: string]: number;
    };
  };
  processing_time?: number;
  model_version?: string;
  message?: string;
}

class CrimeService {
  async submitReport(reportData: CrimeReportData): Promise<any> {
    try {
      // Get current user
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        throw new Error('User not authenticated');
      }

      // Insert crime report
      const { data, error } = await supabase
        .from('crime_reports')
        .insert([
          {
            user_id: user.id,
            category: reportData.category,
            title: reportData.title,
            description: reportData.description,
            incident_date_time: reportData.incident_date_time,
            latitude: reportData.latitude,
            longitude: reportData.longitude,
            location_name: reportData.location_name,
            status: 'pending',
            verified: false,
            created_at: reportData.created_at, // Override Supabase auto timestamp
          },
        ])
        .select()
        .single();

      if (error) {
        throw error;
      }

      return data;
    } catch (error: any) {
      throw new Error(
        error.message || 'Failed to submit crime report. Please try again.',
      );
    }
  }

  async getUserReports(userId: string): Promise<any[]> {
    try {
      const { data, error } = await supabase
        .from('crime_reports')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false });

      if (error) {
        throw error;
      }

      return data || [];
    } catch (error: any) {
      throw new Error(error.message || 'Failed to fetch reports');
    }
  }

  async getReportById(reportId: string): Promise<any> {
    try {
      const { data, error } = await supabase
        .from('crime_reports')
        .select('*')
        .eq('id', reportId)
        .single();

      if (error) {
        throw error;
      }

      return data;
    } catch (error: any) {
      throw new Error(error.message || 'Failed to fetch report details');
    }
  }

  async deleteReport(reportId: string): Promise<void> {
    try {
      const { error } = await supabase
        .from('crime_reports')
        .delete()
        .eq('id', reportId);

      if (error) {
        throw error;
      }
    } catch (error: any) {
      throw new Error(error.message || 'Failed to delete report');
    }
  }

  /**
   * Analyze crime image using AI to auto-detect crime type and generate report content.
   * @param imageUri - Local URI of the image to analyze
   * @param confidenceThreshold - Minimum confidence threshold (0.0-1.0)
   * @returns Analysis result with crime type, title, description, and confidence
   */
  async analyzeCrimeImage(
    imageUri: string,
    confidenceThreshold: number = 0.25,
  ): Promise<CrimeAnalysisResult> {
    try {
      // Create form data
      const formData = new FormData();

      // Extract file name from URI
      const fileName = imageUri.split('/').pop() || 'crime_image.jpg';
      const fileType = fileName.split('.').pop()?.toLowerCase() || 'jpg';
      const mimeType = fileType === 'png' ? 'image/png' : 'image/jpeg';

      // Add image file
      formData.append('file', {
        uri: imageUri,
        name: fileName,
        type: mimeType,
      } as any);

      // Make API request
      // apiService returns a shaped response; keep 'any' here to avoid strict typing errors
      const response = await apiService.post<any>(
        `/ai/crime-detection/analyze?confidence_threshold=${confidenceThreshold}`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          timeout: 30000, // 30 seconds for AI processing
        },
      );

      if (response.success && response.data) {
        return {
          success: true,
          crime_type: response.data.crime_type,
          confidence: response.data.confidence,
          title: response.data.title,
          description: response.data.description,
          severity: response.data.severity,
          details: response.data.details,
          pose_analysis: response.data.pose_analysis, // Phase 2: Include pose data
          scene_analysis: response.data.scene_analysis, // Phase 3: Include scene data
          decision_engine: response.data.decision_engine, // Phase 4: Include decision engine
          fusion_signals: response.data.fusion_signals, // Phase 4: Include fusion signals
          processing_time: response.data.processing_time,
          model_version: response.data.model_version,
        };
      } else {
        // No crime detected but returned as 200 response
        return {
          success: false,
          message: response.message || 'Analysis failed',
          // Include detected_objects and analysis data even when no crime detected
          details: response.data?.detected_objects
            ? {
                detected_objects: response.data.detected_objects,
                person_count: 0,
                total_detections: response.data.detected_objects.length,
                matched_objects: [],
              }
            : undefined,
          pose_analysis: response.data?.pose_analysis,
          scene_analysis: response.data?.scene_analysis,
          processing_time: response.data?.processing_time,
        };
      }
    } catch (error: any) {
      // Extract error message and status code
      const errorMessage =
        error.message || // ApiError or general error
        error.response?.data?.message || // Raw axios error
        'Failed to analyze image. Please try again.';

      const statusCode = error.statusCode || error.response?.status;

      // Check if this is a 400 "no crime detected" response (not a real error)
      const isNoCrimeDetected =
        statusCode === 400 &&
        (errorMessage.toLowerCase().includes('no crime') ||
          errorMessage.toLowerCase().includes('crime indicators') ||
          errorMessage.toLowerCase().includes('validation_failed') ||
          errorMessage.toLowerCase().includes('no relevant objects') ||
          errorMessage.toLowerCase() === 'validation failed');

      // Only log actual errors, not "no crime detected" scenarios
      if (!isNoCrimeDetected) {
        console.error('Crime image analysis error:', error);
      } else {
        console.log('No crime detected in image:', errorMessage);
      }

      // Extract data from error response (for 400 "no crime detected" scenarios)
      const errorData = error.response?.data?.data || {};

      return {
        success: false,
        message: errorMessage,
        // Include detected_objects and analysis data even when no crime detected
        details: errorData.detected_objects
          ? {
              detected_objects: errorData.detected_objects,
              person_count: 0,
              total_detections: errorData.detected_objects.length,
              matched_objects: [],
            }
          : undefined,
        pose_analysis: errorData.pose_analysis,
        scene_analysis: errorData.scene_analysis,
        processing_time: errorData.processing_time,
      };
    }
  }

  /**
   * Check if crime detection AI is available.
   * @returns Status of AI models
   */
  async checkCrimeDetectionStatus(): Promise<{
    available: boolean;
    model_name?: string;
    status?: string;
  }> {
    try {
      const response = await apiService.get<any>('/ai/crime-detection/status');

      if (response && response.data) {
        return {
          available: response.data?.loaded ?? false,
          model_name: response.data?.model_name,
          status: response.data?.status,
        };
      }

      return { available: false };
    } catch (error) {
      console.error('Error checking crime detection status:', error);
      return { available: false };
    }
  }
}

export const crimeService = new CrimeService();
