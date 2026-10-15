/**
 * JG1 — resuming a journey, and not accidentally starting a second one.
 *
 * `goesTo` is the whole of the decision that `Start` makes between "record a new
 * journey" and "this is the one already open". Getting it wrong in either
 * direction is invisible on the screen and expensive later:
 *
 * * **Too tight** and resuming writes a second journey, moving `started_at` to
 *   now -- so from JG2 onward the deadline silently resets every time someone
 *   reopens the app, which is the one thing a deadline must never do.
 * * **Too loose** and a journey to a different place keeps the old row, so from
 *   JG3 onward a guardian is told the wrong destination.
 */
import fs from 'fs';
import path from 'path';

import { goesTo, startedAtLabel, TOLERANCE_DEGREES } from './resume';

const mirpur = { destination_latitude: 23.8223, destination_longitude: 90.3654 };

describe('goesTo', () => {
  it('recognises the journey already open', () => {
    expect(goesTo(mirpur, { latitude: 23.8223, longitude: 90.3654 })).toBe(true);
  });

  it('tolerates a destination that made the round trip through PostGIS', () => {
    // A geography column stores float8, and the value coming back is equal to
    // about a metre rather than bit-identical.
    expect(goesTo(mirpur, { latitude: 23.82230001, longitude: 90.36539998 })).toBe(true);
  });

  it('does not recognise a different place', () => {
    // Gulshan 2, about 5 km away.
    expect(goesTo(mirpur, { latitude: 23.7925, longitude: 90.4078 })).toBe(false);
  });

  it('does not recognise the other side of a road', () => {
    // ~100 m north. Two cafés facing each other are different destinations, and
    // from JG3 onward this is what a guardian is told.
    expect(goesTo(mirpur, { latitude: 23.8232, longitude: 90.3654 })).toBe(false);
  });

  it('needs both coordinates to match, not either', () => {
    expect(goesTo(mirpur, { latitude: 23.8223, longitude: 90.4078 })).toBe(false);
    expect(goesTo(mirpur, { latitude: 23.7925, longitude: 90.3654 })).toBe(false);
  });

  it('is a tolerance of roughly 55 m, not of a city block', () => {
    // The number itself, pinned. A later phase widening this would widen what
    // counts as "the same journey", and the failure is silent.
    expect(TOLERANCE_DEGREES * 111_000).toBeGreaterThan(40);
    expect(TOLERANCE_DEGREES * 111_000).toBeLessThan(70);
  });
});

describe('startedAtLabel', () => {
  it('reads an ISO instant from the server', () => {
    // Local time, deliberately: the label answers "when did I set off", which is
    // a question about the clock on the wall where the person is. Asserted
    // loosely because the test runner's zone is not fixed.
    expect(startedAtLabel('2026-10-14T16:04:00Z')).toMatch(/^\d{1,2}:\d{2} (AM|PM)$/);
  });

  it('is empty rather than "Invalid Date" for anything unparseable', () => {
    expect(startedAtLabel('')).toBe('');
    expect(startedAtLabel('not a date')).toBe('');
  });
});

/**
 * The ordering invariants, as source checks.
 *
 * The same approach `useNavigation.test.ts` takes, and for the same reason: there
 * is no React Testing Library in this project, and these are sequencing rules in
 * a screen rather than behaviour of a pure function. A grep cannot prove the
 * ordering is right, but it fails loudly when the line that establishes it is
 * deleted -- which is the realistic regression.
 */
describe('MapScreen wires the journey in the order JG1 requires', () => {
  const mapScreen = fs.readFileSync(
    path.join(__dirname, '..', '..', 'screens', 'Map', 'MapScreen.tsx'),
    'utf8',
  );

  it('writes the journey before it starts following', () => {
    // The row has to exist before the thing that can be killed begins. If these
    // two swap, a force-stop in the first second of a walk loses the journey --
    // which is precisely the case this phase exists for.
    const write = mapScreen.indexOf('await journey.start({');
    const follow = mapScreen.indexOf('void follow.start();', write);
    expect(write).toBeGreaterThan(-1);
    expect(follow).toBeGreaterThan(write);
  });

  it('does not record a second journey for the one already open', () => {
    expect(mapScreen).toContain('goesTo(open, destination)');
  });

  it('closes the journey by arriving, not by cancelling, when the navigator says so', () => {
    const arrived = mapScreen.indexOf("follow.phase !== 'arrived'");
    expect(arrived).toBeGreaterThan(-1);
    expect(mapScreen.slice(arrived, arrived + 200)).toContain('journey.arrive()');
  });

  it('cancels the journey when following is stopped by hand', () => {
    // `arrive` and `cancel` have to stay distinct: "got there" versus "stopped
    // telling us" is the distinction the whole feature is built on.
    const stop = mapScreen.indexOf('onStop={() => {');
    expect(stop).toBeGreaterThan(-1);
    expect(mapScreen.slice(stop, stop + 600)).toContain('journey.cancel()');
  });

  it('keeps the resume card off the first frame, and out of route mode unless asked', () => {
    // `loading` is what stops it flashing in and out while the launch read is in
    // flight. `|| awaitingAnswer` is JG2: the deadline usually passes while
    // somebody is still walking, which is route mode, which is exactly when this
    // card used to be hidden -- leaving the notification as the only way to
    // answer.
    expect(mapScreen).toContain(
      'const showResume = (!routeMode || awaitingAnswer) && !journey.loading && !!journey.journey;',
    );
  });

  it('moves the buttons back up when the resume card goes away', () => {
    // `onLayout` does not fire on unmount, so the measured height outlives the
    // card. Deriving the offset from `showResume` is what makes the stack
    // correct in both directions rather than only on the way down.
    expect(mapScreen).toContain('showResume && resumeHeight > 0 ? resumeHeight + space.sm : 0');
  });

  it('says "journey not recorded" in the app dialog, not the phone one', () => {
    // `Alert.alert` draws the operating system's box -- Roboto, the platform
    // accent, and on some Android skins a white panel over a dark map. The one
    // moment the app most needs to look deliberate is the moment it is telling
    // you something failed.
    //
    // The title used to sit in the JSX, so this walked back from it to the
    // `<Dialog` tag. JG2 moved it into the notice itself -- one dialog serves two
    // unrelated failures and a single hardcoded title is how the wrong copy got
    // shown -- so the check is now the two halves: the message exists, and the
    // dialog that renders it is ours.
    expect(mapScreen).toContain("title: 'Journey not recorded'");
    const dialog = mapScreen.indexOf('<Dialog');
    expect(dialog).toBeGreaterThan(-1);
    expect(mapScreen.slice(dialog, mapScreen.indexOf('/>', dialog))).toContain(
      'journeyNotice?.title',
    );
    // Scoped to the two journey-failure paths, not the whole screen: this file
    // has half a dozen legitimate `Alert.alert` calls for routing and location
    // errors, and whether those should also be Dialogs is a separate question
    // this test has no business answering.
    for (const raise of ["title: 'Journey not recorded'", "title: 'Check-in not sent'"]) {
      const at = mapScreen.indexOf(raise);
      expect(at).toBeGreaterThan(-1);
      expect(mapScreen.slice(at - 400, at)).not.toContain('Alert.alert');
    }
  });

  it('raises that notice from the result of the write, not from hook state', () => {
    // A failure message kept in state is the same string the second time, so
    // nothing watching it can tell "failed again" from "still failed" -- and the
    // second press of Start is exactly the one someone makes when the first
    // looked like it did nothing.
    expect(mapScreen).toContain('if (written.error)');
    const raise = mapScreen.indexOf('if (written.error)');
    expect(mapScreen.slice(raise, raise + 300)).toContain('setJourneyNotice({');
    expect(mapScreen).not.toContain('journey.error');
  });
});

/**
 * One layout rule, because it cost a bug report from a real phone.
 */
describe('the route planner inputs cannot overflow their row', () => {
  const mapScreen = fs.readFileSync(
    path.join(__dirname, '..', '..', 'screens', 'Map', 'MapScreen.tsx'),
    'utf8',
  );

  it('zeroes the padding Android gives an EditText and stretches to the row', () => {
    // Android's own vertical padding pushed the measured input past the 36pt
    // row, and a ViewGroup clips what overflows it: the descenders went --
    // "Mirpur Bangla School and College" lost the tails of both g's. Invisible
    // on iOS, which is why it looked like one device's problem.
    const input = mapScreen.indexOf('    input: {');
    expect(input).toBeGreaterThan(-1);
    const style = mapScreen.slice(input, mapScreen.indexOf('},', input));
    expect(style).toContain('paddingVertical: 0');
    expect(style).toContain("alignSelf: 'stretch'");
  });
});
