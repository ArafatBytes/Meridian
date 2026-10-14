/**
 * The navigation strip: which way to go, how far is left, and when it is wrong.
 *
 * Sits where the route comparison card sits, and replaces it while following —
 * because the two answer different questions and only one of them matters while
 * you are walking. The card is for *choosing* a route: three candidates, safety
 * scores, flag lists, a trade-off sentence. Once you have chosen and started
 * moving, all of that is settled, and the screen's whole job becomes "am I going
 * the right way". Keeping both on screen would leave the thing you need in a
 * sheet you have to expand one-handed, at night, while walking.
 *
 * ## It is deliberately four pieces of information
 *
 * An arrow, a turn, a distance and a time. Not a step list, not a street name, not
 * a lane diagram — `nextTurn` works from the route geometry and the backend does
 * not request OSRM `steps`, so nothing here knows what a road is called. Saying
 * "bear left in 120 m" is the whole of what the data supports, and a fabricated
 * street name in a navigation instruction would be the worst place in this app to
 * start inventing things.
 *
 * ## Why the off-route state has a button and not a behaviour
 *
 * The long version is in `useNavigation.ts`. The short version: the route being
 * followed was *chosen*, from a comparison that explained what it avoids, and
 * replacing it silently throws that away at the exact moment the user cannot look
 * at the screen. So off-route says so, plainly, and offers one tap.
 */

import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { Glass } from '../../components/motion';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { radius, space, type } from '../../theme/type';
import { formatDistance, formatDuration, type StepHint, type TurnHint } from './progress';
import { currentRoadName, instructionFor } from './instructions';
import type { NavigationPhase } from './useNavigation';

export interface NavigationBannerProps {
  phase: NavigationPhase;
  turn: TurnHint | null;
  /** OSRM's manoeuvre, when the route carries steps. Preferred over `turn`. */
  step: StepHint | null;
  /** True while an automatic re-route is in flight. */
  rerouting: boolean;
  remainingM: number;
  remainingSeconds: number;
  accuracyM: number | null;
  /** Distance from the clear bottom edge, so it stacks like the route card. */
  bottomInset: number;
  onRecalculate: () => void;
  onStop: () => void;
  recalculating?: boolean;
}

/** The arrow glyph for a turn. One channel, so it reads before the words do. */
const TURN_ICON: Record<TurnHint['direction'], string> = {
  straight: 'arrow-up',
  'slight left': 'arrow-up',
  left: 'arrow-back',
  'sharp left': 'return-down-back',
  'slight right': 'arrow-up',
  right: 'arrow-forward',
  'sharp right': 'return-down-forward',
};

export const NavigationBanner: React.FC<NavigationBannerProps> = ({
  phase,
  turn,
  step,
  rerouting,
  remainingM,
  remainingSeconds,
  accuracyM,
  bottomInset,
  onRecalculate,
  onStop,
  recalculating = false,
}) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);

  if (phase === 'idle') return null;

  const road = currentRoadName(step);
  const tone =
    phase === 'off-route' ? t.warn : phase === 'arrived' ? t.ok : t.brand;

  return (
    <Glass
      style={[styles.card, { bottom: bottomInset + space.lg }]}
      padding={space.lg}
      radius={radius.card}
      // No blur: this sits over the map, on a screen with no backdrop of its own,
      // and a blurred surface there resolves the screen-wide `ClaimBlurTarget` as
      // its blur target -- which makes the `BlurView` a descendant of the view it
      // blurs and overflows Android's render thread. See `BlurTarget.tsx`. It is
      // also the one surface on screen while the user is walking, so the per-frame
      // GPU cost would be the least affordable here of anywhere in the app.
      blur={false}
      elevated
    >
      {phase === 'locating' && (
        <View style={styles.row}>
          <ActivityIndicator size="small" color={t.brand} />
          <Text style={styles.finding}>Finding you on the route…</Text>
          <Pressable onPress={onStop} hitSlop={10} accessibilityLabel="Stop following">
            <Ionicons name="close" size={20} color={t.textSoft} />
          </Pressable>
        </View>
      )}

      {phase === 'arrived' && (
        <View style={styles.row}>
          <View style={[styles.badge, { backgroundColor: t.ok }]}>
            <Ionicons name="checkmark" size={22} color={t.onBrand} />
          </View>
          <View style={styles.grow}>
            <Text style={styles.instruction}>You have arrived</Text>
            <Text style={styles.meta}>Following stopped</Text>
          </View>
          <Pressable onPress={onStop} hitSlop={10} accessibilityLabel="Close">
            <Ionicons name="close" size={20} color={t.textSoft} />
          </Pressable>
        </View>
      )}

      {phase === 'off-route' && (
        <>
          <View style={styles.row}>
            <View style={[styles.badge, { backgroundColor: t.warn }]}>
              <Ionicons name="alert" size={22} color={t.onBrand} />
            </View>
            <View style={styles.grow}>
              <Text style={styles.instruction}>
                {rerouting ? 'Finding a new route' : 'You’re off this route'}
              </Text>
              {/* Says which of the two is happening rather than implying one. The
                  automatic re-route only fires after a sustained period off-route,
                  so there is a real window in which nothing is being recalculated
                  and claiming otherwise would be a lie. */}
              <Text style={styles.meta}>
                {rerouting
                  ? 'Routing from where you are now'
                  : `${formatDistance(remainingM)} left on the route you chose`}
              </Text>
            </View>
            <Pressable onPress={onStop} hitSlop={10} accessibilityLabel="Stop following">
              <Ionicons name="close" size={20} color={t.textSoft} />
            </Pressable>
          </View>
          <Pressable
            onPress={onRecalculate}
            disabled={recalculating || rerouting}
            style={[styles.action, { borderColor: t.warn }]}
            accessibilityRole="button"
            accessibilityLabel="Find a new route from where I am"
          >
            {recalculating || rerouting ? (
              <ActivityIndicator size="small" color={t.warn} />
            ) : (
              <Ionicons name="refresh" size={16} color={t.warn} />
            )}
            <Text style={[styles.actionText, { color: t.warn }]}>
              {recalculating || rerouting
                ? 'Finding a new route…'
                : 'Route from where I am'}
            </Text>
          </Pressable>
        </>
      )}

      {phase === 'following' && (
        <View style={styles.row}>
          <View style={[styles.badge, { backgroundColor: tone }]}>
            <Ionicons
              name={TURN_ICON[turn?.direction ?? 'straight']}
              size={24}
              color={t.onBrand}
              // Slight turns reuse the straight arrow, rotated, so a 30-degree
              // bend does not get the same glyph as a 90-degree one.
              style={
                turn?.direction === 'slight left'
                  ? { transform: [{ rotate: '-35deg' }] }
                  : turn?.direction === 'slight right'
                    ? { transform: [{ rotate: '35deg' }] }
                    : undefined
              }
            />
          </View>

          <View style={styles.grow}>
            {/* Two lines, not one. Dhaka road names are long -- "Jessore -
                Magura Highway", "Kazi Nazrul Islam Avenue" -- and on one line the
                instruction truncated to "Turn right onto Jessore - Mag...", which
                loses the only part the street name was added for. Two lines fits
                every name measured so far; a third would start pushing the map
                out of view, and the road is also named on the line below when it
                is the one being travelled.

                The row is `alignItems: 'center'`, so the arrow and the close
                button stay centred against whichever height the text takes. */}
            <Text style={styles.instruction} numberOfLines={2}>
              {/* OSRM's manoeuvre when the route has steps, the polyline's own
                  geometry when it does not. Both produce a true sentence; only the
                  first can name a road. See `instructions.ts`. */}
              {instructionFor(step, turn)}
            </Text>
            <Text style={styles.meta} numberOfLines={1}>
              {/* The road being travelled, when OSM has a name for it -- which on a
                  Dhaka lane it often does not, hence the conditional rather than a
                  placeholder. */}
              {road ? `on ${road} · ` : ''}
              {formatDistance(remainingM)} · {formatDuration(remainingSeconds)} left
              {/* Shown only when it is bad enough to explain a wandering marker.
                  A permanent accuracy readout is noise; one that appears when the
                  fix is poor answers "why is the arrow jumping". */}
              {accuracyM !== null && accuracyM > 30 ? ` · ±${Math.round(accuracyM)} m` : ''}
            </Text>
          </View>

          <Pressable onPress={onStop} hitSlop={10} accessibilityLabel="Stop following">
            <Ionicons name="close" size={20} color={t.textSoft} />
          </Pressable>
        </View>
      )}
    </Glass>
  );
};

const makeStyles = (t: Palette) =>
  StyleSheet.create({
    card: {
      position: 'absolute',
      left: space.lg,
      right: space.lg,
    },
    row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
    grow: { flex: 1 },
    badge: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: 'center',
      justifyContent: 'center',
    },
    instruction: {
      ...type.bodyStrong,
      color: t.text,
      // Tightened from the default so two lines read as one instruction rather
      // than as two stacked sentences.
      lineHeight: 20,
    },
    meta: { ...type.caption, color: t.textSoft, marginTop: 1 },
    finding: { ...type.body, color: t.textSoft, flex: 1 },
    action: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: space.sm,
      marginTop: space.md,
      paddingVertical: space.sm,
      borderRadius: radius.pill,
      borderWidth: StyleSheet.hairlineWidth * 2,
    },
    actionText: { ...type.label },
  });

export default NavigationBanner;
