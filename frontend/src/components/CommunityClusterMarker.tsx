/**
 * A community report cluster on the map, drawn so it cannot be mistaken for a flag.
 *
 * B13. This component exists because of Defect 54's second half: the map drew crime
 * reports and risk flags as the same kind of pin, *"which makes them look
 * interchangeable"* — and they are not interchangeable at all. A flag is the
 * product's own mobility claim, from edited sources. A cluster is a count of what
 * residents reported. Presenting them alike invites a user to trust the second as
 * much as the first.
 *
 * ## The channels, and why they are the ones they are
 *
 * `RiskFlagMarker` has already spent three: colour on severity, fill and ring style
 * on verification, shape (square) on scheduled. So:
 *
 * ```
 *   risk flag, confirmed       (3)  round,  filled, solid ring
 *   risk flag, unconfirmed      ?   round,  hollow, dashed ring
 *   risk flag, scheduled       [3]  square
 *   cluster, corroborated     ((3))  PILL,  filled, solid ring
 *   cluster, provisional      ((2))  PILL,  hollow, dashed ring
 * ```
 *
 * **Shape separates the two object families**: a wide pill against a 26px round dot
 * is distinguishable at a glance, at any zoom, and on a projector with the contrast
 * wound down. A pill also reads as a *label* rather than a *pin*, which is the right
 * implication — a cluster is a statement about a stretch, not a point.
 *
 * **Fill and ring keep meaning exactly what they mean on a flag**: solid is
 * corroborated, dashed is not. One grammar across both families, so the rule a user
 * learns from the news layer transfers to this one for free. Inventing a second
 * language for the same distinction would be the real inconsistency.
 *
 * **Colour is the accent, not a severity band.** Flags are coloured by
 * `riskBand(severityNow)`; a cluster deliberately is not, and that is a claim about
 * what the product knows. A severity band on a cluster would imply the app has
 * graded how bad a place is from a handful of reports. It has not, and
 * `app/policy/community.py::severity_for` says so: severity comes from the reporter
 * count alone and is capped well below a live event, precisely so it cannot be read
 * as a measurement. One accent colour, one meaning: people reported things here.
 *
 * ## `tracksViewChanges`
 *
 * Same race and same fix as `RiskFlagMarker` — see the long note there. Markers with
 * React children re-rasterise on every parent render unless tracking is off, but
 * starting with it off can freeze a half-drawn bitmap on Android. Track until laid
 * out and drawn, then stop, with a timeout as the backstop.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Marker } from 'react-native-maps';

import { useTheme } from '../theme/ThemeProvider';
import { useStyles } from '../theme/useStyles';
import type { Palette } from '../theme/palette';
import { fontFamily } from '../theme/type';
import type { CommunityCluster } from '../types/contracts/community';

export interface CommunityClusterMarkerProps {
  cluster: CommunityCluster;
  onPress: (cluster: CommunityCluster) => void;
}

/** The one place that decides what "corroborated" looks like for a cluster. */
export const isCorroboratedCluster = (cluster: CommunityCluster): boolean =>
  cluster.status === 'corroborated';

const CommunityClusterMarkerComponent: React.FC<CommunityClusterMarkerProps> = ({
  cluster,
  onPress,
}) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const corroborated = isCorroboratedCluster(cluster);

  const [tracking, setTracking] = useState(true);
  const settled = useRef(false);

  const settle = useCallback(() => {
    if (settled.current) return;
    settled.current = true;
    requestAnimationFrame(() => requestAnimationFrame(() => setTracking(false)));
  }, []);

  useEffect(() => {
    const timer = setTimeout(settle, 1_000);
    return () => clearTimeout(timer);
  }, [settle]);

  // The published sentence, verbatim. Never rebuilt here: the wording is produced by
  // `to_cluster_statement` and checked by the framing guard, and a client that
  // composed its own would be free to call a place dangerous.
  const title = cluster.statement;

  // "2 of 3 reports" would be wrong -- `reportCount` is the total and
  // `reporterCount` the distinct people. Spelling out both is what stops ten
  // reports from two accounts reading as ten witnesses.
  const people = cluster.reporterCount === 1 ? 'person' : 'people';
  const extra =
    cluster.reportCount > cluster.reporterCount
      ? ` from ${cluster.reportCount} reports`
      : '';

  return (
    <Marker
      coordinate={{ latitude: cluster.lat, longitude: cluster.lon }}
      title={title}
      description={`${cluster.reporterCount} ${people}${extra} · ${
        corroborated ? 'independently corroborated' : 'not yet corroborated'
      }`}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={tracking}
      onPress={() => onPress(cluster)}
      accessibilityLabel={`Community reports. ${title} ${
        corroborated
          ? `Independently corroborated by ${cluster.reporterCount} people.`
          : `Reported by ${cluster.reporterCount} people, not yet corroborated.`
      }`}
    >
      <View
        onLayout={settle}
        style={[
          styles.pill,
          {
            backgroundColor: corroborated ? t.accent : t.surface,
            borderColor: t.accent,
            borderStyle: corroborated ? 'solid' : 'dashed',
          },
        ]}
      >
        <Text
          style={[styles.label, { color: corroborated ? t.onBrand : t.accent }]}
          allowFontScaling={false}
        >
          {/* The reporter count, not the report count. It is the number that decided
              the tier, and the only one that is evidence about the place rather than
              about how much one person typed. */}
          {cluster.reporterCount}
        </Text>
      </View>
    </Marker>
  );
};

/**
 * Memoised on the fields that change the drawing, like `RiskFlagMarker`.
 *
 * `severityNow` is deliberately **absent** from the comparison, where the flag
 * marker rounds and compares it: a cluster is not coloured by severity, so a change
 * to it alters nothing on screen. Including it would re-rasterise every cluster on
 * every `as of` tap for no visual difference.
 */
export const CommunityClusterMarker = React.memo(
  CommunityClusterMarkerComponent,
  (prev, next) =>
    prev.cluster.clusterId === next.cluster.clusterId &&
    prev.cluster.status === next.cluster.status &&
    prev.cluster.reporterCount === next.cluster.reporterCount &&
    prev.cluster.reportCount === next.cluster.reportCount &&
    prev.onPress === next.onPress,
);

const makeStyles = (_t: Palette) =>
  StyleSheet.create({
    pill: {
      // Wider than tall, and wider than the 26px flag dot. The aspect ratio is the
      // channel doing the work here, so it has to survive a single-digit count.
      minWidth: 40,
      height: 24,
      paddingHorizontal: 8,
      borderRadius: 12,
      borderWidth: 2,
      alignItems: 'center',
      justifyContent: 'center',
    },
    label: {
      fontFamily: fontFamily.bodySemi,
      fontSize: 12,
      // Room above the baseline: a bare lineHeight equal to fontSize clips on
      // Android. Same fix as the flag marker's label.
      lineHeight: 15,
    },
  });

export default CommunityClusterMarker;
