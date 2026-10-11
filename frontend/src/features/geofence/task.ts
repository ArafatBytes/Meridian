/**
 * The background geofence handler. B6a / S17.
 *
 * This is the file that runs when the user is nowhere near the app — phone in a
 * pocket, screen off, Meridian not on screen and possibly not in memory. Android
 * wakes the JS runtime, evaluates the bundle, and calls the task registered
 * under `GEOFENCE_TASK`.
 *
 * ## `defineTask` must run at import time, every time
 *
 * It is called at **module scope**, and this module is imported statically from
 * `App.tsx`. That is not stylistic. On a headless wake-up the OS looks for a task
 * registered under a name; if the bundle has not evaluated the `defineTask` call
 * by the time the event is delivered, the event is **dropped silently**. Putting
 * the registration behind a lazy import, a hook, or a "start tracking" button
 * would mean geofencing worked while the app was open and nowhere else — which
 * is the only state where it is not needed.
 *
 * ## What it is allowed to touch
 *
 * AsyncStorage and `expo-notifications`. Nothing else.
 *
 * No network, no Supabase session, no API call, no zustand store, no navigation.
 * The zone text was written to disk while the app was open (`storage.ts` explains
 * why), so an alert needs nothing that could be unavailable. A task that fetched
 * the flag would need an access token, and a wake-up six hours later is exactly
 * when one has expired — on a phone that may have no data signal. It would fail
 * silently, and the only symptom would be a person walking into a flagged road
 * and hearing nothing.
 *
 * ## Everything is caught
 *
 * An unhandled rejection in a headless task is invisible: there is no console
 * anybody is watching and no screen to show an error on. So the body is wrapped,
 * and failures are written to the log the user can actually read. A crash here
 * is an alert that did not arrive.
 */

import * as Location from 'expo-location';
import { GeofencingEventType } from 'expo-location';
import * as TaskManager from 'expo-task-manager';

import { ZONE_REALERT_AFTER_MS, composeZoneAlert, presentZoneAlert } from './alert';
import { appendZoneEvent, claimZoneAlert, loadZones } from './storage';

/**
 * The task name. Shared with `service.ts`, which registers the regions.
 *
 * A string the OS persists, so **renaming it orphans any geofencing already
 * running** on an installed app: the old registration keeps firing into a task
 * that no longer exists, and `stopGeofencingAsync` under the new name cannot
 * stop it. If it ever has to change, bump the suffix and stop the old one by its
 * old name first.
 */
export const GEOFENCE_TASK = 'meridian.geofence.v1';

interface GeofenceEventBody {
  eventType: GeofencingEventType;
  region: Location.LocationRegion;
}

TaskManager.defineTask<GeofenceEventBody>(GEOFENCE_TASK, async ({ data, error }) => {
  if (error) {
    // The OS reporting a problem with monitoring itself — revoked permission,
    // location services switched off. Logged where the user can see it, because
    // from their side the symptom is identical to the feature being broken.
    await appendZoneEvent({
      flagId: '-',
      statement: '',
      title: 'Zone monitoring error',
      body: error.message ?? 'The system reported a geofencing error.',
      at: new Date().toISOString(),
      notified: false,
      reason: 'os-error',
    });
    return;
  }

  try {
    if (!data?.region) return;
    // Only entries. Exits are not registered for (`notifyOnExit: false`), but
    // the OS may still deliver one, and "you have left a risk area" is not
    // something worth waking somebody up for.
    if (data.eventType !== GeofencingEventType.Enter) return;

    const identifier = data.region.identifier;
    if (!identifier) return;

    const zones = await loadZones();
    const meta = zones[identifier];
    if (!meta) {
      // The OS is still monitoring a region the app has since forgotten —
      // normal for a few minutes after a refresh, since `startGeofencingAsync`
      // replaces the whole set and in-flight events can arrive against the old
      // one. Nothing to say about a zone whose text we no longer hold.
      return;
    }

    const now = Date.now();
    const text = composeZoneAlert(meta);
    const mayAlert = await claimZoneAlert(meta.flagId, now, ZONE_REALERT_AFTER_MS);

    if (!mayAlert) {
      // Recorded rather than dropped. A suppressed crossing and a missed
      // crossing look identical from the outside, and the difference is the
      // difference between the debounce working and the feature being broken.
      await appendZoneEvent({
        flagId: meta.flagId,
        statement: meta.statement,
        title: text.title,
        body: text.body,
        at: new Date(now).toISOString(),
        notified: false,
        reason: 'already alerted in the last 6 hours',
      });
      return;
    }

    await presentZoneAlert(meta);
    await appendZoneEvent({
      flagId: meta.flagId,
      statement: meta.statement,
      title: text.title,
      body: text.body,
      at: new Date(now).toISOString(),
      notified: true,
    });
  } catch (problem: unknown) {
    await appendZoneEvent({
      flagId: '-',
      statement: '',
      title: 'Zone alert failed',
      body: problem instanceof Error ? problem.message : String(problem),
      at: new Date().toISOString(),
      notified: false,
      reason: 'task-threw',
    });
  }
});
