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
 *   scheduled     [3]   square rather than round — a claim about a future window
 * ```
 *
 * Two independent channels carry the confirmed/unconfirmed distinction — fill and
 * ring style — because one of them has to survive a projector with the contrast
 * wound down, and because colour alone already carries severity. A viewer who cannot
 * separate hues still sees solid-versus-hollow.
 *
 * **D09 adds scheduled, and it gets its own channel: shape.** Every other channel is
 * already spent — colour on severity, fill and ring on verification — so a
 * forward-dated flag is a rounded *square*. That matters because the two questions
 * are independent: a scheduled flag can be confirmed or unconfirmed exactly as a
 * live one can, and the map has to show both at once. Squareness says *when*,
 * fill says *whether*, colour says *how bad*.
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

import { useTheme } from '../theme/ThemeProvider';
import { useStyles } from '../theme/useStyles';
import type { Palette } from '../theme/palette';
import { fontFamily } from '../theme/type';
import type { RiskFlag } from '../types/contracts';
import { riskBand } from './RiskFlagSheet';
import { isScheduledFlag } from '../features/risk/scheduled';

export interface RiskFlagMarkerProps {
  flag: RiskFlag;
  onPress: (flag: RiskFlag) => void;
}

/** The one place that decides what "confirmed" looks like. */
export const isConfirmedFlag = (flag: RiskFlag): boolean => flag.status === 'confirmed';

const RiskFlagMarkerComponent: React.FC<RiskFlagMarkerProps> = ({ flag, onPress }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const band = riskBand(flag.severityNow);
  const confirmed = isConfirmedFlag(flag);
  const scheduled = isScheduledFlag(flag);

  return (
    <Marker
      coordinate={{ latitude: flag.lat, longitude: flag.lon }}
      title={flag.mobilityStatement}
      // The callout keeps saying it in words as well as in shape. Shape is faster to
      // read; words are what a screen reader and a long-press get.
      description={`${scheduled ? 'Scheduled · ' : ''}${band.label} · ${Math.round(
        flag.severityNow,
      )}/100 · ${
        confirmed ? `confirmed, ${flag.sourceCount} sources` : 'unconfirmed, 1 source'
      }`}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={false}
      onPress={() => onPress(flag)}
      accessibilityLabel={`${scheduled ? 'Scheduled. ' : ''}${flag.mobilityStatement}. ${
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
            backgroundColor: confirmed ? band.color : t.surface,
            borderColor: band.color,
            borderStyle: confirmed ? 'solid' : 'dashed',
            borderWidth: 2,
            // Square for scheduled. 7 rather than 0 so it still reads as a mark on
            // a map at this size instead of a rendering artefact.
            borderRadius: scheduled ? 7 : 13,
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
    prev.flag.validFrom === next.flag.validFrom &&
    Math.round(prev.flag.severityNow) === Math.round(next.flag.severityNow) &&
    prev.onPress === next.onPress,
);

const makeStyles = (t: Palette) =>
StyleSheet.create({
    dot: {
      width: 26,
      height: 26,
      borderRadius: 13,
      alignItems: 'center',
      justifyContent: 'center',
    },
    label: {
      fontFamily: fontFamily.bodySemi,
      fontSize: 12,
      // Bare `lineHeight` equal to fontSize clips the glyph on Android; a little room
      // and no vertical padding keeps the digit optically centred in the circle.
      lineHeight: 15,
    },
  });
