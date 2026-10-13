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
  /** Object path in the private evidence bucket, from analyzeCrimeImage. D07. */
  evidence_photo_path?: string | null;
  /**
   * What D07 read out of the photo, kept verbatim.
   *
   * Stored even when the reporter overrides the suggested category -- that is
   * the case most worth being able to look back at, because it is the record of
   * the machine being wrong and a human catching it.
   */
  vision_analysis?: Record<string, any> | null;
}

/** One of `yes` / `no` / `unclear`, per cue. `unclear` is a real answer, not a failure. */
export type Cue = 'yes' | 'no' | 'unclear';

export interface CrimeCues {
  physical_confrontation: Cue;
  weapon_visible: Cue;
  property_damage: Cue;
  /** Widened past building openings on 2026-10-10: a vehicle or a lock counts. */
  forced_entry: Cue;
  unwanted_pursuit: Cue;
  /** Two people pulling the same bag. They need not be touching each other. */
  struggle_over_property: Cue;
  /** Goods going into a bag or pocket in a shop. */
  goods_concealed: Cue;
}

/**
 * What D07 read out of a report photo. See docs/adr/0006-d07-vision-pipeline.md.
 *
 * The model answers the five cues; the backend's own code proposes a category
 * from them; the reporter confirms it. So `proposed_category` is a suggestion
 * and nothing more -- it is null whenever no cue came back a definite `yes`,
 * which is the normal result for a benign photo.
 *
 * `confidence` is three bands, not a percentage. The old pipeline printed
 * figures like 0.73 that came out of weights nobody had validated, and a judge
 * asking what 73% means deserves an answer.
 */
export interface CrimeAnalysisResult {
  success: boolean;
  /** Which tier answered: `gemini` (live), `replay` (rehearsed), `ollama` (offline). Shown on the card. */
  engine?: 'gemini' | 'replay' | 'ollama' | 'none';
  elapsed_seconds?: number;
  /** One plain sentence of what is visibly happening. The part we stand behind. */
  description?: string;
  people_count?: number;
  scene?: 'street' | 'indoor' | 'vehicle' | 'other';
  cues?: CrimeCues;
  /** The cue names that came back `yes`. Empty when the photo shows nothing specific. */
  cues_fired?: string[];
  /** A suggestion for the category field. Null means "propose nothing". */
  proposed_category?: string | null;
  confidence?: 'strong' | 'weak' | 'none';
  /** Why that category, in words, e.g. "a weapon is visible and people are in forceful contact". */
  reason?: string;
  /** Does what the reporter wrote line up with the photo? `silent` is the common answer. */
  agreement?: 'agrees' | 'disagrees' | 'silent';
  /** Categories a photograph cannot establish at all. Only `fraud` now. */
  unreachable_from_photo?: string[];
  /** Object path in the private evidence bucket, to save on the report row. */
  evidence_photo_path?: string | null;
  image_sha256?: string;
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
            // 'filed', not 'pending'. There is nothing to be pending ON: no queue,
            // no approver, no way for this product to establish that an incident
            // happened. The report is the author's own record from the moment it is
            // written, and what reaches a stranger's map is corroboration across
            // several independent reports -- see types/contracts/community.ts.
            //
            // `verified: false` used to be written here too. The column is gone
            // (B13): the client no longer has UPDATE privilege on `status` either, so
            // the three lines that used to be able to self-award a tick now fail at
            // the database rather than being merely unused.
            status: 'filed',
            created_at: reportData.created_at, // Override Supabase auto timestamp
            evidence_photo_path: reportData.evidence_photo_path ?? null,
            vision_analysis: reportData.vision_analysis ?? null,
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
   * Retract one of your own reports.
   *
   * An RPC rather than an update, because the client deliberately has no UPDATE
   * privilege on `crime_reports.status` -- that column-level revoke is what closed
   * the hole where any account could set `verified = true` on its own row.
   * `public.withdraw_crime_report` is `security definer`, sets exactly one column to
   * exactly one value, and only on a row the caller owns that is still `filed`.
   *
   * Withdrawal rather than deletion, and the difference matters once a report has
   * contributed to a published cluster: `delete` would remove the audit trail behind
   * a claim that is still on other people's maps, while this leaves the row and stops
   * it counting on the corroboration agent's next run. `deleteReport` is still there
   * for a report the author simply wants gone.
   *
   * Returns false when the report is not yours, does not exist, or has already been
   * withdrawn or removed. All three are legitimate states, not errors.
   */
  async withdrawReport(reportId: string): Promise<boolean> {
    try {
      const { data, error } = await supabase.rpc('withdraw_crime_report', {
        p_report_id: reportId,
      });
      if (error) throw error;
      return data === true;
    } catch (error: any) {
      throw new Error(error.message || 'Failed to withdraw this report');
    }
  }

  /**
   * Read the visible cues out of a report photo.
   *
   * `reportText` is optional and only feeds the corroboration cross-check --
   * whether what the reporter wrote lines up with what the photo showed.
   *
   * The 60s timeout is sized for the slowest tier, not the fastest: with the
   * network down the local model takes about 9s on a photo it has not seen,
   * plus the upload, and a cold model load adds ~5s more on top of that.
   */
  async analyzeCrimeImage(
    imageUri: string,
    reportText?: string,
  ): Promise<CrimeAnalysisResult> {
    try {
      const formData = new FormData();

      const fileName = imageUri.split('/').pop() || 'report_photo.jpg';
      const fileType = fileName.split('.').pop()?.toLowerCase() || 'jpg';
      const mimeType = fileType === 'png' ? 'image/png' : 'image/jpeg';

      formData.append('file', {
        uri: imageUri,
        name: fileName,
        type: mimeType,
      } as any);

      if (reportText && reportText.trim()) {
        formData.append('report_text', reportText.trim());
      }

      const response = await apiService.post<any>(
        '/ai/crime-detection/analyze',
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000,
        },
      );

      // The endpoint answers 200 either way. `success: false` means every tier
      // was unavailable -- not "nothing was found", which is a successful
      // result with proposed_category null.
      if (!response.success) {
        return {
          success: false,
          engine: 'none',
          proposed_category: null,
          message: response.message || 'Could not analyse this photo.',
        };
      }

      return { success: true, ...response.data };
    } catch (error: any) {
      const message =
        error.message ||
        error.response?.data?.detail ||
        'Could not analyse this photo. It can still be attached to your report.';
      console.log('Photo analysis unavailable:', message);
      return {
        success: false,
        engine: 'none',
        proposed_category: null,
        message,
      };
    }
  }

  /**
   * A short-lived URL for a stored evidence photo, or null.
   *
   * The evidence bucket is private, so there is no permanent link: the backend
   * signs one per request. Null means the photo is gone or storage is
   * unreachable, and the screen says "photo unavailable" rather than showing a
   * broken image.
   */
  async getEvidencePhotoUrl(path: string): Promise<string | null> {
    try {
      const response = await apiService.get<any>(
        `/ai/crime-detection/evidence-url?path=${encodeURIComponent(path)}`,
      );
      return response?.data?.url ?? null;
    } catch (error: any) {
      console.log('Evidence photo unavailable:', error.message);
      return null;
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
