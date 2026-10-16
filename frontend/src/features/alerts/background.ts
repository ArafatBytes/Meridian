/**
 * Getting a notification onto a phone that Android has decided to put to sleep.
 *
 * ## What this is for
 *
 * Android's Cached App Freezer suspends an app's process once it has been in the
 * background for a while. `expo-notifications` composes an incoming push
 * **inside the app process** rather than handing FCM a notification payload for
 * the system tray to draw, so a frozen app means a message that arrives at the
 * device and then waits. Waking the phone thaws the process and the notification
 * appears at that moment — which makes the buzz look like a consequence of
 * picking the phone up, because it is one.
 *
 * It was found on a device, on the fifth run of `docs/walkthroughs/JG2.md`:
 *
 *     18:51:15  D/ActivityManager: freezing 13857 com.Meridian.app
 *
 * and measured both ways. Whitelisted, with the screen off and the device
 * reporting `mWakefulness=Dreaming` throughout, a push posted in **five
 * seconds**. Not whitelisted, it never posted until the screen came on.
 *
 * ## Why it matters more here than in most apps
 *
 * For a road alert, late is a nuisance. For JG2 it is the whole feature: the
 * claim is that the clock lives on the server and asks whether you arrived even
 * if the phone is in a pocket and the app has been force-stopped. A check-in
 * that only fires when you happen to look at the screen is not that. It is a
 * reminder you find later, and JOURNEY_GUARDIAN.md §5's whole point is the case
 * where nobody is looking at the screen.
 *
 * ## What was ruled out first
 *
 * Neither of the two usual explanations. The app's App Standby bucket was `10`
 * (active), so the bucket throttle was not involved; and `alerts/expo.py`
 * already sends `priority: "high"`, which is what asks FCM to deliver through
 * Doze. Both were checked on the device before this module existed, and it is
 * worth writing down because "raise the priority" is the first thing anybody
 * will suggest and it is already as high as it goes.
 *
 * ## The honest cost
 *
 * This asks the user to exempt the app from battery optimisation, which is a
 * real thing to ask for and not a free win — it is the permission dialog most
 * associated with apps that abuse it. Three things keep it defensible:
 *
 * * **It is asked for a reason the user can check.** The screen says what breaks
 *   without it, and `Send me a test alert` is on the same screen.
 * * **It is never asked at startup.** It lives behind the diagnosis on the
 *   alerts screen, offered when the device reports the exemption is missing, and
 *   it is skipped entirely on a phone that already has it.
 * * **It is not required for the app to work.** Everything degrades to the
 *   journey card, which is the same fallback the notification has always had.
 *
 * Google Play restricts `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` to apps whose
 * core function needs it, and names "alarms, timers and messaging" among the
 * acceptable cases. A journey deadline that asks whether somebody arrived is
 * squarely that. If a review ever disagrees, `openBatterySettings` is the
 * fallback that needs no permission and costs the user two extra taps.
 */

import { Platform } from 'react-native';
import * as Battery from 'expo-battery';
import * as IntentLauncher from 'expo-intent-launcher';
import Constants from 'expo-constants';

/**
 * Whether Android is allowed to freeze this app, or `null` where the question
 * does not apply.
 *
 * `null` rather than `false` off Android, and `null` rather than a guess when
 * the query throws. The three answers are acted on differently: `true` offers
 * the fix, `false` says nothing, and `null` also says nothing — because telling
 * an iPhone user to go and find an Android battery setting, or guessing wrong
 * and nagging somebody who has already granted it, are both worse than staying
 * quiet. Everything downstream treats `null` as "do not raise this".
 */
export async function isBatteryOptimized(): Promise<boolean | null> {
  if (Platform.OS !== 'android') return null;
  try {
    return await Battery.isBatteryOptimizationEnabledAsync();
  } catch {
    // Never throws upward. This is one line in a diagnosis panel; it has no
    // business taking the screen down with it.
    return null;
  }
}

/**
 * Ask Android to stop freezing the app. Opens the system dialog.
 *
 * Returns whether a screen was opened, not whether the user said yes — the
 * intent reports nothing about the choice, and there is no callback. The caller
 * re-reads `isBatteryOptimized` when the app comes back to the foreground, which
 * is the only answer that can be trusted anyway: the user may have granted it,
 * refused it, or walked away.
 *
 * `applicationId` from `expo-constants` rather than a hardcoded
 * `com.Meridian.app`. The direct request intent needs the package as its data
 * URI, and a wrong one silently opens the dialog for nothing, or for somebody
 * else's app.
 */
export async function requestBackgroundDelivery(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  const pkg = Constants.expoConfig?.android?.package;
  try {
    if (pkg) {
      await IntentLauncher.startActivityAsync(
        IntentLauncher.ActivityAction.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
        { data: `package:${pkg}` },
      );
      return true;
    }
  } catch {
    // Falls through to the settings list below. The direct dialog needs the
    // REQUEST_IGNORE_BATTERY_OPTIMIZATIONS permission and an OEM that honours
    // it; where it is refused, the list still gets the user there.
  }
  return openBatterySettings();
}

/**
 * The battery-optimisation list, for every phone where the one-tap dialog is
 * not available. Needs no permission.
 */
export async function openBatterySettings(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  try {
    await IntentLauncher.startActivityAsync(
      IntentLauncher.ActivityAction.IGNORE_BATTERY_OPTIMIZATION_SETTINGS,
    );
    return true;
  } catch {
    return false;
  }
}

/*
 * The sentence shown when this is missing lives in
 * `types/contracts/notifications.ts::blockingPushProblem`, with the other eight.
 * It is not here beside the check, which would keep the condition and its copy
 * together — but push has nine ways to be broken and showing four complaints at
 * once gets all four ignored, so they have to be ordered against each other in
 * one place. Splitting one of the nine out would be the first step to a screen
 * that contradicts itself.
 */
