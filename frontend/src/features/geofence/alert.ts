/**
 * What a zone alert says, and the debounce that stops it saying it again.
 * B6a / S17.
 *
 * Pure except for the storage calls, and the text half is entirely pure so it
 * can be tested.
 *
 * ## The framing rule applies here too, and it is easier to break
 *
 * Concept document §9: the product describes effects on movement and never
 * characterises a place. A geofence notification is the hardest place to keep
 * that, because the obvious sentence writes itself — *"You are entering a
 * dangerous area"* — and it is exactly what the product must not say.
 *
 * So the body is **`flag.mobilityStatement`, forwarded verbatim**, plus one
 * fixed clause chosen from a constant table. The statement was written by
 * `backend/app/policy/framing.py`, which is the only producer of flag prose in
 * the system, and it arrives already guarded. Nothing here composes a sentence
 * about any location, and `alert.test.ts` asserts that mechanically by the same
 * residue method the backend's own invariant uses: strip the forwarded statement
 * and what is left must be identical for every zone.
 *
 * ## Why a local notification and not a push
 *
 * The detection happens on the phone — the OS wakes our task when a geofence is
 * crossed — so the phone can post the notification itself. Routing it through a
 * server and back would add Expo's push service, FCM credentials and an EAS
 * project to a path that needs none of them, and would fail whenever the phone
 * had no data signal. Which, for a safety alert, is precisely when it matters.
 */

import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

import { ALERT_CHANNELS } from '../alerts/channels';
import type { ZoneMeta } from './zones';

/**
 * How long before the same zone may alert again, in milliseconds.
 *
 * Six hours. Android reports a geofence entry every time the person crosses the
 * boundary, and somebody living or working beside a flagged corridor crosses it
 * repeatedly — walking to a shop and back is two crossings. Without a debounce
 * this feature becomes the reason they switch notifications off.
 *
 * Six rather than "once ever", because a flag's severity and its corroboration
 * both change over the day: a road that was a delay at noon can be impassable by
 * evening, and that is worth a second alert.
 */
export const ZONE_REALERT_AFTER_MS = 6 * 60 * 60 * 1000;

/**
 * The fixed clauses. The entire vocabulary of a zone alert.
 *
 * Keyed by verification tier, which is the only thing allowed to vary the text.
 * D05 made the confirmed/unconfirmed distinction visible on the map through fill
 * and ring style; a notification has no shape to vary, so it says it in words.
 */
const CONFIRMED_CLAUSE = 'Confirmed by {n} independent sources.';
const UNCONFIRMED_CLAUSE = 'Unconfirmed — a single source so far.';

/**
 * The proximity clause. One string, no interpolation.
 *
 * Not "you are 300 m away": a varying distance is text generated on the device
 * about a place, which is the thing this module does not do. The distance goes
 * in `data`, where the app can render it.
 */
const APPROACH_CLAUSE = 'You are approaching this area.';

export const ZONE_ALERT_TITLE = 'Risk zone ahead';

export interface ZoneAlertText {
  title: string;
  body: string;
}

/** The verification tier, in words. */
export function sourceClause(meta: Pick<ZoneMeta, 'status' | 'sourceCount'>): string {
  return meta.status === 'confirmed'
    ? CONFIRMED_CLAUSE.replace('{n}', String(meta.sourceCount))
    : UNCONFIRMED_CLAUSE;
}

/**
 * The alert for one zone.
 *
 * `statement` is forwarded, not rewritten. If it is somehow empty — a row edited
 * by hand, a contract change — the alert still goes out with the clauses alone
 * rather than being silently dropped: the person is near something flagged, and
 * saying so without detail beats saying nothing.
 */
export function composeZoneAlert(meta: ZoneMeta): ZoneAlertText {
  const parts = [meta.statement?.trim(), sourceClause(meta), APPROACH_CLAUSE].filter(
    (part): part is string => Boolean(part),
  );
  return { title: ZONE_ALERT_TITLE, body: parts.join(' ') };
}

/**
 * Post the notification for a zone crossing.
 *
 * `trigger: { channelId }` rather than `null`: expo-notifications treats that as
 * "deliver immediately, on this channel", and `null` is immediate but carries no
 * channel — which files the notification under Android's fallback channel with
 * default importance and no sound. That mistake was already made once on this
 * project, in the inherited `notification.service.ts`, where a correct
 * `getChannelId()` had no call sites at all.
 */
export async function presentZoneAlert(meta: ZoneMeta): Promise<void> {
  const { title, body } = composeZoneAlert(meta);
  await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: {
        type: 'risk_alert',
        source: 'geofence',
        flagId: meta.flagId,
        lat: meta.lat,
        lon: meta.lon,
        radiusM: meta.flagRadiusM,
        severity: Math.round(meta.severity),
        status: meta.status,
        sourceCount: meta.sourceCount,
      },
      // `true`, not 'default': a string here goes through Android's
      // custom-sound-filename lookup and logs a "not found" error.
      sound: true,
      priority: Notifications.AndroidNotificationPriority.HIGH,
      vibrate: [0, 250, 250, 250],
      badge: 1,
    },
    // iOS has no channels; Android needs the id or the channel is lost.
    trigger: Platform.OS === 'android' ? { channelId: ALERT_CHANNELS.RISK } : null,
  });
}
