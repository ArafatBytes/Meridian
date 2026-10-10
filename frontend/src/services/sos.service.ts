/**
 * Reading back the SOS audit trail. D09, demo beat 9.
 *
 * Sending an SOS does not go through here: that is `features/sos/useSOS`, which
 * uses XHR because it is the one request in the app that needs real upload
 * progress. This file is only the history, which is an ordinary GET.
 */
import apiService from './api.service';

export interface SosHistoryEntry {
  id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  status: string;
  voice_activated: boolean;
  /**
   * Whether the alert left the system. `null` on rows written before the audit
   * blob existed — shown as "not recorded" rather than guessed in either
   * direction, because "delivered: no" on an alert that did go out would be a
   * worse lie than admitting we do not know.
   */
  delivered: boolean | null;
  recipient_count: number;
  police_station_count: number;
  video_attached: boolean;
}

export interface SosHistoryResponse {
  count: number;
  incidents: SosHistoryEntry[];
}

export const sosService = {
  /** This user's own past alerts, newest first. Scoped server-side. */
  async getHistory(): Promise<SosHistoryResponse> {
    // The cast is the house pattern, not laziness: `apiService.get` is typed as
    // returning `ApiResponse<T>`, but its interceptor unwraps the body before
    // returning, so the declared type and the runtime value disagree. Every
    // caller in `casework.service` does the same thing. Reconciling that
    // signature with reality is a change to a shared file every screen uses, and
    // it belongs in B3's service de-barrelling rather than in D09.
    const response = await apiService.get<any>('/sos/history');
    return response as unknown as SosHistoryResponse;
  },
};

export default sosService;
