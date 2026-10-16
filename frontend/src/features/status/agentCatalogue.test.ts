import {
  AGENT_CATALOGUE,
  STATE_LABELS,
  describeAge,
  describeAgent,
  describeCadence,
} from './agentCatalogue';

/**
 * B9's catalogue: agent keys turned into words, and the honesty rules on top.
 *
 * The screen itself has no test — this suite tests logic, not render trees, and
 * everything on that screen that could be wrong in a way that matters is in
 * here: which words a state maps to, how an age reads, and what happens to a
 * key this build has never seen.
 */

describe('every catalogue entry', () => {
  it('has a title and a blurb', () => {
    for (const [key, entry] of Object.entries(AGENT_CATALOGUE)) {
      expect(entry.title.length).toBeGreaterThan(0);
      expect(entry.blurb.length).toBeGreaterThan(0);
      // A blurb that is one word is a title restated, which tells the user
      // nothing they could not read from the heading.
      expect(entry.blurb.split(' ').length).toBeGreaterThan(4);
      expect(key).toMatch(/^[a-z_]+$/);
    }
  });

  it('covers every agent the backend registers', () => {
    // Kept in step from the other side too: `backend/tests/test_agent_health.py`
    // asserts every registered agent has a cadence this app can describe, and
    // the catalogue coverage check lives there because only the backend knows
    // the real list. This is the client-side half of the same pair.
    //
    // `journey_watch` joined the list when JG2 landed, and this test is how the
    // app found out: the backend half failed first, naming the missing key.
    expect(Object.keys(AGENT_CATALOGUE).sort()).toEqual([
      'alert_dispatch',
      'expiry_sweep',
      'journey_watch',
      'live_risk',
      'report_corroboration',
      'scheduled_risk',
    ]);
  });

  it('marks exactly the parts a user would notice', () => {
    /**
     * `expiry_sweep` is the one that must stay `false`, and it is the reason
     * this field exists. Its own docstring: *"the sweep does not decide what is
     * live; every surface stops serving a row the moment it passes
     * `expires_at`, whether or not this has ever run."* So a red card there does
     * not mean stale warnings are on the map, and telling a user it does would
     * frighten them about the wrong thing.
     */
    expect(AGENT_CATALOGUE.expiry_sweep.affectsWhatYouSee).toBe(false);
    for (const key of ['live_risk', 'scheduled_risk', 'report_corroboration', 'alert_dispatch']) {
      expect(AGENT_CATALOGUE[key].affectsWhatYouSee).toBe(true);
    }
  });
});

describe('an agent this build has never heard of', () => {
  it('gets a readable title rather than a blank card', () => {
    expect(describeAgent('weather_watch').title).toBe('Weather Watch');
  });

  it('gets no invented claim about what it does', () => {
    const unknown = describeAgent('weather_watch');
    expect(unknown.blurb).toMatch(/no description/i);
    // Never claim a part the app knows nothing about changes the user's map.
    expect(unknown.affectsWhatYouSee).toBe(false);
  });

  it('does not fall over on a degenerate key', () => {
    expect(() => describeAgent('')).not.toThrow();
    expect(() => describeAgent('__')).not.toThrow();
  });
});

describe('the state labels', () => {
  it('never call a late agent working', () => {
    /**
     * The discipline the whole feature rests on. `health.py` refuses to report a
     * stale success as healthy; collapsing amber into green here to make the
     * page look calm would undo that server-side honesty in one line of
     * presentation.
     */
    expect(STATE_LABELS.late.text).not.toMatch(/working/i);
    expect(STATE_LABELS.late.tone).toBe('warn');
  });

  it('give each of the five states its own words', () => {
    const texts = Object.values(STATE_LABELS).map((label) => label.text);
    expect(new Set(texts).size).toBe(texts.length);
    expect(texts).toHaveLength(5);
  });

  it('reserve the healthy tone for the healthy state', () => {
    const healthy = Object.entries(STATE_LABELS).filter(([, label]) => label.tone === 'ok');
    expect(healthy.map(([state]) => state)).toEqual(['working']);
  });
});

describe('describeAge', () => {
  it.each([
    [null, 'never run'],
    [0, 'just now'],
    [45, 'just now'],
    [60, '1 minute ago'],
    [240, '4 minutes ago'],
    [3600, '1 hour ago'],
    [50400, '14 hours ago'],
    [172800, '2 days ago'],
  ])('reads %p as %p', (seconds, expected) => {
    expect(describeAge(seconds as number | null)).toBe(expected);
  });

  it('never renders a negative age as the future', () => {
    /**
     * A handset clock ahead of the server's is ordinary, which is exactly why
     * `AgentHealth.secondsSinceLastRun` is measured on the server and carried
     * across. This clamp is the second line of defence: "updated in 20 minutes"
     * on a status page destroys confidence in everything else on it.
     */
    expect(describeAge(-1200)).toBe('just now');
  });
});

describe('describeCadence', () => {
  it.each([
    [null, null],
    [0, null],
    [-5, null],
    [60, 'every minute'],
    [900, 'every 15 minutes'],
    [1800, 'every 30 minutes'],
    [3600, 'every hour'],
    [21600, 'every 6 hours'],
    [86400, 'once a day'],
  ])('reads %p as %p', (seconds, expected) => {
    expect(describeCadence(seconds as number | null)).toBe(expected);
  });
});
