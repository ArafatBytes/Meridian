import apiService from './api.service';

/**
 * Fleet status: is each of the agents behind the map actually running. B9.
 *
 * The server does the judging. Whether an agent is `late` depends on its cron
 * cadence and a grace window, and that arithmetic lives in
 * `backend/app/agents/health.py` — the same function that feeds
 * `python -m app.agents status`, so the operator's view and this screen can
 * never disagree about whether something is healthy.
 *
 * This file carries the answer across and nothing else, for the same reason
 * `risk.service.ts` does no decay arithmetic: one implementation, and a phone is
 * not the place for it.
 *
 * **What the endpoint deliberately does not send:** error text, item counts and
 * failure tallies. They are in the CLI, where the reader can act on them. See
 * `AgentHealthReport` in `backend/app/contracts/agents.py` for the reasoning on
 * each one — it is not an oversight to be helpfully filled in later.
 */

/** The five states `health.py` can report. Mirrors `AgentHealthState`. */
export type AgentState = 'working' | 'late' | 'problem' | 'never_run' | 'unknown';

/** Wire shape — snake_case, as the endpoint sends it. */
interface AgentHealthWire {
  agent: string;
  state: AgentState;
  last_run_at: string | null;
  seconds_since_last_run: number | null;
  cadence_seconds: number | null;
  runs_last_24h: number;
}

interface FleetStatusWire {
  mode: 'live' | 'replay';
  checked_at: string;
  agents: AgentHealthWire[];
}

export interface AgentHealth {
  /** The agent's internal key, e.g. `live_risk`. The catalogue turns it into words. */
  agent: string;
  state: AgentState;
  lastRunAt: Date | null;
  /**
   * Age of the last run, **as the server measured it**.
   *
   * Carried across rather than derived from `lastRunAt` on the device, because a
   * handset whose clock is twenty minutes out would otherwise render "updated 20
   * minutes ago" for a run that just finished — or a negative age, which is how
   * a status screen ends up saying something impossible.
   */
  secondsSinceLastRun: number | null;
  cadenceSeconds: number | null;
  runsLast24h: number;
}

export interface FleetStatus {
  /**
   * `replay` is the offline demo (`RISK_SURFACE_IMPL=seeded`): no schedules, no
   * run history, and `agents` is empty. The screen says so rather than showing
   * five agents as never-started, which would read as five things broken.
   */
  mode: 'live' | 'replay';
  checkedAt: Date;
  agents: AgentHealth[];
}

function toAgentHealth(wire: AgentHealthWire): AgentHealth {
  return {
    agent: wire.agent,
    state: wire.state,
    lastRunAt: wire.last_run_at ? new Date(wire.last_run_at) : null,
    secondsSinceLastRun: wire.seconds_since_last_run ?? null,
    cadenceSeconds: wire.cadence_seconds ?? null,
    runsLast24h: wire.runs_last_24h ?? 0,
  };
}

class AgentsService {
  /**
   * Fetch fleet status. Throws on failure, unlike `geo.service.ts`.
   *
   * The difference is what the caller can do about it. An unresolved place still
   * lets the map draw nothing sensible; a status screen that cannot reach the
   * server has exactly one honest thing to show, which is that it could not
   * reach the server. Swallowing the error here would make that indistinguishable
   * from "all five agents are fine", which is the one claim this feature must
   * never make by accident.
   */
  async status(): Promise<FleetStatus> {
    // `apiService.get` declares ApiResponse<T> but hands back the body verbatim,
    // and this endpoint returns an unwrapped object. Same double cast as
    // risk.service.ts and geo.service.ts, and said out loud for the same reason.
    const body = (await apiService.get<FleetStatusWire>('/agents/status')) as unknown as
      | FleetStatusWire
      | { data?: FleetStatusWire };

    const payload: FleetStatusWire | undefined =
      body && 'agents' in body ? (body as FleetStatusWire) : (body as { data?: FleetStatusWire })?.data;

    if (!payload) {
      throw new Error('fleet status response had no body');
    }

    return {
      mode: payload.mode === 'replay' ? 'replay' : 'live',
      checkedAt: payload.checked_at ? new Date(payload.checked_at) : new Date(),
      agents: (payload.agents ?? []).map(toAgentHealth),
    };
  }
}

export const agentsService = new AgentsService();
export default agentsService;
