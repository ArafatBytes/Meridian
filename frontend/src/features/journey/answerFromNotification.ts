/**
 * Answering the check-in without opening the app. JG2.
 *
 * `NotificationService` hands every notification response to one handler. This
 * is the part of that handler that belongs to Journey Guardian: if the response
 * is somebody answering a check-in, post the answer.
 *
 * ## Why this lives outside the screen
 *
 * `MapScreen` cannot do it. The whole point of the lock-screen button is that no
 * screen is mounted — the app may be backgrounded, or launched by the tap itself
 * — so a handler registered by a component would not exist at the moment it was
 * needed. It is registered from `App.tsx`'s startup path instead, next to the
 * other things that have to be alive before any screen is.
 *
 * ## What it does when it fails
 *
 * Logs, and nothing else. There is no screen to put a message on and no user
 * waiting for one: they tapped a button on a lock screen and put the phone back
 * in their pocket.
 *
 * That is a real limit and it is why the journey card carries the same button.
 * A failed answer leaves the journey at `check_in_sent`, so the sweep records a
 * non-response the person did not make — which in JG3 is what starts an
 * escalation. The mitigation is the card, which shows the question for as long
 * as it is outstanding and answers it through the same endpoint.
 */

import journeyService from '../../services/journey.service';
import type { AlertTap } from '../../services/notification.service';
import { isCheckInAnswer } from './checkIn';

/**
 * Handle one notification response. Returns whether it was a check-in answer.
 *
 * The boolean is for the caller to chain on — `App.tsx` registers one handler
 * and other features will want their own turn — and for the test, which has no
 * other way to see that a tap was recognised.
 */
export async function answerFromNotification(tap: AlertTap): Promise<boolean> {
  if (!isCheckInAnswer({ actionIdentifier: tap.actionIdentifier, type: tap.type })) {
    return false;
  }

  // A check-in notification always carries one. Its absence means the message
  // was composed by something other than `compose_check_in`, which is worth a
  // log line rather than a guess: answering "whatever journey is open" would be
  // the app vouching for a trip nobody asked about.
  if (!tap.journeyId) {
    console.warn('[journey] check-in response carried no journeyId');
    return false;
  }

  try {
    await journeyService.checkIn(tap.journeyId);
    return true;
  } catch (error: any) {
    // See the module note: there is nowhere to show this. The journey card is
    // the fallback, and it is still showing the question.
    console.warn('[journey] could not answer the check-in', error?.message);
    return false;
  }
}
