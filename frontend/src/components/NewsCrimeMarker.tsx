/**
 * A crime reported by a named news publisher, drawn so it cannot be mistaken for
 * any of the other three things on this map.
 *
 * S30. The map now carries four families of object, and Defect 54 is the log of
 * what happens when two of them look alike: *"which makes them look
 * interchangeable"*. With four, the shape vocabulary has to be spent deliberately.
 *
 * ```
 *   risk flag, confirmed       (3)   round,   filled, solid ring
 *   risk flag, unconfirmed      ?    round,   hollow, dashed ring
 *   risk flag, scheduled       [3]   square
 *   cluster, corroborated     ((3))  pill,    filled, solid ring
 *   cluster, provisional      ((2))  pill,    hollow, dashed ring
 *   news crime, corroborated   <>    DIAMOND, filled, solid ring   <- this file
 *   news crime, published      <>    DIAMOND, hollow, dashed ring
 * ```
 *
 * **Shape separates the families.** A diamond is a 45°-rotated square, which is
 * distinguishable from a circle and from an upright square at a glance and at any
 * zoom — and critically it is still distinguishable in a photograph of a projector
 * screen, which is how this will be judged.
 *
 * **Fill and ring keep meaning exactly what they mean on the other two**: solid is
 * corroborated, dashed is not. One grammar across all three published families, so
 * the rule a user learns from the news layer transfers here for free.
 *
 * ## Colour means category here, and severity on a flag. That is deliberate.
 *
 * A flag is coloured by `riskBand(severityNow)`. A cluster is one accent colour
 * and deliberately not banded, because grading a place from a handful of anonymous
 * reports is a claim the product does not make.
 *
 * This is coloured by **category**, through the same `CRIME_COLORS` the user's own
 * reports use. The reasoning is the cluster's, applied to a different fact: what
 * was reported is a checkable fact about a published article, so the marker may
 * say it. *How bad this place is* is not, so the marker does not band it. Sharing
 * the palette with the user's own reports also means one colour has one meaning
 * across the whole app — purple is harassment wherever you see it.
 *
 * ## The callout says who, because that is the licence
 *
 * `title` is `incident.statement`, verbatim, which always names the publisher —
 * `app/policy/attribution.py` is its only writer and a database CHECK refuses any
 * statement without a publisher in it. **Never rebuild that sentence here.** A
 * sentence composed from `category` alone would be this app asserting that a crime
 * occurred, which is exactly what it has no standing to do, and it would discard
 * the one thing that makes naming the offence defensible.
 *
 * ## `tracksViewChanges`
 *
 * Same race and same fix as `RiskFlagMarker` and `CommunityClusterMarker` — see
 * the long note in the first of those. Track until laid out and drawn, then stop,
 * with a timeout as the backstop.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Marker } from 'react-native-maps';

import { useTheme } from '../theme/ThemeProvider';
import { useStyles } from '../theme/useStyles';
import type { Palette } from '../theme/palette';
import { fontFamily } from '../theme/type';
import { crimeCategoryLabel, crimeColor } from '../types/contracts/crime';
import type { NewsCrimeIncident } from '../types/contracts/newsCrime';

export interface NewsCrimeMarkerProps {
  incident: NewsCrimeIncident;
  onPress: (incident: NewsCrimeIncident) => void;
}

/** The one place that decides what "corroborated" looks like for a news crime. */
export const isCorroboratedNewsCrime = (incident: NewsCrimeIncident): boolean =>
  incident.status === 'corroborated';

const NewsCrimeMarkerComponent: React.FC<NewsCrimeMarkerProps> = ({
  incident,
  onPress,
}) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const corroborated = isCorroboratedNewsCrime(incident);
  const accent = crimeColor(incident.category);

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

  // The published sentence, verbatim. It names the publisher; that is the licence.
  const title = incident.statement;

  const publishers =
    incident.sourceCount === 1
      ? 'One publisher'
      : `${incident.sourceCount} independent publishers`;

  return (
    <Marker
      coordinate={{ latitude: incident.lat, longitude: incident.lon }}
      title={title}
      description={`${publishers} · tap for the source`}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={tracking}
      onPress={() => onPress(incident)}
      accessibilityLabel={`Reported in the news. ${title}. ${publishers}.`}
    >
      {/* The rotation is on an OUTER wrapper, and the glyph counter-rotates inside
          it. Rotating the view that holds the text would tip the letter 45° too,
          which is unreadable at 11pt. */}
      <View
        onLayout={settle}
        style={[
          styles.diamond,
          {
            backgroundColor: corroborated ? accent : t.surface,
            borderColor: accent,
            borderStyle: corroborated ? 'solid' : 'dashed',
          },
        ]}
      >
        <Text
          style={[styles.glyph, { color: corroborated ? t.onBrand : accent }]}
          allowFontScaling={false}
        >
          {/* One letter of the category, not a count. A count here would be the
              number of newspapers, which reads as a number of incidents — the
              exact confusion the cluster marker avoids by showing reporters
              rather than reports. */}
          {crimeCategoryLabel(incident.category).charAt(0).toUpperCase()}
        </Text>
      </View>
    </Marker>
  );
};

/**
 * Memoised on the fields that change the drawing.
 *
 * `severityNow` is deliberately absent, as on `CommunityClusterMarker`: this
 * marker is not coloured by severity, so a change to it alters nothing on screen
 * and including it would re-rasterise every incident on every `as of` tap.
 */
export const NewsCrimeMarker = React.memo(
  NewsCrimeMarkerComponent,
  (prev, next) =>
    prev.incident.incidentId === next.incident.incidentId &&
    prev.incident.status === next.incident.status &&
    prev.incident.category === next.incident.category &&
    prev.incident.sourceCount === next.incident.sourceCount &&
    prev.onPress === next.onPress,
);

const makeStyles = (_t: Palette) =>
  StyleSheet.create({
    diamond: {
      width: 24,
      height: 24,
      borderRadius: 4,
      borderWidth: 2,
      alignItems: 'center',
      justifyContent: 'center',
      // The channel that separates this family from the round flags and the wide
      // cluster pills. A small corner radius keeps the points from aliasing into
      // fuzz at low zoom while still reading as a diamond rather than a circle.
      transform: [{ rotate: '45deg' }],
    },
    glyph: {
      fontSize: 11,
      fontFamily: fontFamily.bodySemi,
      // Cancels the parent's rotation so the letter sits upright inside the
      // diamond. Without it the glyph is tipped 45° and unreadable.
      transform: [{ rotate: '-45deg' }],
    },
  });

export default NewsCrimeMarker;
