/**
 * The deadline, the chips, and the one tap. JG2.
 *
 * Three things are checked here, in rising order of how badly they fail:
 *
 * 1. `deadlineLabel`, which is arithmetic over a clock and is the kind of thing
 *    that is wrong by an hour for six months before anybody notices.
 * 2. `isCheckInAnswer`, which decides whether a notification response counts as
 *    somebody saying they are fine. Too strict and the obvious gesture does
 *    nothing; too loose and dismissing a notification tells the server you are
 *    safe.
 * 3. The MapScreen wiring, as source greps -- the `useNavigation.test.ts` idiom,
 *    for the reason given there: no React Testing Library in this project, and
 *    these are sequencing rules in a screen rather than behaviour of a function.
 */

import fs from 'fs';
import path from 'path';

import {
  DEADLINE_CHOICES,
  HEARTBEAT_INTERVAL_MS,
  MIN_CHOICE_MINUTES,
  SERVER_GRACE_MINUTES,
  deadlineLabel,
  isAwaitingAnswer,
} from './deadline';
import { CHECK_IN_ACTION_OK, CHECK_IN_TYPE, isCheckInAnswer } from './checkIn';

// A fixed instant so the expected clock times are readable rather than derived.
// 2026-10-15T14:00:00 local.
const NOW = new Date(2026, 9, 15, 14, 0, 0).getTime();

const label = (minutes: number | null, durationMinutes = 18) =>
  deadlineLabel({
    now: NOW,
    minutes,
    durationMinutes,
    graceMinutes: SERVER_GRACE_MINUTES,
  });

describe('deadlineLabel', () => {
  it('adds the server grace period to the route ETA for the default', () => {
    // 14:00 + 18 min of route + 10 min of grace.
    expect(label(null, 18)).toBe('2:28 PM');
  });

  it('takes a chosen offset as given, ignoring the route', () => {
    // The whole point of choosing: the router's opinion stops mattering.
    expect(label(30, 18)).toBe('2:30 PM');
    expect(label(2, 180)).toBe('2:02 PM');
  });

  it('crosses the hour correctly', () => {
    expect(label(60, 0)).toBe('3:00 PM');
    expect(label(75, 0)).toBe('3:15 PM');
  });

  it('renders nothing rather than "Invalid Date" for input it cannot use', () => {
    // A row reading `Invalid Date` looks broken; one reading nothing looks
    // absent, and the server picks a sane default either way.
    expect(label(null, Number.NaN)).toBe('');
    expect(deadlineLabel({ now: Number.NaN, minutes: 5, durationMinutes: 1, graceMinutes: 10 }))
      .toBe('');
  });
});

describe('DEADLINE_CHOICES', () => {
  it('offers the route ETA first, and offers it as the server default', () => {
    // `null`, not a number computed here. The route's ETA plus the grace period
    // is the server's sum, and a copy of that sum on the client would be a
    // second definition free to drift from the first.
    expect(DEADLINE_CHOICES[0].minutes).toBeNull();
  });

  it('never offers something the server will silently clamp', () => {
    // An offer the system quietly ignores is worse than no offer: the person
    // believes they set something they did not.
    for (const choice of DEADLINE_CHOICES) {
      if (choice.minutes === null) continue;
      expect(choice.minutes).toBeGreaterThanOrEqual(MIN_CHOICE_MINUTES);
    }
  });

  it('includes a short leash', () => {
    // Two minutes is what makes this phase demonstrable without waiting out a
    // real journey, and it is also JOURNEY_GUARDIAN.md §6's short leash arriving
    // early. If it goes, the walkthrough stops being runnable.
    expect(DEADLINE_CHOICES.some(c => c.minutes === MIN_CHOICE_MINUTES)).toBe(true);
  });

  it('fits four across a phone', () => {
    expect(DEADLINE_CHOICES).toHaveLength(4);
    for (const choice of DEADLINE_CHOICES) {
      expect(choice.label.length).toBeLessThanOrEqual(10);
    }
  });
});

describe('isAwaitingAnswer', () => {
  it('is true only while an active journey has a question outstanding', () => {
    expect(isAwaitingAnswer({ state: 'active', escalation_state: 'check_in_sent' })).toBe(true);
    expect(isAwaitingAnswer({ state: 'active', escalation_state: 'normal' })).toBe(false);
  });

  it('is false for a journey that has ended, whatever it was asked', () => {
    // A journey can arrive between the sweep asking and the person answering.
    // Showing "Are you there yet?" on a trip that finished is the feature
    // looking broken at the exact moment it worked.
    expect(isAwaitingAnswer({ state: 'arrived', escalation_state: 'check_in_sent' })).toBe(false);
    expect(isAwaitingAnswer({ state: 'cancelled', escalation_state: 'check_in_sent' })).toBe(false);
  });
});

describe('isCheckInAnswer', () => {
  it('accepts the button', () => {
    expect(isCheckInAnswer({ actionIdentifier: CHECK_IN_ACTION_OK, type: CHECK_IN_TYPE })).toBe(
      true,
    );
  });

  it('accepts a tap on the notification itself', () => {
    // A person who taps the notification rather than the button has answered as
    // plainly as one who pressed it. Treating that as no answer would make the
    // most obvious gesture on the screen the one that does nothing.
    expect(
      isCheckInAnswer({ actionIdentifier: 'expo.modules.notifications.actions.DEFAULT', type: CHECK_IN_TYPE }),
    ).toBe(true);
  });

  it('ignores a response to anything that is not a check-in', () => {
    // The risk-alert path uses the same listener. A road alert tapped on a lock
    // screen must never be recorded as "I am fine" on a journey.
    expect(isCheckInAnswer({ actionIdentifier: CHECK_IN_ACTION_OK, type: 'risk_alert' })).toBe(
      false,
    );
    expect(isCheckInAnswer({ type: undefined })).toBe(false);
  });
});

describe('MapScreen wires the clock the way JG2 requires', () => {
  const mapScreen = fs.readFileSync(
    path.join(__dirname, '..', '..', 'screens', 'Map', 'MapScreen.tsx'),
    'utf8',
  );

  it('reports in only while actually following', () => {
    // A journey resumed to the route card but not started is one the person is
    // not walking. Reporting progress for it would be the app vouching for
    // somebody standing still -- and vouching is exactly what a heartbeat does,
    // since it is the only thing that extends a deadline without a button press.
    const effect = mapScreen.indexOf('journey.heartbeat(left)');
    expect(effect).toBeGreaterThan(-1);
    const guard = mapScreen.lastIndexOf('if (!follow.active || !journey.journey) return;', effect);
    expect(guard).toBeGreaterThan(-1);
  });

  it('reports on an interval rather than on every GPS fix', () => {
    expect(mapScreen).toContain('setInterval(beat, HEARTBEAT_INTERVAL_MS)');
    // One minute, matching the sweep that reads the result.
    expect(HEARTBEAT_INTERVAL_MS).toBe(60_000);
  });

  it('sends the chosen deadline, and sends null for the default', () => {
    expect(mapScreen).toContain(
      'deadline_minutes: DEADLINE_CHOICES[deadlineChoice].minutes,',
    );
  });

  it('forgets a short leash when route mode is left', () => {
    // A two-minute deadline chosen for one trip is a setting about that journey,
    // not a preference about the person. Inheriting it silently would mean the
    // next trip across town gets asked about after two minutes.
    const exit = mapScreen.indexOf('setSourceLocation(null);');
    expect(exit).toBeGreaterThan(-1);
    expect(mapScreen.slice(exit, exit + 400)).toContain('setDeadlineChoice(0)');
  });

  it('can be answered from the card as well as from the lock screen', () => {
    // The notification is the half of this feature most likely to be missing on
    // a given handset -- a denied permission, Expo Go, a dead token. A safety
    // question with one way to answer it is one permission dialog away from
    // being unanswerable.
    expect(mapScreen).toContain('journey.checkIn()');
    expect(mapScreen).toContain('Are you there yet?');
  });

  it('shows the deadline on the card, not a countdown', () => {
    // An instant stays true while nobody is looking; a duration does not, and
    // nothing in this app is maintaining one.
    expect(mapScreen).toContain('startedAtLabel(journey.journey.deadline_at)');
    expect(mapScreen).toContain('check in by ');
  });
});

describe('answering twice is not a failure', () => {
  // Found on a device. The person tapped the notification, which woke the app
  // and posted the answer; the card rendered from state older than that round
  // trip and was still offering the button; they pressed it; the endpoint
  // refused the second answer with a 409 because `escalation_state` was no
  // longer `check_in_sent`; and the screen told them their check-in had not
  // been recorded. It had been, 30 seconds earlier.
  const hook = fs.readFileSync(path.join(__dirname, 'useJourney.ts'), 'utf8');
  const mapScreen = fs.readFileSync(
    path.join(__dirname, '..', '..', 'screens', 'Map', 'MapScreen.tsx'),
    'utf8',
  );

  it('asks the server whether the question is still open instead of trusting the error', () => {
    // The honest test is not "did my request succeed" but "is anybody still
    // waiting for an answer", and only the server knows that. Keying off the
    // HTTP status instead would tie this to a 409 that the endpoint is free to
    // stop sending.
    const body = hook.slice(hook.indexOf('const checkIn'), hook.indexOf('return { journey, loading'));
    expect(body).toContain('await refresh()');
    expect(body).toContain("escalation_state === 'check_in_sent'");
  });

  it('reports a failure only while the question is outstanding', () => {
    // The negation matters. `return !(after && ...)` reports success when the
    // question is closed *or* the journey is gone; `return after && ...` would
    // invert it and warn on every successful answer.
    const body = hook.slice(hook.indexOf('const checkIn'), hook.indexOf('return { journey, loading'));
    expect(body).toContain("return !(after && after.escalation_state === 'check_in_sent')");
  });

  it('does not tell somebody their check-in failed in the words of a failed journey start', () => {
    // One dialog, two unrelated failures. The journey-start copy ends "this
    // journey will not be here if the app restarts", which said the opposite of
    // the truth when it was appended to a check-in failure on a journey that
    // was recorded and running.
    const notice = mapScreen.slice(
      mapScreen.indexOf("title: 'Check-in not sent'"),
      mapScreen.indexOf("title: 'Check-in not sent'") + 400,
    );
    expect(notice).not.toContain('will not be here if the app restarts');
    expect(notice).not.toContain('Directions will still work');
    expect(notice).toContain('still');
  });

  it('keeps every title with the body it was written for', () => {
    // A single hardcoded <Dialog title> is how the wrong copy got shown in the
    // first place, so the title travels in the state with the message.
    expect(mapScreen).toContain('journeyNotice?.title');
    expect(mapScreen).toContain('journeyNotice?.message');
    expect(mapScreen).toContain("title: 'Journey not recorded'");
    expect(mapScreen).toContain("title: 'Check-in not sent'");
  });
});

describe('an answer pressed from a notification is not thrown away', () => {
  // Found on the fifth device run. `addNotificationResponseReceivedListener`
  // only fires while the JS runtime is alive, so a lock-screen button pressed
  // against a frozen or killed app was delivered to Android, dismissed the
  // notification, and then held by expo-notifications as the *last* response --
  // which nothing read. The answer vanished and the person answered again in
  // the app, which is what they reported.
  const service = fs.readFileSync(
    path.join(__dirname, '..', '..', 'services', 'notification.service.ts'),
    'utf8',
  );

  it('reads the response that was waiting when the process started', () => {
    expect(service).toContain('getLastNotificationResponseAsync');
    // Inside initialize, so it runs on every cold start rather than only where
    // some screen remembers to ask.
    const init = service.slice(
      service.indexOf('async initialize'),
      service.indexOf('async requestPermission'),
    );
    expect(init).toContain('consumePendingResponse');
  });

  it('holds a tap that arrives before anything is listening', () => {
    // App.tsx installs the handler *after* initialize(), with awaits between,
    // and a check-in answered from the lock screen is precisely the tap that
    // arrives while the app is starting -- because answering is what starts it.
    expect(service).toContain('pendingTaps');
    const onTap = service.slice(
      service.indexOf('onAlertTap(handler'),
      service.indexOf('private deliver'),
    );
    expect(onTap).toContain('this.pendingTaps.splice(0)');
  });

  it('cannot answer the same check-in twice', () => {
    // `getLastNotificationResponseAsync` keeps returning the launching response
    // for the life of the process, so without a dedupe the cold-start read and
    // the live listener both answer -- and the second is a 409.
    expect(service).toContain('lastDeliveredId');
    const deliver = service.slice(
      service.indexOf('private deliver'),
      service.indexOf('private async consumePendingResponse'),
    );
    expect(deliver).toContain('id === this.lastDeliveredId');
  });

  it('builds the tap the same way from both sources', () => {
    // Two inline mappings would be free to disagree about which fields they
    // carry, and `journeyId` missing from one of them is a dropped answer.
    expect(service).toContain('function toAlertTap');
    expect(service.match(/toAlertTap\(/g)?.length).toBeGreaterThanOrEqual(3);
  });
});
