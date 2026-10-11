/**
 * Keeping the server's idea of this device current. B6a / S16.
 *
 * One job: make sure the backend knows (a) where to push to, and (b) roughly
 * where this phone is — so the dispatcher has something to match flags against.
 *
 * ## Why this runs on every foreground and not once at sign-in
 *
 * Two things go stale, on different clocks.
 *
 * **The token.** Expo push tokens rotate — on reinstall, on a restore to a new
 * handset, occasionally on an OS update. A token registered once at sign-in and
 * never refreshed is the single commonest way push silently stops working for
 * somebody who is still opening the app every day. Nothing surfaces it: the
 * server holds an address that no longer resolves, and Expo answers
 * `DeviceNotRegistered`, which disables the row.
 *
 * **The position.** This is the honest limit of the whole feature. The server
 * stores one point per device and overwrites it; there is no background
 * location, because that is S17 and is not built. So the position is only as
 * fresh as the last time the app was open, and the backend refuses to alert on
 * one older than `DEVICE_LOCATION_MAX_AGE` (six hours). Re-registering on
 * foreground is what keeps a daily user inside that window.
 *
 * ## Why it fails quietly
 *
 * Every function here returns rather than throws. It is called from `App.tsx`'s
 * startup path and from an `AppState` listener, and neither is a place where an
 * exception has anywhere useful to go. A user who declines location permission
 * must still get an app; they simply never match a corridor alert, which the
 * Alerts screen states plainly.
 */

import { AppState, type AppStateStatus } from 'react-native';

import LocationService from '../../services/location.service';
import NotificationService from '../../services/notification.service';
import { supabase } from '../../lib/supabase';

/**
 * How long to wait before re-registering on a foreground transition.
 *
 * Android and iOS both fire `active` on transient events — a permission dialog
 * dismissing, the app switcher closing — so a user flicking between apps would
 * otherwise produce a burst of identical registrations. Thirty seconds is short
 * enough that a genuine return to the app refreshes the position and long enough
 * that incidental transitions do not.
 */
const MIN_REREGISTER_INTERVAL_MS = 30_000;

let lastRegisteredAt = 0;
let subscription: { remove: () => void } | null = null;

/**
 * Register this install, if there is somebody signed in.
 *
 * The session check is not optional: `POST /notifications/devices` is
 * authenticated and scopes the row to the caller's `user_id`, so calling it
 * before sign-in is a guaranteed 401. Asked of Supabase directly rather than
 * read from the auth store, for the same reason `auth.service.ts` does — a
 * cached token that has expired looks exactly like a valid one until the request
 * comes back 401, and that bug cost a sprint.
 *
 * Returns whether the server now has a current address for this device.
 */
export async function registerForAlerts(): Promise<boolean> {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session) return false;

    // A position is nice to have, not required. Registering without one still
    // records the token, so a test alert works and the user is reachable the
    // moment they grant location — the alternative, skipping registration
    // entirely, would make "no device registered" the diagnosis for what is
    // really "no location permission".
    let position: { lat: number; lon: number } | undefined;
    try {
      const where = await LocationService.getCurrentLocation();
      position = { lat: where.latitude, lon: where.longitude };
    } catch {
      position = undefined;
    }

    const ok = await NotificationService.registerDevice(position);
    if (ok) lastRegisteredAt = Date.now();
    return ok;
  } catch (error) {
    console.warn('registerForAlerts failed:', error);
    return false;
  }
}

/**
 * Re-register whenever the app comes to the foreground, at most every 30 s.
 *
 * Returns an unsubscribe function. Idempotent: calling it twice replaces the
 * previous listener rather than stacking a second one, because a duplicated
 * `AppState` subscription is invisible and doubles every registration.
 */
export function watchForegroundRegistration(): () => void {
  subscription?.remove();

  const onChange = (state: AppStateStatus) => {
    if (state !== 'active') return;
    if (Date.now() - lastRegisteredAt < MIN_REREGISTER_INTERVAL_MS) return;
    // Deliberately not awaited: an AppState handler must not block the
    // transition, and nothing downstream needs the result.
    void registerForAlerts();
  };

  subscription = AppState.addEventListener('change', onChange);
  return () => {
    subscription?.remove();
    subscription = null;
  };
}

/**
 * Forget this install. Call on sign-out, before the session is cleared.
 *
 * Order matters: `DELETE /notifications/devices` is authenticated, so once the
 * session is gone the call 401s and the server keeps a live push address for a
 * user who has signed out — and keeps alerting a phone whose owner has left.
 */
export async function unregisterForAlerts(): Promise<void> {
  lastRegisteredAt = 0;
  await NotificationService.unregisterDevice();
}
