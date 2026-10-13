/**
 * Your position, snapped to the route.
 *
 * A component of its own rather than four lines inside `MapScreen`, because it
 * needs the same `tracksViewChanges` dance `RiskFlagMarker` does — and the first
 * version of this did not, which was a bug.
 *
 * ## The bug this file exists to not have
 *
 * A `Marker` with React children takes its bitmap from the child view on a native
 * draw pass. With `tracksViewChanges={false}` from the first render, that snapshot
 * can happen **before the child has drawn**, and what gets frozen is a blank
 * circle. `RiskFlagMarker` has the long version of this note; it is the same race.
 *
 * It is worse here than there. A flag marker's `key` includes the fields that
 * change its appearance, so React replaces it on the next `as of` tap and the
 * replacement mounts into a map that is already drawing — the blank recovers by
 * itself. This marker has no such key: there is one of it, its content never
 * changes, and only its coordinate moves. A blank snapshot would therefore stay
 * blank for the entire walk, and the symptom is the route trimming perfectly with
 * no dot anywhere on it.
 *
 * So: track until the view has been laid out and drawn, then stop. Stopping still
 * matters — the map re-renders on every fix while following, which is exactly the
 * case `tracksViewChanges` exists for — and a position change does not need a
 * re-rasterisation, only a move.
 *
 * ## Why it is drawn at all, next to the platform's own dot
 *
 * `showsUserLocation` already draws the raw fix. This is the *snapped* position,
 * which is what every number in the banner is measured from. Drawing both is
 * deliberate: when they disagree, the gap between them is the honest explanation
 * for a reading that looks wrong, and it is the only way a user can see that their
 * GPS is the problem rather than the app.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Marker } from 'react-native-maps';

import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import type { LatLng } from './progress';

export interface FollowMarkerProps {
  /** The snapped position. Moves on every accepted fix. */
  coordinate: LatLng;
}

export const FollowMarker: React.FC<FollowMarkerProps> = ({ coordinate }) => {
  const styles = useStyles(makeStyles);

  // True until the dot has been drawn, then false forever. See the note above.
  const [tracking, setTracking] = useState(true);
  const settled = useRef(false);

  const settle = useCallback(() => {
    if (settled.current) return;
    settled.current = true;
    // Two frames, not one. `onLayout` fires when React Native has measured the
    // view; the native marker copies it on the following draw. Stopping in the
    // same tick can beat that draw and freeze the half-painted bitmap, which is
    // the whole defect.
    requestAnimationFrame(() => requestAnimationFrame(() => setTracking(false)));
  }, []);

  useEffect(() => {
    // The backstop, for the case where `onLayout` never arrives. Without it a
    // marker that failed to lay out would track forever, re-rasterising on every
    // fix for the length of the walk.
    const timer = setTimeout(settle, 1_000);
    return () => clearTimeout(timer);
  }, [settle]);

  return (
    <Marker
      coordinate={coordinate}
      anchor={{ x: 0.5, y: 0.5 }}
      flat
      tracksViewChanges={tracking}
      title="You, on the route"
      zIndex={20}
    >
      <View onLayout={settle} style={styles.outer}>
        <View style={styles.inner} />
      </View>
    </Marker>
  );
};

const makeStyles = (t: Palette) =>
  StyleSheet.create({
    /**
     * A brand dot with a white collar.
     *
     * A collar rather than a shadow, because the platform draws its own blue dot in
     * the same place and the two have to be separable at a glance — one is where the
     * phone thinks you are, the other is where that puts you on the route.
     */
    outer: {
      width: 22,
      height: 22,
      borderRadius: 11,
      backgroundColor: '#FFFFFF',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: [{ offsetX: 0, offsetY: 1, blurRadius: 3, color: t.shadow }],
    },
    inner: {
      width: 14,
      height: 14,
      borderRadius: 7,
      backgroundColor: t.brand,
    },
  });

export default FollowMarker;
