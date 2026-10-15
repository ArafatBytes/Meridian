/**
 * Android notification channels. B6a / S16.
 *
 * A channel id is a contract between two codebases that never speak to each
 * other at build time. The backend puts `channelId` on every message it sends to
 * Expo (`app/alerts/compose.py` → `PushMessage.channel_id`); Android looks the id
 * up among the channels this app created at startup. If they disagree, **Android
 * does not error** — it files the notification under a fallback channel with
 * default importance, no custom sound and no vibration pattern.
 *
 * That is the worst kind of bug: the notification arrives, so the walkthrough
 * passes, and the thing that was lost is the urgency the channel existed to
 * carry. Nothing in either codebase reports it.
 *
 * So the ids live here, in one file, and
 * `backend/tests/invariants/test_alert_channels_match_the_client.py` reads this
 * file and asserts the backend only ever names an id that appears in it. A
 * rename on either side fails that test by name.
 *
 * ## Why a channel per urgency and not per kind
 *
 * Android channel settings are user-controllable and permanent: once someone
 * turns a channel down, the app cannot turn it back up — by design, and it is a
 * good design. That makes the channel split a promise about what the user is
 * choosing between.
 *
 * Three channels, cut by what somebody would plausibly want to silence
 * separately:
 *
 * - `risk_alert` — a road is affected near you. The product's core output.
 * - `sos_alert`  — you or someone who named you pressed the button. Maximum
 *                  importance, and never shares a channel with anything else:
 *                  a user who silences routine alerts must not silence this.
 * - `system`     — delivery tests and housekeeping. Low importance, because
 *                  somebody turning off test notifications after a walkthrough
 *                  must not be turning off real warnings at the same time.
 * - `journey_check_in` — JG2. "Are you there yet?" on a journey whose deadline
 *                  passed. Its own channel for the same reason the others are
 *                  split: somebody who silences road alerts after a noisy week
 *                  must not discover they have also silenced the question that
 *                  asks whether they got home. HIGH, not MAX — it is a question,
 *                  not an emergency, and borrowing the SOS channel would train
 *                  people to ignore that one.
 *
 * ## What was removed, and why
 *
 * `danger_zone` and `crime_report` were two of the four inherited channels. Both
 * are gone.
 *
 * `danger_zone` is the framing the product abandoned. Concept document §9
 * commits to describing effects on movement and never characterising a place as
 * dangerous, and an Android channel is a *user-visible string* — it appears in
 * the system settings list under the app's name. Shipping one called "Danger
 * Zone Alerts" would put the one word the product does not say into the OS
 * settings screen, where no amount of care in `framing.py` can reach it.
 *
 * `crime_report` had no sender and never did.
 */

import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

/**
 * The channel ids, as both sides spell them.
 *
 * `as const` so the values are literal types rather than `string` — a typo in a
 * call site becomes a compile error instead of a notification quietly landing on
 * the fallback channel.
 */
export const ALERT_CHANNELS = {
  RISK: 'risk_alert',
  SOS: 'sos_alert',
  SYSTEM: 'system',
  JOURNEY: 'journey_check_in',
} as const;

export type AlertChannelId = (typeof ALERT_CHANNELS)[keyof typeof ALERT_CHANNELS];

/** Every id, for the contract test and for iteration. */
export const ALL_CHANNEL_IDS: readonly AlertChannelId[] = Object.values(ALERT_CHANNELS);

interface ChannelSpec {
  id: AlertChannelId;
  /** Shown to the user in Android's notification settings. Read it as copy. */
  name: string;
  /** Also shown there, under the name. Worth writing properly. */
  description: string;
  importance: Notifications.AndroidImportance;
  vibrationPattern?: number[];
  /**
   * A **custom** sound filename from `res/raw`, or omitted for the system default.
   *
   * There is no string that means "default" here, and getting this wrong is
   * noisy rather than silent. `NotificationChannelInput.sound` is typed
   * `string | null`, and Android treats **any** string as a filename to look
   * up — so `sound: 'default'` made it hunt for a file called "default" and log
   * on every app start:
   *
   *     ERROR  expo-notifications: Custom sound 'default' not found in native app.
   *
   * What misled me is the *read-back* type, `'default' | 'custom' | null`:
   * that is what Android **reports** a channel's sound as, not what it accepts.
   *
   * Omit the key for the default. To use a real custom sound, put the .wav in
   * `assets/sounds/`, add it to the expo-notifications plugin's `sounds` array
   * in app.json, rebuild, and only then name it here.
   */
  sound?: string;
}

/**
 * The channels this app creates at startup.
 *
 * `HIGH` rather than `MAX` for risk alerts. `MAX` asks Android to take over the
 * screen with a heads-up notification, interrupting whatever the person is
 * doing. That is reserved for `sos_alert`, where somebody has pressed a button
 * and expects to be interrupted. A road being blocked is important and is not
 * that — and a product that treats every alert as maximum urgency is the one
 * people disable.
 */
const CHANNELS: readonly ChannelSpec[] = [
  {
    id: ALERT_CHANNELS.RISK,
    name: 'Road and route alerts',
    description:
      'Something affecting movement near where the app last had your location, ' +
      'or expected later today.',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
    // No `sound`: that selects Android's default notification sound. See ChannelSpec.
  },
  {
    id: ALERT_CHANNELS.JOURNEY,
    name: 'Journey check-ins',
    description:
      'Asks whether you arrived, when a journey you started passes the time you ' +
      'gave it. One tap answers it.',
    importance: Notifications.AndroidImportance.HIGH,
    // Longer than the risk pattern and distinctly two-part, because this one is
    // meant to be recognisable in a pocket without looking: the whole feature is
    // "you feel it, you tap it, you carry on". Not MAX importance -- see the
    // channel notes above.
    vibrationPattern: [0, 400, 200, 400],
    // No `sound`: Android's default notification sound. See ChannelSpec for why
    // there is no string that means "default".
  },
  {
    id: ALERT_CHANNELS.SOS,
    name: 'Emergency SOS',
    description:
      'An emergency alert you triggered, or one raised by someone who listed you ' +
      'as their contact. Keep this on.',
    importance: Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 300, 500, 300, 500],
    // No `sound`: Android's default notification sound. See ChannelSpec for why
    // there is no string that means "default".
    //
    // A distinct sound would genuinely be worth having for SOS. app.json named
    // `sos_alert.wav` in the expo-notifications plugin's `sounds` array from D01
    // onward and **the file never existed** -- nor did the other four assets it
    // named. Nothing caught it because config plugins only run during `prebuild`,
    // and this app had only ever run in Expo Go, which ignores the plugins block
    // entirely. The first prebuild failed on it.
  },
  {
    id: ALERT_CHANNELS.SYSTEM,
    name: 'App status',
    description: 'Delivery tests and occasional notices about the app itself.',
    importance: Notifications.AndroidImportance.LOW,
  },
];

/**
 * Create every channel. Safe to call repeatedly.
 *
 * `setNotificationChannelAsync` is an upsert, so this runs on every launch and
 * is how a changed importance or description reaches an existing install.
 *
 * One caveat worth knowing before wondering why an edit here did nothing: once
 * the user has adjusted a channel themselves, Android keeps *their* importance
 * and ignores ours. Only the name and description update. That is deliberate on
 * Android's part and we do not work around it.
 *
 * iOS has no channels; the call is skipped rather than guarded at each call site.
 */
export async function createAlertChannels(): Promise<void> {
  if (Platform.OS !== 'android') return;

  await Promise.all(
    CHANNELS.map(channel =>
      Notifications.setNotificationChannelAsync(channel.id, {
        name: channel.name,
        description: channel.description,
        importance: channel.importance,
        vibrationPattern: channel.vibrationPattern,
        enableVibrate: Boolean(channel.vibrationPattern),
        sound: channel.sound,
      }),
    ),
  );
}

/**
 * Which channel a received notification belongs to, from its `data.type`.
 *
 * Used for locally-presented notifications, where the app is both sender and
 * receiver. Remote pushes carry `channelId` from the backend and never reach
 * this.
 *
 * Defaults to `SYSTEM` rather than `RISK` on an unrecognised type. An unknown
 * notification is more likely to be a stale payload from an older build than a
 * genuine warning, and guessing "urgent" would be the wrong way to be wrong.
 */
export function channelForType(type: string | undefined): AlertChannelId {
  switch (type) {
    case 'risk_alert':
      return ALERT_CHANNELS.RISK;
    case 'sos_alert':
      return ALERT_CHANNELS.SOS;
    default:
      return ALERT_CHANNELS.SYSTEM;
  }
}
