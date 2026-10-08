/**
 * A risk flag on the map, drawn so its verification tier is legible without tapping.
 *
 * D05. `DEMO_PLAN.md` asks for *"confirmed vs unconfirmed rendered differently on the
 * map — not just a field in a sheet. The tiering is an ethical commitment; it should
 * be legible at a glance."* So:
 *
 * ```
 *   confirmed     (3)   filled, solid ring, source count in white
 *   unconfirmed    ?    hollow, dashed ring, question mark
 * ```
 *
 * Two independent channels carry the same distinction — fill and ring style — because
 * one of them has to survive a projector with the contrast wound down, and because
 * colour alone already carries severity. A viewer who cannot separate hues still sees
 * solid-versus-hollow.
 *
 * ## Why this replaces `pinColor`
 *
 * A native `Marker` with `pinColor` can express exactly one variable, and D04 had
 * already spent it on severity. There is nowhere left to put the tier, let alone the
 * source count. The teardrop also implies a point, and a flag is a claim about an
 * *area* — the radius circle is the honest part of the drawing, so a small dot sitting
 * at its centre reads better than a pin planted in it.
 *
 * ## `tracksViewChanges={false}` is not optional
 *
 * A `Marker` with React children re-rasterises its view on **every** parent render
 * unless this is set, and the map re-renders on pan, zoom, and every `as of` tap. With
 * ~60 flags in view that is tens of thousands of needless bitmap conversions and the
 * map visibly stutters on a phone.
 *
 * The cost of turning it off: the marker image is snapshotted once, so later prop
 * changes do not repaint it. That is handled by `key` — it includes the fields that
 * change the drawing, so React replaces the marker instead of mutating it. Anything
 * added to this component's appearance must also be added to that key.
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Marker } from 'react-native-maps';

import { colors } from '../theme';
import type { RiskFlag } from '../types/contracts';
import { riskBand } from './RiskFlagSheet';

export interface RiskFlagMarkerProps {
  flag: RiskFlag;
  onPress: (flag: RiskFlag) => void;
}

/** The one place that decides what "confirmed" looks like. */
export const isConfirmedFlag = (flag: RiskFlag): boolean => flag.status === 'confirmed';

const RiskFlagMarkerComponent: React.FC<RiskFlagMarkerProps> = ({ flag, onPress }) => {
  const band = riskBand(flag.severityNow);
  const confirmed = isConfirmedFlag(flag);

  return (
    <Marker
      coordinate={{ latitude: flag.lat, longitude: flag.lon }}
      title={flag.mobilityStatement}
      // The callout keeps saying it in words as well as in shape. Shape is faster to
      // read; words are what a screen reader and a long-press get.
      description={`${band.label} · ${Math.round(flag.severityNow)}/100 · ${
        confirmed ? `confirmed, ${flag.sourceCount} sources` : 'unconfirmed, 1 source'
      }`}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={false}
      onPress={() => onPress(flag)}
      accessibilityLabel={`${flag.mobilityStatement}. ${
        confirmed
          ? `Confirmed by ${flag.sourceCount} independent sources.`
          : 'Unconfirmed, a single source.'
      }`}
    >
      <View
        style={[
          styles.dot,
          {
            // Hollow for unconfirmed: the claim is lighter, so the mark is lighter.
            backgroundColor: confirmed ? band.color : colors.surface,
            borderColor: band.color,
            borderStyle: confirmed ? 'solid' : 'dashed',
            borderWidth: 2,
          },
        ]}
      >
        <Text
          style={[styles.label, { color: confirmed ? '#FFFFFF' : band.color }]}
          allowFontScaling={false}
        >
          {/* The source count is the thing beat 2 is about, so it goes on the pin
              rather than only in the sheet. A `?` for unconfirmed rather than "1":
              the number is not the point, the absence of corroboration is. */}
          {confirmed ? flag.sourceCount : '?'}
        </Text>
      </View>
    </Marker>
  );
};

/**
 * Memoised, and the comparison is explicit.
 *
 * `riskFlags` is rebuilt on every refresh and every `as of` change, so without this
 * all ~60 markers reconcile on each one. Only the fields that change the drawing are
 * compared — `severityNow` through its rounded display value, since a change of
 * 0.004 does not alter a single pixel.
 */
export const RiskFlagMarker = React.memo(
  RiskFlagMarkerComponent,
  (prev, next) =>
    prev.flag.flagId === next.flag.flagId &&
    prev.flag.status === next.flag.status &&
    prev.flag.sourceCount === next.flag.sourceCount &&
    Math.round(prev.flag.severityNow) === Math.round(next.flag.severityNow) &&
    prev.onPress === next.onPress,
);

const styles = StyleSheet.create({
  dot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    // Bare `lineHeight` equal to fontSize clips the glyph on Android; a little room
    // and no vertical padding keeps the digit optically centred in the circle.
    lineHeight: 15,
  },
});
