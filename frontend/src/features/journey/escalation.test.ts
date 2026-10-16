/**
 * The ladder, in words. JG3.
 *
 * Four things, in rising order of how badly they fail:
 *
 * 1. **The ladder itself**, checked against the backend's own list. The two
 *    drifting apart is not hypothetical: the server grew five states while this
 *    app, and the server's own check-in endpoint, both went on testing
 *    `=== 'check_in_sent'`. That bug took the answer button away from the one
 *    person pressing it hardest and let the escalation run on regardless.
 * 2. **`journeyStatus`**, which is what somebody reads at the worst moment of
 *    this feature. A sentence that promises more than the product does -- or
 *    that implies the police are coming -- is worse than no screen at all.
 * 3. **`journeyTimeline`**, which must show only what the row records.
 * 4. **The wiring**, as source greps: the `useNavigation.test.ts` idiom, for the
 *    reason given there. No React Testing Library in this project, and these are
 *    rules about a screen rather than behaviour of a function.
 */

import fs from 'fs';
import path from 'path';

import { isAwaitingAnswer } from './deadline';
import {
  ESCALATION_LADDER,
  clockTime,
  guardianLine,
  journeyStatus,
  journeyTimeline,
} from './escalation';
import type { EscalationState, Journey } from '../../services/journey.service';

/** A journey, with only the fields a test cares about spelled out. */
const journeyOf = (over: Partial<Journey> = {}): Journey =>
  ({
    journey_id: 'j1',
    state: 'active',
    origin_latitude: 23.75,
    origin_longitude: 90.39,
    destination_latitude: 23.8,
    destination_longitude: 90.4,
    destination_label: 'Mirpur',
    route_id: null,
    route_profile: 'foot',
    distance_km: 2,
    duration_minutes: 20,
    safety_score: null,
    started_at: '2026-10-15T14:00:00Z',
    eta_at: '2026-10-15T14:20:00Z',
    ended_at: null,
    deadline_at: '2026-10-15T14:30:00Z',
    escalation_state: 'normal',
    check_in_sent_at: null,
    answered_at: null,
    unanswered_at: null,
    last_heartbeat_at: null,
    check_in_repeated_at: null,
    contacts_notified_at: null,
    full_sos_at: null,
    guardian_contact_id: null,
    guardian_name: null,
    started_notice_at: null,
    arrived_notice_at: null,
    ...over,
  }) as Journey;

const withGuardian = (over: Partial<Journey> = {}) =>
  journeyOf({ guardian_contact_id: 'c1', guardian_name: 'Ammu', ...over });

describe('the ladder', () => {
  it('is the backend ladder, state for state', () => {
    // The one test in this file that reaches outside the app. It is here
    // because neither suite can see the other's list, and the cost of them
    // disagreeing was measured today: three of the five states were
    // unanswerable on the server and invisible to this app.
    const model = fs.readFileSync(
      path.join(__dirname, '../../../../backend/app/models/journey.py'),
      'utf8',
    );
    const block = model.slice(
      model.indexOf('ESCALATION_STATES = ('),
      model.indexOf(')', model.indexOf('ESCALATION_STATES = (')),
    );
    const states = [...block.matchAll(/ESCALATION_([A-Z_]+),/g)].map(m =>
      m[1].toLowerCase(),
    );
    expect(states.length).toBeGreaterThan(1);
    // `normal` is not a rung -- it is the absence of one -- so the ladder is
    // everything after it, in the server's own order.
    expect(ESCALATION_LADDER).toEqual(states.slice(1));
  });

  it('counts every rung as a question still outstanding', () => {
    for (const state of ESCALATION_LADDER) {
      expect(isAwaitingAnswer(journeyOf({ escalation_state: state }))).toBe(true);
    }
  });

  it('includes the last rung, where answering is all that is left to do', () => {
    // `full_sos` is terminal for the escalation, not for the person. The server
    // accepts an answer from it, so the app has to offer one.
    expect(isAwaitingAnswer(journeyOf({ escalation_state: 'full_sos' }))).toBe(true);
  });

  it('asks nothing of a journey in normal, or of one that has ended', () => {
    expect(isAwaitingAnswer(journeyOf({ escalation_state: 'normal' }))).toBe(false);
    expect(
      isAwaitingAnswer(journeyOf({ state: 'arrived', escalation_state: 'check_in_sent' })),
    ).toBe(false);
  });
});

describe('journeyStatus', () => {
  it('says what state the journey is in, in one line per rung', () => {
    const headlines = ESCALATION_LADDER.map(
      state => journeyStatus(withGuardian({ escalation_state: state })).headline,
    );
    // Four rungs, four distinct sentences. A screen that said the same thing at
    // "we asked you" and at "we emailed everybody you know" would be the one
    // part of this feature a person could not act on.
    expect(new Set(headlines).size).toBe(ESCALATION_LADDER.length);
    headlines.forEach(line => expect(line.length).toBeGreaterThan(0));
  });

  it('names the guardian once they have been emailed', () => {
    const status = journeyStatus(withGuardian({ escalation_state: 'contacts_notified' }));
    expect(status.headline).toContain('Ammu');
  });

  it('never claims anybody was told about a journey with no guardian', () => {
    for (const state of ['normal', ...ESCALATION_LADDER] as EscalationState[]) {
      const status = journeyStatus(journeyOf({ escalation_state: state }));
      const text = `${status.headline} ${status.detail ?? ''}`;
      expect(text).not.toMatch(/was emailed|has been emailed/);
    }
  });

  it('says so plainly when nobody is being told', () => {
    const status = journeyStatus(journeyOf({ escalation_state: 'normal' }));
    expect(status.detail).toMatch(/[Nn]obody/);
  });

  it('does not imply the police are involved at any rung', () => {
    // The most damaging false impression this screen could leave. 999 and the
    // thana are JG7; somebody who believes help is already coming because of a
    // sentence on this page has been actively misled.
    for (const state of ['normal', ...ESCALATION_LADDER] as EscalationState[]) {
      const status = journeyStatus(withGuardian({ escalation_state: state }));
      const text = `${status.headline} ${status.detail ?? ''}`.toLowerCase();
      expect(text).not.toContain('police');
      expect(text).not.toContain('999');
      expect(text).not.toContain('thana');
      expect(text).not.toContain('help is');
    }
  });

  it('does not tell somebody who cancelled that their guardian was told', () => {
    // Cancelling emails nobody, by design -- "she stopped the journey" is not
    // news, and sending it would teach people to ignore these messages. So the
    // screen must not say it happened.
    const status = journeyStatus(withGuardian({ state: 'cancelled' }));
    expect(`${status.headline} ${status.detail ?? ''}`).not.toContain('Ammu');
  });

  it('gets louder as the ladder climbs', () => {
    expect(journeyStatus(withGuardian()).tone).toBe('calm');
    expect(journeyStatus(withGuardian({ escalation_state: 'check_in_sent' })).tone).toBe(
      'waiting',
    );
    expect(
      journeyStatus(withGuardian({ escalation_state: 'contacts_notified' })).tone,
    ).toBe('alarm');
    expect(journeyStatus(withGuardian({ escalation_state: 'full_sos' })).tone).toBe(
      'alarm',
    );
  });
});

describe('guardianLine', () => {
  it('names the person, for the one line on the card', () => {
    expect(guardianLine(withGuardian())).toBe('Telling Ammu');
  });

  it('says nothing at all when nobody is being told', () => {
    expect(guardianLine(journeyOf())).toBeNull();
  });

  it('still says something when the contact has been deleted', () => {
    // The foreign key is `on delete set null`, but this app can be holding a
    // journey it read before that happened. "Telling" with a blank after it
    // would be worse than a generic word.
    expect(guardianLine({ guardian_contact_id: 'c1', guardian_name: null })).toBe(
      'Telling your guardian',
    );
    expect(guardianLine({ guardian_contact_id: 'c1', guardian_name: '  ' })).toBe(
      'Telling your guardian',
    );
  });
});

describe('journeyTimeline', () => {
  it('shows only what the row records', () => {
    // A fresh journey has one timestamp, so it gets one line. An empty-ish
    // history is the honest rendering of a journey where nothing has happened.
    expect(journeyTimeline(journeyOf()).map(e => e.label)).toEqual([
      'Journey started',
    ]);
  });

  it('puts everything in the order it happened', () => {
    const timeline = journeyTimeline(
      withGuardian({
        started_at: '2026-10-15T14:00:00Z',
        started_notice_at: '2026-10-15T14:01:00Z',
        check_in_sent_at: '2026-10-15T14:30:00Z',
        unanswered_at: '2026-10-15T14:40:00Z',
        check_in_repeated_at: '2026-10-15T14:41:00Z',
        contacts_notified_at: '2026-10-15T14:52:00Z',
        escalation_state: 'contacts_notified',
      }),
    );
    expect(timeline.map(e => e.at)).toEqual([
      '2026-10-15T14:00:00Z',
      '2026-10-15T14:01:00Z',
      '2026-10-15T14:30:00Z',
      '2026-10-15T14:40:00Z',
      '2026-10-15T14:41:00Z',
      '2026-10-15T14:52:00Z',
    ]);
    expect(timeline[timeline.length - 1].label).toContain('Ammu');
  });

  it('places an answer in time rather than matching it to a question', () => {
    // `answered_at` survives the return to `normal`, so on a journey asked
    // twice it belongs to the first question. A timeline is the one place where
    // showing it where it happened is exactly right.
    const timeline = journeyTimeline(
      journeyOf({
        check_in_sent_at: '2026-10-15T15:00:00Z',
        answered_at: '2026-10-15T14:35:00Z',
        escalation_state: 'check_in_sent',
      }),
    );
    expect(timeline.map(e => e.label)).toEqual([
      'Journey started',
      'You said you were fine',
      'Meridian asked if you were okay',
    ]);
  });

  it('invents no entry for a deadline passing', () => {
    // Nothing stamps it. The sweep runs once a minute, so for up to a minute a
    // passed deadline has had no consequence at all -- and a history that
    // listed it would be describing something that may not have happened.
    const timeline = journeyTimeline(
      journeyOf({ deadline_at: '2026-10-15T14:05:00Z' }),
    );
    expect(timeline).toHaveLength(1);
  });

  it('drops what it cannot read instead of rendering Invalid Date', () => {
    const timeline = journeyTimeline(journeyOf({ started_notice_at: 'not a time' }));
    expect(timeline.map(e => e.label)).toEqual(['Journey started']);
  });

  it('calls the end what it was', () => {
    const arrived = journeyTimeline(
      journeyOf({ state: 'arrived', ended_at: '2026-10-15T14:18:00Z' }),
    );
    expect(arrived[arrived.length - 1].label).toBe('You arrived');
    const stopped = journeyTimeline(
      journeyOf({ state: 'cancelled', ended_at: '2026-10-15T14:18:00Z' }),
    );
    expect(stopped[stopped.length - 1].label).toBe('Journey ended');
  });
});

describe('clockTime', () => {
  it('renders a wall-clock time', () => {
    expect(clockTime(new Date(2026, 9, 15, 20, 45).toISOString())).toBe('8:45 PM');
  });

  it('renders nothing for what it cannot use', () => {
    expect(clockTime(null)).toBe('');
    expect(clockTime('tomorrow-ish')).toBe('');
  });
});

describe('the wiring', () => {
  const read = (file: string) => fs.readFileSync(path.join(__dirname, file), 'utf8');

  it('defaults the guardian picker to nobody', () => {
    const mapScreen = fs.readFileSync(
      path.join(__dirname, '../../screens/Map/MapScreen.tsx'),
      'utf8',
    );
    expect(mapScreen).toContain('useState<string | null>(null)');
    // And forgets the choice when route mode is left. A guardian inherited by
    // the next trip is an email somebody did not mean to send.
    expect(mapScreen).toContain('setGuardianId(null)');
  });

  it('sends no position for a journey nobody is watching', () => {
    const hook = read('useJourney.ts');
    // The rule at the point of collection: the fix is dropped here, before the
    // request exists, not filtered server-side afterwards.
    expect(hook).toMatch(/guardian_contact_id\s*\?\s*position/);
  });

  it('leaves the position out of the request body entirely when there is none', () => {
    const service = fs.readFileSync(
      path.join(__dirname, '../../services/journey.service.ts'),
      'utf8',
    );
    // Spread of a conditional object rather than `latitude: null`: the server's
    // field is optional, and sending an explicit null on every heartbeat of
    // every guardianless journey is a wire that claims to have looked.
    expect(service).toMatch(/\.\.\.\(position/);
  });

  it('answers through the same hook the card uses', () => {
    const screen = fs.readFileSync(
      path.join(__dirname, '../../screens/Map/JourneyScreen.tsx'),
      'utf8',
    );
    expect(screen).toContain('journey.checkIn()');
    // One definition of "a question is outstanding", shared with the card.
    expect(screen).toContain('isAwaitingAnswer(open)');
  });
});
