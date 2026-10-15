/**
 * Android channel ids, and the things that must stay true about them.
 *
 * B6a / S16. The cross-codebase half of this contract is asserted on the backend
 * (`tests/invariants/test_alert_channels_match_the_client.py` reads this
 * directory's `channels.ts`). What is checked here is the client's own side: the
 * ids are the literal strings the backend sends, and the fallback behaviour is
 * the safe one.
 */

import fs from 'fs';
import path from 'path';

import { ALERT_CHANNELS, ALL_CHANNEL_IDS, channelForType } from './channels';

describe('ALERT_CHANNELS', () => {
  /**
   * The ids are a wire contract, not an implementation detail.
   *
   * Written out as literals rather than derived, because the point of the test
   * is to make a rename visible: `backend/app/alerts/compose.py` sends these
   * exact strings, and Android silently files a notification under a fallback
   * channel when they disagree — default importance, no sound, no vibration, no
   * error anywhere.
   */
  it('are the exact strings the backend sends', () => {
    expect(ALERT_CHANNELS).toEqual({
      RISK: 'risk_alert',
      SOS: 'sos_alert',
      SYSTEM: 'system',
      // JG2. Its own channel so that silencing road alerts after a noisy week
      // does not also silence the question asking whether you got home.
      JOURNEY: 'journey_check_in',
    });
  });

  it('has no duplicates', () => {
    expect(new Set(ALL_CHANNEL_IDS).size).toBe(ALL_CHANNEL_IDS.length);
  });

  /**
   * The two inherited channels that were removed must stay removed.
   *
   * `danger_zone` is the framing the product abandoned, and a channel name is a
   * *user-visible string* in Android's settings list — so shipping one would put
   * the one word concept document §9 forbids into the OS settings screen, where
   * nothing in `framing.py` can reach it. `crime_report` never had a sender.
   *
   * Pinned because re-adding one is a two-line change that nothing else would
   * notice.
   */
  it('does not reintroduce the abandoned channels', () => {
    expect(ALL_CHANNEL_IDS).not.toContain('danger_zone');
    expect(ALL_CHANNEL_IDS).not.toContain('crime_report');
  });
});

describe('channelForType', () => {
  it('maps the types the app presents locally', () => {
    expect(channelForType('risk_alert')).toBe(ALERT_CHANNELS.RISK);
    expect(channelForType('sos_alert')).toBe(ALERT_CHANNELS.SOS);
    expect(channelForType('system')).toBe(ALERT_CHANNELS.SYSTEM);
  });

  /**
   * An unknown type must not be guessed as urgent.
   *
   * It is far more likely to be a stale payload from an older build than a
   * genuine warning. Defaulting to the risk channel would make every unrecognised
   * notification buzz at high importance, and defaulting to SOS would make it
   * take over the screen. `system` is the way to be wrong quietly.
   */
  it.each([undefined, '', 'unknown', 'danger_zone', 'DANGER'])(
    'falls back to the low-importance channel for %p',
    type => {
      expect(channelForType(type as string | undefined)).toBe(ALERT_CHANNELS.SYSTEM);
    },
  );
});

/**
 * Background delivery. JG2, found on the fifth device run.
 *
 * Android freezes a backgrounded app's process, and `expo-notifications` builds
 * the notification inside it -- so a check-in arrives at the device and then
 * waits for the phone to be woken. These assertions pin the two things that
 * make the exemption askable at all, both of which live outside TypeScript and
 * neither of which fails loudly: the manifest permission, and the dependency
 * that opens the dialog.
 */
describe('the app can ask to keep running in the background', () => {
  const appJson = JSON.parse(
    fs.readFileSync(path.join(__dirname, '..', '..', '..', 'app.json'), 'utf8'),
  );
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(__dirname, '..', '..', '..', 'package.json'), 'utf8'),
  );

  it('declares the permission the request dialog needs', () => {
    // Without it `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` throws and the user
    // lands in the settings list instead of a one-tap dialog. The failure is a
    // worse experience rather than an error, so nothing would report it.
    expect(appJson.expo.android.permissions).toContain(
      'REQUEST_IGNORE_BATTERY_OPTIMIZATIONS',
    );
  });

  it('keeps the two modules the check and the request need', () => {
    // `expo-battery` reads whether Android may freeze us; `expo-intent-launcher`
    // opens the dialog. Both are native, so losing either is a runtime failure
    // on a phone and nothing at all in CI.
    expect(packageJson.dependencies['expo-battery']).toBeDefined();
    expect(packageJson.dependencies['expo-intent-launcher']).toBeDefined();
  });

  it('reaches the diagnosis from the Profile screen', () => {
    // The battery problem is reported on AlertPreferences, and that screen was
    // unreachable for most of this project's life -- the row was removed when
    // push was off at both ends. A diagnosis nobody can open diagnoses nothing.
    const profile = fs.readFileSync(
      path.join(__dirname, '..', '..', 'screens', 'Profile', 'ProfileScreen.tsx'),
      'utf8',
    );
    expect(profile).toContain("navigation.navigate('AlertPreferences')");
  });
});
