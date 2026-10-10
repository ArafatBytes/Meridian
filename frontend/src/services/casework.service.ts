/**
 * D08 — the General Diary. ADR 0007.
 *
 * Meridian drafts a GD application; a person files it. There is no submit call
 * in here and there is not going to be one: Bangladesh Police has no API, and a
 * cognizable offence cannot be closed online in any case — the applicant has to
 * appear at the thana. So the chain ends at a document the user prints, or a
 * paragraph they paste into the police's own app.
 *
 * Drafts go through the backend rather than straight to Supabase, unlike
 * reports. The state machine lives there, and it should be one place.
 */
import apiService from './api.service';

export type GdState = 'draft' | 'ready_to_file';

export interface GdProfile {
  /** On the form and on the signature line, so the user writes it themselves. */
  full_name: string | null;
  phone: string | null;
  gd_nid: string | null;
  gd_father_name: string | null;
  gd_mother_name: string | null;
  gd_permanent_address: string | null;
  gd_present_address: string | null;
  /** From the login, shown on the form but not editable here. */
  email: string | null;
  is_complete: boolean;
  missing_fields: string[];
}

export interface GdDraft {
  id: string;
  report_id: string;
  state: GdState;
  narrative_bn: string;
  /**
   * sha256 of `narrative_bn`, handed back on approve. This is the review gate:
   * the server only accepts a hash of text it actually sent, and only while
   * that is still what it holds. Approving something you were never shown, or
   * something that has since changed, fails at the server with no help from
   * this screen.
   */
  narrative_sha256: string;
  summary_en: string;
  missing_details: string[];
  thana_name: string;
  thana_district: string;
  engine: string;
  approved_at: string | null;
  gd_number: string | null;
  gd_filed_at: string | null;
  created_at: string;
}

/** Where else this report can go. Real national numbers; nothing from the CSV. */
export interface Channel {
  label: string;
  number: string;
  reason: string;
}

const EMERGENCY: Channel = {
  label: 'National Emergency Service',
  number: '999',
  reason: 'If it is happening now, or anyone is hurt',
};

const CHANNELS_BY_CATEGORY: Record<string, Channel[]> = {
  harassment: [
    EMERGENCY,
    {
      label: 'Violence against women and children',
      number: '109',
      reason: 'The national helpline',
    },
    {
      label: 'Police Cyber Support for Women',
      number: '01320-000888',
      reason: 'If any of it happened online',
    },
  ],
  fraud: [
    {
      label: 'CID Cyber Police Centre',
      number: '01320010148',
      reason: 'Online fraud and cybercrime',
    },
    EMERGENCY,
  ],
};

const DEFAULT_CHANNELS: Channel[] = [
  EMERGENCY,
  {
    label: 'Online GD help line',
    number: '01320001428',
    reason: 'If the police app will not let you register or submit',
  },
];

export function channelsFor(category: string): Channel[] {
  return CHANNELS_BY_CATEGORY[category] ?? DEFAULT_CHANNELS;
}

/**
 * The status, wherever it ended up.
 *
 * `api.service` normalises every axios failure into `{message, statusCode}`,
 * so `error.response.status` does not survive the interceptor. Reading only
 * that meant a 404 from "this report has no draft yet" — the normal state of
 * every report — was treated as a real failure and alerted on.
 */
export function statusOf(error: any): number | undefined {
  return error?.statusCode ?? error?.response?.status;
}

export function messageOf(error: any, fallback: string): string {
  return error?.message || error?.response?.data?.detail || fallback;
}

class CaseworkService {
  async getProfile(): Promise<GdProfile> {
    const response = await apiService.get<any>('/casework/profile');
    return response as unknown as GdProfile;
  }

  async saveProfile(profile: Partial<GdProfile>): Promise<GdProfile> {
    const response = await apiService.put<any>('/casework/profile', {
      full_name: profile.full_name ?? null,
      phone: profile.phone ?? null,
      gd_nid: profile.gd_nid ?? null,
      gd_father_name: profile.gd_father_name ?? null,
      gd_mother_name: profile.gd_mother_name ?? null,
      gd_permanent_address: profile.gd_permanent_address ?? null,
      gd_present_address: profile.gd_present_address ?? null,
    });
    return response as unknown as GdProfile;
  }

  /** The existing draft for a report, or null when none has been generated. */
  async getDraft(reportId: string): Promise<GdDraft | null> {
    try {
      const response = await apiService.get<any>(
        `/casework/reports/${reportId}/draft`,
      );
      return response as unknown as GdDraft;
    } catch (error: any) {
      // No draft yet is the ordinary case, not an error.
      if (statusOf(error) === 404) {
        return null;
      }
      throw new Error(messageOf(error, 'Could not load the General Diary draft.'));
    }
  }

  /** One LLM call. ~2s on the cloud tier; allow for a slow network. */
  async generateDraft(reportId: string): Promise<GdDraft> {
    try {
      const response = await apiService.post<any>(
        `/casework/reports/${reportId}/draft`,
        undefined,
        { timeout: 60000 },
      );
      return response as unknown as GdDraft;
    } catch (error: any) {
      throw new Error(
        messageOf(
          error,
          'Could not write the General Diary right now. Nothing was saved — try again when you have a connection.',
        ),
      );
    }
  }

  async editDraft(
    draftId: string,
    changes: { narrative_bn?: string; thana_name?: string; thana_district?: string },
  ): Promise<GdDraft> {
    try {
      const response = await apiService.patch<any>(
        `/casework/drafts/${draftId}`,
        changes,
      );
      return response as unknown as GdDraft;
    } catch (error: any) {
      throw new Error(messageOf(error, 'Could not save your changes.'));
    }
  }

  /**
   * Approve the exact text that was on screen. The hash comes from the draft
   * this screen was given — it is not computed here, because a hash this screen
   * computed would prove nothing about what the server holds.
   */
  async approve(draftId: string, narrativeSha256: string): Promise<GdDraft> {
    try {
      const response = await apiService.post<any>(
        `/casework/drafts/${draftId}/approve`,
        { narrative_sha256: narrativeSha256 },
      );
      return response as unknown as GdDraft;
    } catch (error: any) {
      throw new Error(
        messageOf(error, 'Could not approve this General Diary. Reload and try again.'),
      );
    }
  }

  /** What the duty officer wrote on the copy he handed back. */
  async recordGdNumber(draftId: string, gdNumber: string): Promise<GdDraft> {
    try {
      const response = await apiService.post<any>(
        `/casework/drafts/${draftId}/gd-number`,
        { gd_number: gdNumber },
      );
      return response as unknown as GdDraft;
    } catch (error: any) {
      throw new Error(messageOf(error, 'Could not save the GD number.'));
    }
  }

  async listThanas(): Promise<string[]> {
    try {
      const response = await apiService.get<any>('/casework/thanas');
      return (response as unknown as string[]) ?? [];
    } catch {
      return [];
    }
  }
}

export const caseworkService = new CaseworkService();
export default caseworkService;
