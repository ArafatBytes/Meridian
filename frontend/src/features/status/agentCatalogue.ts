import type { AgentState } from '../../services/agents.service';

/**
 * Agent keys turned into words, for the System Status screen. B9.
 *
 * Every description here was written from the agent's own module docstring, not
 * from its name. `expiry_sweep` is the one that proves why that matters: the
 * name suggests the map depends on it, and its docstring says the opposite —
 * *"the sweep does not decide what is live; every surface stops serving a row
 * the moment it passes `expires_at`, whether or not this has ever run."* So a
 * red card there does **not** mean stale warnings are on your map, and the
 * description says so. Guessing from the name would have produced a plausible
 * sentence that frightens the user about the wrong thing.
 *
 * `affectsWhatYouSee` is the field that makes this screen worth having rather
 * than merely honest: it separates "this being broken changes your map" from
 * "this being broken is our problem, not yours".
 */

export interface AgentDescription {
  title: string;
  /** One sentence, present tense, about what the user gets from it. */
  blurb: string;
  /**
   * Does a failure here change what the user sees or receives?
   *
   * `false` means the app is still correct while this agent is down — which is
   * the more reassuring and the more surprising answer, so it is the one that
   * has to be stated rather than implied.
   */
  affectsWhatYouSee: boolean;
}

export const AGENT_CATALOGUE: Readonly<Record<string, AgentDescription>> = {
  live_risk: {
    title: "Today's news",
    blurb:
      'Reads Dhaka news sites and puts incidents reported today onto your map as zone warnings.',
    affectsWhatYouSee: true,
  },
  scheduled_risk: {
    title: "Tomorrow's map",
    blurb:
      'Finds processions, strikes and roadworks announced for a future date, so the warning is on your map before the day arrives.',
    affectsWhatYouSee: true,
  },
  report_corroboration: {
    title: 'Community reports',
    blurb:
      'Groups reports from different people about the same place, so two independent accounts count for more than one.',
    affectsWhatYouSee: true,
  },
  alert_dispatch: {
    title: 'Zone alerts to your phone',
    blurb: 'Sends the notification when you are approaching an area that has a live warning.',
    affectsWhatYouSee: true,
  },
  expiry_sweep: {
    title: 'Tidying up finished warnings',
    blurb:
      'Files away warnings whose time has passed. Your map already stops showing them on its own, so nothing is out of date while this is behind.',
    affectsWhatYouSee: false,
  },
  journey_watch: {
    title: 'Watching your journeys',
    // Written from `agents/journey_watch.py`, and `affectsWhatYouSee` is `true`
    // for a reason worth stating: this is the only agent whose failure is
    // silent *by design*. Nothing on the map changes, no error is shown, and
    // the journey screen still says "on your way" — because the question it
    // asks is asked by this sweep and nothing else. A person who picked a
    // guardian believes somebody is watching, and while this is down, nobody
    // is. That is the single most important red card on this screen.
    blurb:
      'Asks if you are okay when a journey deadline passes, and emails the person you chose if you do not answer. While this is down, nothing asks and nobody is told.',
    affectsWhatYouSee: true,
  },
};

/**
 * A description for any key, including one this build has never heard of.
 *
 * The fallback exists because the server decides which agents there are. A new
 * agent added to the backend reaches an older app as an unknown key, and the
 * honest degradation is a readable title with no claim attached — not a blank
 * card, and not a confident sentence this file invented.
 *
 * `backend/tests/test_agent_health.py` asserts that every registered agent has
 * an entry here, so an agent added alongside a frontend release fails a test
 * rather than silently falling through to this.
 */
export function describeAgent(key: string): AgentDescription {
  const known = AGENT_CATALOGUE[key];
  if (known) {
    return known;
  }
  return {
    title: key
      .split('_')
      .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
      .join(' '),
    blurb: 'A newer part of the system. This version of the app has no description for it yet.',
    affectsWhatYouSee: false,
  };
}

export interface StateLabel {
  text: string;
  /** `ok` | `warn` | `bad` | `idle` — the screen maps these onto theme colours. */
  tone: 'ok' | 'warn' | 'bad' | 'idle';
}

/**
 * The five server states in the user's words.
 *
 * `late` is "Running behind" and not "Working", which is the whole discipline of
 * this screen: the backend refuses to call a stale success healthy, and it would
 * be undone here by collapsing amber into green to make the page look calm.
 */
export const STATE_LABELS: Readonly<Record<AgentState, StateLabel>> = {
  working: { text: 'Working', tone: 'ok' },
  late: { text: 'Running behind', tone: 'warn' },
  problem: { text: 'Not working', tone: 'bad' },
  never_run: { text: 'Not started yet', tone: 'idle' },
  unknown: { text: 'Unknown', tone: 'idle' },
};

/**
 * "4 minutes ago", from the age the **server** measured.
 *
 * Takes seconds rather than a `Date` so the handset clock never enters the
 * calculation — see `AgentHealth.secondsSinceLastRun`. A phone twenty minutes
 * out would otherwise report a fresh run as twenty minutes old, or produce a
 * negative age and render "in 20 minutes".
 */
export function describeAge(seconds: number | null): string {
  if (seconds === null) {
    return 'never run';
  }
  const safe = Math.max(0, Math.round(seconds));
  if (safe < 60) {
    return 'just now';
  }
  const minutes = Math.round(safe / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  }
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

/** "every 15 minutes", for the line under the age. */
export function describeCadence(seconds: number | null): string | null {
  if (seconds === null || seconds <= 0) {
    return null;
  }
  if (seconds < 3600) {
    const minutes = Math.round(seconds / 60);
    return minutes <= 1 ? 'every minute' : `every ${minutes} minutes`;
  }
  if (seconds < 86400) {
    const hours = Math.round(seconds / 3600);
    return hours <= 1 ? 'every hour' : `every ${hours} hours`;
  }
  return 'once a day';
}
