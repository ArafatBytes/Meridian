/**
 * The lock-screen answer. JG2.
 *
 * The whole point of this phase from the person's side is one tap without
 * opening anything. On Android that means an **Expo notification category**: a
 * named set of action buttons the app registers once at startup, which the
 * backend then names on the message with `categoryId`. Android draws the buttons
 * from the registration, not from the message.
 *
 * ## The two strings that have to match, and what happens when they don't
 *
 * `CHECK_IN_ACTION_CATEGORY` here must equal the one in
 * `backend/app/journeys/checkin.py`. If it doesn't, the notification arrives
 * with **no buttons at all** — not an error, not a warning, just a plain
 * notification — and the feature silently degrades to "open the app and find the
 * journey card". Nothing in either codebase reports it.
 *
 * `backend/tests/invariants/test_journey_deadline.py` reads this file and
 * asserts both ids agree, which is the same crude cross-codebase check
 * `test_alert_channels_match_the_client.py` already does for channel ids, for
 * the same reason: it is that or nothing.
 *
 * ## Why the button does not open the app
 *
 * `opensAppToForeground: false`. The person is meant to be able to answer from a
 * lock screen with the phone still in their hand, in a CNG, without the app
 * taking over the screen — and JOURNEY_GUARDIAN.md §5 notes the case where
 * somebody is watching them answer it. An app that launches announces itself; a
 * notification that quietly disappears does not.
 *
 * The cost is that the answer is posted from a JS context that Android woke for
 * the purpose, which is the least reliable place in this codebase to run a
 * network call. The journey card in the app answers the same question with the
 * same endpoint, and it is the fallback the walkthrough checks.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

/** Must equal `CHECK_IN_ACTION_CATEGORY` in `backend/app/journeys/checkin.py`. */
export const CHECK_IN_ACTION_CATEGORY = 'journey_check_in';

/** Must equal `CHECK_IN_ACTION_OK` in the same file. */
export const CHECK_IN_ACTION_OK = 'journey_ok';

/**
 * The `data.type` the backend puts on the message.
 *
 * Checked as well as the action id, because a tap on the notification *body*
 * carries the default action identifier rather than ours, and that tap should
 * still be recognisable as "this was about a journey".
 */
export const CHECK_IN_TYPE = 'journey_check_in';

/**
 * One button, labelled here.
 *
 * Android renders the label the app registered, never one sent with the push, so
 * this string is the only place it exists. The backend's `_BUTTON` constant is a
 * copy kept for the invariant test to compare against — it is never transmitted.
 */
export const CHECK_IN_OK_LABEL = "I'm fine";

/**
 * Register the category. Idempotent; safe to call on every startup.
 *
 * iOS is included even though JG2 is demonstrated on Android: the call is the
 * same and a category registered on a platform that never receives the push
 * costs nothing, whereas discovering at JG3 that iOS was never wired is a
 * surprise at the worst time.
 */
export async function registerCheckInCategory(): Promise<void> {
  try {
    await Notifications.setNotificationCategoryAsync(CHECK_IN_ACTION_CATEGORY, [
      {
        identifier: CHECK_IN_ACTION_OK,
        buttonTitle: CHECK_IN_OK_LABEL,
        options: {
          // See the module note. The whole feature is one tap without the app
          // appearing.
          opensAppToForeground: false,
          // Android only; harmless elsewhere. Dismisses the notification once
          // the action is taken, so a phone in a pocket does not keep a stale
          // question on its lock screen after it has been answered.
          isDestructive: false,
        },
      },
    ]);
  } catch (error) {
    // Never throws. This runs inside `App.tsx`'s startup path alongside channel
    // creation, and a device that cannot register a category must still get an
    // app — it gets a notification with no buttons, and the journey card.
    console.warn('[journey] could not register the check-in category', error);
  }
}

/**
 * Whether a notification response is somebody answering a check-in.
 *
 * Pure, and exported so it can be tested without a notification: everything else
 * in this file needs a device.
 *
 * Accepts the button **and** a tap on the notification body. A person who taps
 * the notification rather than the button has answered the question as plainly
 * as one who pressed the button, and treating that as "no answer" would mean the
 * most obvious gesture on the screen is the one that does nothing.
 */
export function isCheckInAnswer(response: {
  actionIdentifier?: string;
  type?: string;
}): boolean {
  if (response.type !== CHECK_IN_TYPE) return false;
  return (
    response.actionIdentifier === CHECK_IN_ACTION_OK ||
    response.actionIdentifier === Notifications.DEFAULT_ACTION_IDENTIFIER ||
    response.actionIdentifier === undefined
  );
}

/** Android draws the buttons; iOS needs the category to exist before the push. */
export const SUPPORTS_LOCK_SCREEN_ACTIONS = Platform.OS === 'android' || Platform.OS === 'ios';
