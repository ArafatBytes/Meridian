/**
 * `blockingPushProblem` — the one sentence to show when push is not working.
 *
 * B6a / S16. This is the only logic in the notification feature that is pure
 * enough to test on the client, and it is worth testing because of what it is
 * for: four prerequisites must hold before a notification arrives and **three of
 * them fail silently**. Get the ordering wrong and the screen tells somebody to
 * allow notifications when the real problem is that they are running Expo Go,
 * which cannot deliver them however many times permission is granted.
 *
 * The ordering is therefore the test: most fundamental cause first, so the advice
 * is always actionable.
 */

import { blockingPushProblem, type PushDiagnosis } from './notifications';

/** Everything satisfied. Each test breaks exactly one thing. */
const healthy: PushDiagnosis = {
  isPhysicalDevice: true,
  isExpoGo: false,
  permissionGranted: true,
  canAskAgain: true,
  hasProjectId: true,
  projectId: 'abc-123',
  tokenObtained: true,
  serverPushEnabled: true,
  serverProjectId: 'abc-123',
  registeredDevices: 1,
  locatedDevices: 1,
  lastRejection: null,
  maxAlertsPerHour: 3,
  alertRadiusM: 500,
  batteryOptimized: false,
};

describe('blockingPushProblem', () => {
  it('reports nothing when every prerequisite is satisfied', () => {
    expect(blockingPushProblem(healthy)).toBeNull();
  });

  it('names the simulator before anything else', () => {
    const problem = blockingPushProblem({ ...healthy, isPhysicalDevice: false });
    expect(problem).toMatch(/real phone/i);
  });

  /**
   * Expo Go outranks permission, and that ordering is the point.
   *
   * Android remote push was removed from Expo Go in SDK 53. Someone testing in
   * Expo Go with notifications allowed would otherwise be told everything is
   * fine while nothing ever arrives — or, worse, be sent round the permission
   * loop repeatedly. The fix is a development build and the message says so.
   */
  it('names Expo Go even when permission is granted', () => {
    const problem = blockingPushProblem({ ...healthy, isExpoGo: true });
    expect(problem).toMatch(/Expo Go/);
    expect(problem).toMatch(/development build/i);
  });

  it('names a missing EAS project id before permission', () => {
    const problem = blockingPushProblem({
      ...healthy,
      hasProjectId: false,
      projectId: null,
      permissionGranted: false,
    });
    expect(problem).toMatch(/EAS project id/i);
  });

  /**
   * A soft denial and a hard one need different advice.
   *
   * After a hard denial `canAskAgain` is false and `requestPermissionsAsync`
   * resolves immediately with the same denial — so "Allow notifications" would be
   * a button that visibly does nothing. The only route back is the OS settings
   * app, and the message has to say that.
   */
  it('distinguishes a refusable prompt from a blocked one', () => {
    expect(
      blockingPushProblem({ ...healthy, permissionGranted: false, canAskAgain: true }),
    ).toMatch(/^Allow notifications/);

    const blocked = blockingPushProblem({
      ...healthy,
      permissionGranted: false,
      canAskAgain: false,
    });
    expect(blocked).toMatch(/blocked/i);
    expect(blocked).toMatch(/settings/i);
  });

  it('reports a missing token', () => {
    expect(blockingPushProblem({ ...healthy, tokenObtained: false })).toMatch(/push token/i);
  });

  it('reports delivery being switched off server-side', () => {
    expect(blockingPushProblem({ ...healthy, serverPushEnabled: false })).toMatch(
      /PUSH_ENABLED/,
    );
  });

  /**
   * `null` is not `false`.
   *
   * `serverPushEnabled: null` means the config request failed, which is a
   * different problem from delivery being deliberately off — and reporting it as
   * "switched off on the server" would send somebody to edit a setting that is
   * already correct.
   */
  it('separates an unreachable server from a disabled one', () => {
    expect(blockingPushProblem({ ...healthy, serverPushEnabled: null })).toMatch(
      /reach the server/i,
    );
  });

  it('reports a device that never registered', () => {
    expect(blockingPushProblem({ ...healthy, registeredDevices: 0 })).toMatch(
      /not registered/i,
    );
  });

  /**
   * A rejection is reported last, and it is the only signal for the one
   * prerequisite nothing can check directly.
   *
   * Missing FCM credentials on the EAS project are invisible to both the app and
   * the backend — Expo reports it per message. So once everything else is
   * satisfied, the error from the most recent rejected send is the diagnosis, and
   * it is surfaced verbatim rather than paraphrased.
   */
  it('surfaces the last rejection once everything else is satisfied', () => {
    const problem = blockingPushProblem({
      ...healthy,
      lastRejection: 'InvalidCredentials: no FCM key',
    });
    expect(problem).toContain('InvalidCredentials: no FCM key');
  });

  it('does not let a stale rejection mask a current blocker', () => {
    const problem = blockingPushProblem({
      ...healthy,
      permissionGranted: false,
      lastRejection: 'InvalidCredentials: no FCM key',
    });
    expect(problem).toMatch(/notifications/i);
    expect(problem).not.toContain('InvalidCredentials');
  });

  /**
   * Battery optimisation. The ninth prerequisite, added after a device run
   * where every other one was green: Expo said `ok`, the FCM receipt said `ok`,
   * and the notification still did not arrive until the screen was woken --
   * because Android had frozen the app process, and `expo-notifications` builds
   * the notification inside it. See `features/alerts/background.ts`.
   */
  describe('battery optimisation', () => {
    it('is reported when nothing else is wrong', () => {
      const problem = blockingPushProblem({ ...healthy, batteryOptimized: true });
      expect(problem).toMatch(/wake the phone/i);
    });

    it('names the symptom the person noticed, not the Android setting', () => {
      // Somebody reading this has observed notifications arriving when they
      // pick the phone up. A sentence opening with "battery optimisation" is
      // about Android; one opening with what they saw is about them.
      const problem = blockingPushProblem({ ...healthy, batteryOptimized: true }) ?? '';
      expect(problem.toLowerCase().indexOf('wake the phone')).toBeLessThan(
        problem.toLowerCase().indexOf('android'),
      );
    });

    it('comes last, because every other blocker means nothing arrives at all', () => {
      // This one means the notification arrives and waits. Anything above it
      // means there is no notification, which is the worse problem and the one
      // to name first.
      const problem = blockingPushProblem({
        ...healthy,
        batteryOptimized: true,
        lastRejection: 'InvalidCredentials: no FCM key',
      });
      expect(problem).toContain('InvalidCredentials');
    });

    it('says nothing on a phone that is already exempt, or where it cannot be asked', () => {
      // `null` is iOS, or a query that threw. Telling an iPhone user to find an
      // Android battery setting is worse than saying nothing, and so is nagging
      // somebody who has already granted it.
      expect(blockingPushProblem({ ...healthy, batteryOptimized: false })).toBeNull();
      expect(blockingPushProblem({ ...healthy, batteryOptimized: null })).toBeNull();
    });
  });
});
