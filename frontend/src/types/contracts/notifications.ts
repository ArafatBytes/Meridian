/**
 * Notification contracts. B6a / S16.
 *
 * Mirrors the shapes in `backend/app/api/v1/endpoints/notifications.py`. Hand-kept,
 * like `contracts/risk.ts` — the contract-drift CI check is B2 and does not exist
 * yet, so the only thing stopping these from diverging is that they are small and
 * sit next to each other in a diff.
 *
 * Fields are **snake_case here on purpose**, unlike `RiskFlag`. The risk endpoint
 * is read on a hot path and `risk.service.ts` maps it to camelCase once; these are
 * read on a settings screen and written straight back by `PUT /preferences`, so a
 * mapping layer would be two translations for no benefit and one more place for a
 * field to be dropped silently.
 */

/**
 * What may interrupt this user. Mirrors `AlertPreferences` in
 * `app/alerts/policy.py` and the `notification_preferences` table.
 *
 * The defaults live on the server — in the dataclass and in the column defaults,
 * which a backend test pins to each other — so there are deliberately none here.
 * A client-side default would be a third source of truth and the one most likely
 * to drift.
 */
export interface AlertPreferences {
  /** Something affecting movement now, near where the app last had your location. */
  corridor_alerts: boolean;
  /** D09's forward-dated windows: a road expected to be affected later today. */
  scheduled_alerts: boolean;
  /**
   * Historical patterns. Off by default on the server, and the one switch worth
   * hesitating over — a chronic flag covers ~2 km and never expires, so turning
   * this on means a slow drip of "this area has a history" that shares the same
   * hourly budget as alerts about things actually happening.
   */
  chronic_alerts: boolean;
  /** 0–100, after decay and after confidence damping. Not a percentage. */
  min_severity: number;
  /** Dhaka-local hour, 0–23, inclusive. Null together with `quiet_hours_end`. */
  quiet_hours_start: number | null;
  /** Dhaka-local hour, 0–23, exclusive. May be lower than the start (a night). */
  quiet_hours_end: number | null;
  /** A self-imposed cap. May only be stricter than the server's; null = use theirs. */
  max_per_hour: number | null;
}

/** One row of `sent_alerts`, as `GET /notifications/history` returns it. */
export interface AlertHistoryEntry {
  flag_id: string;
  category: 'corridor' | 'scheduled' | 'chronic' | 'test';
  severity_at_send: number;
  /**
   * What was actually shown, stored at send time rather than re-derived.
   *
   * The flag decays and may later be confirmed, so rendering the history from
   * the live flag would show the alert as it would read *today* instead of as it
   * was sent — which defeats the point of having a record.
   */
  title: string;
  body: string;
  delivery: 'queued' | 'accepted' | 'rejected';
  error: string | null;
  sent_at: string;
}

/** `GET /notifications/config`. Server-side prerequisites, plus the live settings. */
export interface NotificationConfig {
  push_enabled: boolean;
  expo_project_id: string | null;
  max_alerts_per_hour: number;
  alert_radius_m: number;
  location_max_age_hours: number;
  devices: { active: number; disabled: number; located: number };
  /** The error from the most recent rejected send, or null. */
  last_rejection: string | null;
}

/**
 * Every prerequisite for remote push, device-side and server-side, in one object.
 *
 * Not a server shape — `NotificationService.diagnose()` assembles it. It exists
 * because four separate things have to be true before a notification arrives and
 * **three of them fail silently**:
 *
 *   1. a physical device (simulators cannot receive remote push)
 *   2. a development build, not Expo Go — Android push was removed from Expo Go
 *      in SDK 53
 *   3. notification permission granted
 *   4. an EAS `projectId`, a token, `PUSH_ENABLED` on, and FCM credentials
 *      uploaded to the EAS project
 *
 * Only the third produces a visible prompt. The rest just mean nothing arrives,
 * which is indistinguishable from the backend having decided not to send —
 * exactly the ambiguity the alert history and this object exist to remove.
 */
export interface PushDiagnosis {
  isPhysicalDevice: boolean;
  isExpoGo: boolean;
  permissionGranted: boolean;
  canAskAgain: boolean;
  hasProjectId: boolean;
  projectId: string | null;
  tokenObtained: boolean;
  /** Null when the server could not be reached. Distinct from false. */
  serverPushEnabled: boolean | null;
  serverProjectId: string | null;
  registeredDevices: number | null;
  locatedDevices: number | null;
  lastRejection: string | null;
  maxAlertsPerHour: number | null;
  alertRadiusM: number | null;
}

/**
 * The one blocking problem to show the user, or null when push should work.
 *
 * Ordered by what to fix first, and it returns a single string rather than a list
 * because a settings screen showing four simultaneous complaints gets ignored.
 * Each message names the thing to do, not the thing that is wrong.
 */
export function blockingPushProblem(diagnosis: PushDiagnosis): string | null {
  if (!diagnosis.isPhysicalDevice) {
    return 'Push notifications need a real phone — a simulator cannot receive them.';
  }
  if (diagnosis.isExpoGo) {
    return (
      'Expo Go cannot receive push notifications on Android. Install the ' +
      'development build to test alerts.'
    );
  }
  if (!diagnosis.hasProjectId) {
    return 'This build has no EAS project id, so it cannot obtain a push token.';
  }
  if (!diagnosis.permissionGranted) {
    return diagnosis.canAskAgain
      ? 'Allow notifications to receive alerts about roads near you.'
      : 'Notifications are blocked. Turn them on in your phone’s settings for Meridian.';
  }
  if (!diagnosis.tokenObtained) {
    return 'Could not get a push token from Expo. Reopen the app to try again.';
  }
  if (diagnosis.serverPushEnabled === false) {
    return 'Alert delivery is switched off on the server (PUSH_ENABLED).';
  }
  if (diagnosis.serverPushEnabled === null) {
    return 'Could not reach the server to check alert delivery.';
  }
  if (diagnosis.registeredDevices === 0) {
    return 'This device is not registered for alerts yet. Reopen the app to register it.';
  }
  // A rejection is reported last: push is configured, and this is the only
  // signal that FCM credentials are missing on the EAS project — the one
  // prerequisite the server cannot check directly.
  if (diagnosis.lastRejection) {
    return `The last alert was rejected: ${diagnosis.lastRejection}`;
  }
  return null;
}
