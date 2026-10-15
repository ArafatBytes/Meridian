/**
 * Journey Guardian — the journey that survives (JG1), and its clock (JG2).
 *
 * Pressing `Start` writes a row on the server before the app starts following,
 * and the app asks for that row on launch. Force-stop the app mid-journey and
 * the journey is still there, because it was never in the screen.
 *
 * JG2 adds two calls and one idea: the server holds a deadline, and asks once
 * when it passes. `heartbeat` is the only thing that moves that deadline without
 * a person pressing anything, and `checkIn` is the answer.
 *
 * **Nothing here tells anybody else anything.** No guardian, no contact, no
 * message leaving the account -- that is JG3.
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

/**
 * How worried the server is. JG2 has two; JG3 adds the rest of the chain.
 *
 * A second axis, not more values on `JourneyState`: a journey being asked a
 * question is still `active`.
 */
export type EscalationState = 'normal' | 'check_in_sent';

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

  /**
   * Minutes from now. Omitted means "the route's own ETA plus the grace
   * period", which is what the default chip on the planner sends.
   *
   * The server clamps this and computes the instant from its own clock -- what
   * the person chooses is how long they are giving themselves, not where that
   * lands.
   */
  deadline_minutes?: number | null;
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

  // ---- JG2 -------------------------------------------------------------

  /** When the server expects you. Moved only by a heartbeat or an answer. */
  deadline_at: string;

  escalation_state: EscalationState;

  /**
   * When the current question was asked, when it was answered, and when the
   * sweep observed it go unanswered.
   *
   * `answered_at` is history, not state: it survives the return to `normal`, so
   * a journey asked twice carries an answer that is about the first question.
   * Compare it against `check_in_sent_at` rather than reading it alone.
   */
  check_in_sent_at: string | null;
  answered_at: string | null;
  unanswered_at: string | null;

  last_heartbeat_at: string | null;
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

  /**
   * "Still going, about this long left." JG2.
   *
   * Returns null instead of throwing, and the caller ignores the result. This
   * fires on a timer while somebody is walking, on a phone that is by definition
   * moving between cells -- a failed heartbeat is the ordinary case, not an
   * error, and the correct response to one is to send the next one a minute
   * later. Surfacing it would put a dialog in front of someone mid-journey to
   * tell them about a request they never made.
   *
   * The consequence of a dropped heartbeat is exactly the designed one: the
   * deadline does not move. Silence never buys an extension, and a phone that
   * cannot reach the server is indistinguishable from one that is not trying.
   */
  async heartbeat(journeyId: string, remainingSeconds: number): Promise<Journey | null> {
    try {
      const response = await apiService.post<any>(`/journeys/${journeyId}/heartbeat`, {
        remaining_seconds: Math.max(0, Math.round(remainingSeconds)),
      });
      return response as unknown as Journey;
    } catch {
      return null;
    }
  }

  /**
   * "I'm fine." The one tap. JG2.
   *
   * Throws, unlike `heartbeat`: this one is a person pressing a button and
   * expecting something to happen, and a silent failure would leave them
   * believing they had answered a question that is still outstanding. The
   * caller decides whether there is a screen to say so on -- the lock-screen
   * handler has none and logs instead.
   */
  async checkIn(journeyId: string): Promise<Journey> {
    try {
      const response = await apiService.post<any>(`/journeys/${journeyId}/check-in`);
      return response as unknown as Journey;
    } catch (error: any) {
      throw new Error(messageOf(error, 'Could not send your check-in.'));
    }
  }
}

export const journeyService = new JourneyService();
export default journeyService;
