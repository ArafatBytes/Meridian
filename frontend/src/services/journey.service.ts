/**
 * Journey Guardian, phase 1 — the journey that survives.
 *
 * Four calls, one idea: pressing `Start` writes a row on the server before the
 * app starts following, and the app asks for that row on launch. Force-stop the
 * app mid-journey and the journey is still there, because it was never in the
 * screen.
 *
 * **Nothing here watches anything.** No deadline, no check-in, no escalation --
 * those are JG2 and JG3. A journey that nobody is watching is still the thing
 * JG2 needs to exist.
 *
 * Through the backend rather than straight to Supabase, like `casework`: the
 * state machine lives there, the `journeys` table has RLS on with no policies,
 * and a client that could write it directly could start a journey against
 * another user's id -- which from JG3 onward decides whose guardian gets told
 * something.
 */
import apiService from './api.service';
import { messageOf } from './casework.service';

export type JourneyState = 'active' | 'arrived' | 'cancelled';

/** What `Start` sends. Everything comes from state the map screen already has. */
export interface JourneyStart {
  origin_latitude: number;
  origin_longitude: number;
  destination_latitude: number;
  destination_longitude: number;
  /** Whatever was in the destination field, including a POI name from a map tap. */
  destination_label: string;
  route_id?: string | null;
  route_profile: 'driving' | 'foot';
  distance_km: number;
  duration_minutes: number;
  safety_score?: number | null;
}

export interface Journey {
  journey_id: string;
  state: JourneyState;
  origin_latitude: number;
  origin_longitude: number;
  destination_latitude: number;
  destination_longitude: number;
  destination_label: string;
  route_id: string | null;
  route_profile: string;
  distance_km: number;
  duration_minutes: number;
  safety_score: number | null;
  started_at: string;
  /**
   * When the route said you would arrive, as an absolute instant. Derived
   * server-side from `started_at + duration_minutes` and never sent by this
   * client -- a deadline the client sets is a deadline the client can move, and
   * from JG2 onward that deadline is the feature.
   */
  eta_at: string;
  ended_at: string | null;
}

class JourneyService {
  /**
   * Start a journey. Any journey already open is cancelled by the server.
   *
   * That is the right behaviour rather than a conflict error: the force-stop
   * this phase exists to survive is exactly the case where an active row is
   * left behind with nobody to close it, and refusing would mean the Start
   * button stops working until the user finds the End button for a journey the
   * app is no longer showing.
   */
  async start(journey: JourneyStart): Promise<Journey> {
    try {
      const response = await apiService.post<any>('/journeys', journey);
      return response as unknown as Journey;
    } catch (error: any) {
      throw new Error(messageOf(error, 'Could not record this journey.'));
    }
  }

  /**
   * The open journey, or null. Called on launch; null is the ordinary answer.
   *
   * Swallows its errors and returns null rather than throwing. This runs on
   * every cold start, including offline ones, and a network failure here means
   * "we do not know", which looks exactly like "no journey" to the only screen
   * that asks. Throwing would put an error dialog in front of someone opening
   * the map in a basement.
   */
  async active(): Promise<Journey | null> {
    try {
      const response = await apiService.get<any>('/journeys/active');
      return (response as unknown as Journey | null) ?? null;
    } catch (error: any) {
      console.warn('Could not load the active journey:', messageOf(error, 'unknown'));
      return null;
    }
  }

  /** You got there. From JG2 onward this is also what stops the clock. */
  async arrive(journeyId: string): Promise<Journey> {
    try {
      const response = await apiService.post<any>(`/journeys/${journeyId}/arrive`);
      return response as unknown as Journey;
    } catch (error: any) {
      throw new Error(messageOf(error, 'Could not close this journey.'));
    }
  }

  /**
   * You stopped, changed your mind, or went somewhere else. Distinct from
   * `arrive`, and it has to stay distinct: ending without arriving is the shape
   * of the thing JG2 and JG3 care about.
   */
  async cancel(journeyId: string): Promise<Journey> {
    try {
      const response = await apiService.post<any>(`/journeys/${journeyId}/cancel`);
      return response as unknown as Journey;
    } catch (error: any) {
      throw new Error(messageOf(error, 'Could not end this journey.'));
    }
  }
}

export const journeyService = new JourneyService();
export default journeyService;
