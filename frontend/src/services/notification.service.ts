/**
 * Push notifications, on the device side. B6a / S16.
 *
 * Four jobs:
 *
 *   initialize()      channels, permission, token, listeners — once, at startup
 *   registerDevice()  hand the token and a coarse position to the backend
 *   preferences       read and write what may interrupt this user
 *   diagnose()        say which of the four prerequisites is unsatisfied
 *
 * ## What was wrong with the version this replaces
 *
 * The inherited service created four Android channels and then never used any of
 * them: `getChannelId()` existed, was correct, and had **no call sites**, so every
 * notification it presented went to Android's fallback channel — default
 * importance, no custom sound, no vibration pattern. The channels were visible in
 * system settings and controlled nothing.
 *
 * It also obtained an Expo push token and wrote it to `SecureStore`, where
 * nothing read it. No server ever learned the address, so no push could ever have
 * been sent. `initialize()` was commented out in `App.tsx` with the note
 * "disabled in Expo Go", which was true and meant the whole path had never run.
 *
 * And `getDangerColor()` graded severity on a **0–10** scale — the legacy
 * `crime_score` that defect 11 was made of. The product has used 0–100 since D02.
 * Colour-coding a notification by a scale the backend stopped sending would have
 * put every alert in the same bucket.
 *
 * All three are gone rather than fixed in place: the token now goes to the
 * server, the channel id now comes from `features/alerts/channels.ts` (and a
 * backend invariant test asserts the two agree), and severity is not rendered as
 * colour at all — `RiskFlagMarker` already owns that decision on the map, with
 * one scale.
 *
 * ## Expo Go cannot do this, and says so
 *
 * Remote push was removed from Expo Go for Android in SDK 53. `diagnose()`
 * reports the execution environment rather than letting the failure look like a
 * backend problem, because "no notification arrived" has four possible causes and
 * three of them are silent.
 */

import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import Constants, { ExecutionEnvironment } from 'expo-constants';
import { Platform } from 'react-native';

import apiService from './api.service';
import { ALERT_CHANNELS, channelForType, createAlertChannels } from '../features/alerts/channels';
import type {
  AlertHistoryEntry,
  AlertPreferences,
  NotificationConfig,
  PushDiagnosis,
} from '../types/contracts/notifications';

/**
 * How a notification behaves when it arrives with the app in the foreground.
 *
 * `shouldShowBanner` is on. The alternative — suppressing the banner and letting
 * the map update quietly — was rejected because the map only updates if the user
 * is looking at the map. A road alert that arrives while they are reading their
 * own report history would be invisible.
 */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/** What a notification tap hands to whoever is listening. */
export interface AlertTap {
  type: string;
  flagId?: string;
  lat?: number;
  lon?: number;
  category?: string;
}

type TapHandler = (tap: AlertTap) => void;

class NotificationService {
  private notificationListener?: Notifications.Subscription;
  private responseListener?: Notifications.Subscription;
  private tapHandler?: TapHandler;
  private cachedToken: string | null = null;
  private warnedNoProjectId = false;

  /**
   * Channels, permission, token, listeners. Idempotent.
   *
   * Deliberately does **not** throw. It is called from `App.tsx`'s startup path,
   * and a device that refuses notification permission must still get an app — the
   * rest of Meridian works without push. Every failure is returned through
   * `diagnose()` instead, where a screen can show it.
   */
  async initialize(): Promise<void> {
    try {
      await createAlertChannels();
      const granted = await this.requestPermission();
      this.setupListeners();
      if (granted) {
        await this.getExpoPushToken();
      }
    } catch (error) {
      // Logged, not rethrown. See the method docstring.
      console.warn('NotificationService.initialize failed:', error);
    }
  }

  async requestPermission(): Promise<boolean> {
    const existing = await Notifications.getPermissionsAsync();
    if (existing.status === 'granted') return true;
    // Only ask if we have not been refused permanently — `canAskAgain` is false
    // after a hard denial, and calling request() then resolves immediately with
    // the same denial, which looks like a bug when it is the OS working.
    if (existing.status === 'denied' && !existing.canAskAgain) return false;
    const asked = await Notifications.requestPermissionsAsync();
    return asked.status === 'granted';
  }

  /**
   * The Expo push token for this install, or null with the reason logged.
   *
   * `projectId` is required and has no useful default: without
   * `extra.eas.projectId` in `app.json` this throws, and the thrown message is
   * the clearest statement of what is missing, so it is logged verbatim rather
   * than replaced with something friendlier.
   */
  async getExpoPushToken(): Promise<string | null> {
    if (!Device.isDevice) {
      // Simulators and emulators cannot receive remote push. Not an error.
      console.log('Push tokens need a physical device.');
      return null;
    }
    const projectId =
      Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    if (!projectId) {
      // Logged once, not on every foreground.
      //
      // This is expected and harmless now: remote push is **not** how Guardian
      // works. Zone alerts are detected by the OS on the phone and posted as
      // LOCAL notifications, so no Expo project, Firebase project or FCM key is
      // involved. The server-side dispatcher that needs a projectId is the
      // earlier reading of B6a and is off (`PUSH_ENABLED=false`).
      //
      // It warned on every app foreground, which made a correct state look like
      // a fault — three identical warnings in the first ten seconds of a
      // startup log.
      if (!this.warnedNoProjectId) {
        this.warnedNoProjectId = true;
        console.log(
          'No EAS projectId — remote push is disabled. Guardian zone alerts do not ' +
            'need it (they are local notifications).',
        );
      }
      return null;
    }
    try {
      const { data } = await Notifications.getExpoPushTokenAsync({ projectId });
      this.cachedToken = data;
      return data;
    } catch (error) {
      console.warn('Could not obtain an Expo push token:', error);
      return null;
    }
  }

  /**
   * Tell the backend where to reach this install, and roughly where it is.
   *
   * Called on every foreground, not once at sign-in. Expo tokens rotate — on
   * reinstall, on a restore to a new handset, sometimes on an OS update — and a
   * token registered once and never refreshed is the commonest way push silently
   * stops working for somebody who is still opening the app daily.
   *
   * ⚠️ `lat`/`lon` are this install's position **at this moment, in the
   * foreground**. The server stores one point and overwrites it; there is no
   * trace and no history. It is also the honest limit of the feature: alerts
   * reach a user based on where they were when they last opened the app.
   * Continuous background location and true geofence crossing are S17, the other
   * half of B6a, and they are not built.
   *
   * Returns false rather than throwing. A failed registration must not break a
   * foreground transition.
   */
  async registerDevice(position?: { lat: number; lon: number }): Promise<boolean> {
    const token = this.cachedToken ?? (await this.getExpoPushToken());
    if (!token) return false;
    try {
      await apiService.post('/notifications/devices', {
        expo_push_token: token,
        platform: Platform.OS === 'ios' ? 'ios' : 'android',
        app_version: Constants.expoConfig?.version ?? null,
        lat: position?.lat ?? null,
        lon: position?.lon ?? null,
      });
      return true;
    } catch (error) {
      console.warn('Device registration failed:', error);
      return false;
    }
  }

  /**
   * Stop sending to this install. Call on sign-out.
   *
   * The token is kept in memory only, so after a sign-out that skipped this the
   * server would keep a live address for a user who is no longer signed in — and
   * would keep alerting a phone whose owner has left.
   */
  async unregisterDevice(): Promise<void> {
    const token = this.cachedToken;
    if (!token) return;
    try {
      await apiService.delete('/notifications/devices', {
        data: { expo_push_token: token },
      });
    } catch (error) {
      console.warn('Device de-registration failed:', error);
    } finally {
      this.cachedToken = null;
    }
  }

  // -----------------------------------------------------------------------
  // Preferences, history, diagnosis
  // -----------------------------------------------------------------------
  //
  // `apiService.get` declares `ApiResponse<T>` and returns the body verbatim;
  // these endpoints answer with an unwrapped object. The double cast says so out
  // loud rather than pretending the declared type is accurate — the same idiom
  // `risk.service.ts` uses, for the same reason.

  async getPreferences(): Promise<{
    preferences: AlertPreferences;
    systemMaxPerHour: number;
    locationMaxAgeHours: number;
    hasExplicitRow: boolean;
  }> {
    const body = (await apiService.get('/notifications/preferences')) as unknown as {
      preferences: AlertPreferences;
      system_max_per_hour: number;
      location_max_age_hours: number;
      has_explicit_row: boolean;
    };
    return {
      preferences: body.preferences,
      systemMaxPerHour: body.system_max_per_hour,
      locationMaxAgeHours: body.location_max_age_hours,
      hasExplicitRow: body.has_explicit_row,
    };
  }

  async savePreferences(preferences: AlertPreferences): Promise<AlertPreferences> {
    const body = (await apiService.put(
      '/notifications/preferences',
      preferences,
    )) as unknown as { preferences: AlertPreferences };
    return body.preferences;
  }

  /**
   * Send this user a test notification.
   *
   * It counts against the hourly cap, and when the cap is what stopped it the
   * server says so in `detail`. That is deliberate — an endpoint exempt from the
   * cap would be a way to demonstrate the system while bypassing its most
   * important rule — so the screen renders `detail` verbatim instead of
   * interpreting `sent === 0` as a failure.
   */
  async sendTestAlert(): Promise<{ sent: number; devices: number; detail: string }> {
    return (await apiService.post('/notifications/test')) as unknown as {
      sent: number;
      devices: number;
      detail: string;
    };
  }

  async getHistory(limit = 50): Promise<AlertHistoryEntry[]> {
    const body = (await apiService.get(
      `/notifications/history?limit=${limit}`,
    )) as unknown as { alerts: AlertHistoryEntry[] };
    return body.alerts ?? [];
  }

  /**
   * Which of the prerequisites for remote push are satisfied.
   *
   * Four things must hold and three fail silently, so this gathers all four in
   * one place: two from the device, two from the server. Without it, "no
   * notification arrived" is one symptom with four causes, and the walkthrough
   * has nothing to check.
   */
  async diagnose(): Promise<PushDiagnosis> {
    const permission = await Notifications.getPermissionsAsync();
    const isExpoGo =
      Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
    const projectId =
      Constants.expoConfig?.extra?.eas?.projectId ??
      Constants.easConfig?.projectId ??
      null;

    let config: NotificationConfig | null = null;
    try {
      config = (await apiService.get(
        '/notifications/config',
      )) as unknown as NotificationConfig;
    } catch (error) {
      console.warn('Could not read notification config:', error);
    }

    return {
      isPhysicalDevice: Device.isDevice,
      // Expo Go dropped Android remote push in SDK 53. Reported rather than
      // worked around: there is no workaround, and a development build is the
      // answer.
      isExpoGo,
      permissionGranted: permission.status === 'granted',
      canAskAgain: permission.canAskAgain,
      hasProjectId: Boolean(projectId),
      projectId,
      tokenObtained: Boolean(this.cachedToken),
      serverPushEnabled: config?.push_enabled ?? null,
      serverProjectId: config?.expo_project_id ?? null,
      registeredDevices: config?.devices?.active ?? null,
      locatedDevices: config?.devices?.located ?? null,
      lastRejection: config?.last_rejection ?? null,
      maxAlertsPerHour: config?.max_alerts_per_hour ?? null,
      alertRadiusM: config?.alert_radius_m ?? null,
    };
  }

  // -----------------------------------------------------------------------
  // Listeners and local presentation
  // -----------------------------------------------------------------------

  /** Register a handler for notification taps. Replaces any previous one. */
  onAlertTap(handler: TapHandler): void {
    this.tapHandler = handler;
  }

  private setupListeners(): void {
    this.notificationListener?.remove();
    this.responseListener?.remove();

    this.notificationListener = Notifications.addNotificationReceivedListener(
      notification => {
        const data = notification.request.content.data as Record<string, unknown>;
        console.log('Alert received:', data?.type, data?.flagId);
      },
    );

    this.responseListener = Notifications.addNotificationResponseReceivedListener(
      response => {
        const data = (response.notification.request.content.data ?? {}) as Record<
          string,
          unknown
        >;
        this.tapHandler?.({
          type: String(data.type ?? 'unknown'),
          flagId: typeof data.flagId === 'string' ? data.flagId : undefined,
          lat: typeof data.lat === 'number' ? data.lat : undefined,
          lon: typeof data.lon === 'number' ? data.lon : undefined,
          category: typeof data.category === 'string' ? data.category : undefined,
        });
      },
    );
  }

  /**
   * Present a notification from the app itself, now.
   *
   * Only the SOS path uses this: the local notification is what confirms to the
   * person who pressed the button that something happened, without waiting on a
   * server round trip they may have no signal for.
   *
   * **It composes no text about any place.** `title` and `body` are passed in by
   * the caller, and for risk flags the only legitimate source is the server's
   * already-framed statement. Nothing here builds a sentence.
   */
  async present(options: {
    title: string;
    body: string;
    type: 'sos_alert' | 'system';
    data?: Record<string, unknown>;
  }): Promise<void> {
    const isSOS = options.type === 'sos_alert';
    await Notifications.scheduleNotificationAsync({
      content: {
        title: options.title,
        body: options.body,
        data: { type: options.type, ...options.data },
        // `sos_alert.wav` was named here and never existed -- see the note in
        // `features/alerts/channels.ts`. On Android the channel owns the sound
        // anyway; this only matters on iOS, which has no custom sound bundled.
        // `true`, not 'default': a string here goes through Android's
      // custom-sound-filename lookup and logs a "not found" error.
      sound: true,
        priority: isSOS
          ? Notifications.AndroidNotificationPriority.MAX
          : Notifications.AndroidNotificationPriority.DEFAULT,
        badge: 1,
      },
      // This is the fix for the inherited bug. `getChannelId()` existed, was
      // correct, and had no call sites, so every local notification landed on
      // Android's fallback channel with default importance and no sound.
      //
      // The channel goes on the *trigger*, not the content:
      // `ChannelAwareTriggerInput` is `{ channelId }` and
      // expo-notifications documents it as "a trigger that will cause the
      // notification to be delivered immediately" — so it is both "now" and
      // "on this channel". `trigger: null` is also immediate but carries no
      // channel, which is exactly how the original lost it.
      //
      // iOS has no channels, so `null` there.
      trigger: Platform.OS === 'android' ? { channelId: channelForType(options.type) } : null,
    });
  }

  async cancelAll(): Promise<void> {
    await Notifications.cancelAllScheduledNotificationsAsync();
  }

  cleanup(): void {
    this.notificationListener?.remove();
    this.responseListener?.remove();
    this.notificationListener = undefined;
    this.responseListener = undefined;
    this.tapHandler = undefined;
  }
}

export { ALERT_CHANNELS };
export default new NotificationService();
