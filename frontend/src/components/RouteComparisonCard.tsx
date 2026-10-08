/**
 * The route comparison card. D06, demo beat 4.
 *
 * `DEMO_PLAN.md` asks for *"alternatives ranked, each with `safety_score`, duration, and
 * the trade-off stated: 4 minutes longer, avoids two flagged corridors"* — and for
 * *"the explanation on screen, attached to the route, not in a log."*
 *
 * ## Three things this screen must not do
 *
 * **1. It must not render `safety_score` as a percentage.** It is a 0–100 score, not a
 * proportion of anything. The previous card printed `58.3% Safe`, which was one of the
 * three mutually inconsistent scales that made up defect 11 — alongside a 0–10
 * `crime_score` per path point. One scale, written `NN/100`.
 *
 * **2. It must not compose prose about a place.** `explanation` and
 * `flag.mobility_statement` arrive already framed by `app/policy/framing.py`, which is
 * their only producer; an invariant test enforces that server-side. This component
 * renders those strings and builds no sentences of its own about any location.
 *
 * **3. It must not hide a degraded answer.** `engine` and `notes` are rendered when they
 * say something — a walking time that is an estimate, a route from the public demo server,
 * a straight-line guess, a safety preference that had to be relaxed. All four are states
 * the previous card could reach silently.
 */

import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';

import { borderRadius, colors, fontSize, spacing } from '../theme';
import type { RouteResponse } from '../services/route.service';

export interface RouteComparisonCardProps {
  routes: RouteResponse[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  bottomInset: number;
}

/**
 * Colour for a safety score. Shared with the polyline so the card and the line agree.
 *
 * Thresholds deliberately differ from `RISK_SEVERITY_BANDS`: that scale is *severity*
 * (higher is worse) and this is *safety* (higher is better). Reusing one table for both
 * would invert the meaning of every colour, which is the kind of mistake defect 11 was
 * made of.
 */
export const safetyColour = (score: number): string => {
  if (score >= 75) return colors.success;
  if (score >= 50) return colors.warning;
  return colors.error;
};

/** `local` needs no mention; anything else is a degraded answer and must be visible. */
const engineNote = (engine: string): string | null => {
  if (engine === 'public-demo') {
    return 'Routed by a public demo server — the local routing engine did not answer.';
  }
  if (engine === 'straight-line') {
    return 'No routing engine answered. This is a straight-line estimate, not a road route.';
  }
  return null;
};

export const RouteComparisonCard: React.FC<RouteComparisonCardProps> = ({
  routes,
  selectedIndex,
  onSelect,
  bottomInset,
}) => {
  const route = routes[selectedIndex];
  if (!route) return null;

  const colour = safetyColour(route.safety_score);
  const caveats = [...route.notes, engineNote(route.engine)].filter(
    (note): note is string => Boolean(note),
  );

  return (
    <View style={[styles.card, { bottom: bottomInset + spacing.md }]}>
      {/* Ranked tabs. The recommended route is index 0 by composite score, and saying so
          beats leaving the user to infer it from the order. */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.tabs}
      >
        {routes.map((candidate, index) => {
          const active = index === selectedIndex;
          return (
            <TouchableOpacity
              key={candidate.route_id}
              onPress={() => onSelect(index)}
              style={[styles.tab, active && styles.tabActive]}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.tabText, active && styles.tabTextActive]}>
                {index === 0 ? 'Recommended' : `Option ${index + 1}`}
              </Text>
              <Text
                style={[
                  styles.tabScore,
                  { color: active ? safetyColour(candidate.safety_score) : colors.textMuted },
                ]}
              >
                {Math.round(candidate.safety_score)}/100
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      <View style={styles.stats}>
        <View style={styles.stat}>
          <Ionicons name="shield-checkmark" size={18} color={colour} />
          {/* NN/100 — not a percentage. See the module docstring. */}
          <Text style={[styles.statValue, { color: colour }]}>
            {Math.round(route.safety_score)}/100
          </Text>
          <Text style={styles.statLabel}>safety</Text>
        </View>

        <View style={styles.stat}>
          <Ionicons name="time-outline" size={18} color={colors.text} />
          <Text style={styles.statValue}>{route.duration_minutes} min</Text>
          {/* The label carries where the number came from, so a calibration is never
              mistaken for a measurement. Driving times are scaled from the graph's
              free-flow speeds (54.8 km/h measured across central Dhaka, which is
              absurd); walking times are computed from distance because OSRM answers a
              /foot/ request from the car graph. Both are estimates and say so. */}
          <Text style={styles.statLabel}>
            {route.notes.length === 0
              ? 'from the road map'
              : route.notes.some(n => n.startsWith('Walking'))
                ? 'walking estimate'
                : 'in traffic (est.)'}
          </Text>
        </View>

        <View style={styles.stat}>
          <MaterialCommunityIcons
            name="map-marker-distance"
            size={18}
            color={colors.text}
          />
          <Text style={styles.statValue}>{route.distance_km.toFixed(1)} km</Text>
          <Text style={styles.statLabel}>distance</Text>
        </View>

        <View style={styles.stat}>
          <Ionicons
            name="alert-circle-outline"
            size={18}
            color={route.flags.length > 0 ? colors.warning : colors.success}
          />
          <Text style={styles.statValue}>{route.flags.length}</Text>
          <Text style={styles.statLabel}>
            {route.flags.length === 1 ? 'flag' : 'flags'}
          </Text>
        </View>
      </View>

      {/* Beat 4. Server-framed, rendered verbatim. */}
      <Text style={styles.explanation}>{route.explanation}</Text>

      {/* One route is a legitimate answer, but a card showing a single tab with no
          comment reads like the alternatives failed to load. Say which it is.

          It happens when the road network genuinely offers one sensible way through —
          OSRM returns alternatives only where a distinct road exists, and across five
          Dhaka pairs three had one and two had two — and when nothing on the route was
          worth routing around. A historical blackspot is not: it covers kilometres, so
          "avoiding" it means avoiding the city. */}
      {routes.length === 1 && (
        <View style={styles.caveat}>
          <Ionicons name="git-branch-outline" size={14} color={colors.textMuted} />
          <Text style={styles.caveatText}>
            Only one sensible route exists between these points, so there is nothing to
            compare. Nothing on it was worth a detour.
          </Text>
        </View>
      )}

      {route.filter_relaxed && (
        <View style={styles.caveat}>
          <Ionicons name="information-circle-outline" size={14} color={colors.info} />
          <Text style={styles.caveatText}>
            Every available route exceeds your safety preference. These are shown
            best-first rather than hiding them.
          </Text>
        </View>
      )}

      {caveats.map(note => (
        <View key={note} style={styles.caveat}>
          <Ionicons name="warning-outline" size={14} color={colors.warning} />
          <Text style={styles.caveatText}>{note}</Text>
        </View>
      ))}

      {/* The flags themselves, so the score is auditable rather than asserted. Chronic
          flags are labelled, because "this area has a history" and "there is a fire here
          now" are different claims and must not look the same. */}
      {route.flags.length > 0 && (
        <ScrollView style={styles.flagList} showsVerticalScrollIndicator={false}>
          {route.flags.map(flag => (
            <View key={flag.flag_id} style={styles.flagRow}>
              <View
                style={[
                  styles.flagDot,
                  {
                    backgroundColor:
                      flag.status === 'confirmed' ? colors.error : 'transparent',
                    borderColor: colors.error,
                  },
                ]}
              />
              <Text style={styles.flagText} numberOfLines={2}>
                {flag.mobility_statement}
                <Text style={styles.flagMeta}>
                  {flag.kind === 'chronic'
                    ? '  ·  historical pattern'
                    : `  ·  ${flag.source_count} ${
                        flag.source_count === 1 ? 'source' : 'sources'
                      }${flag.status === 'confirmed' ? '' : ', unconfirmed'}`}
                </Text>
              </Text>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
};

export default RouteComparisonCard;

const styles = StyleSheet.create({
  card: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    // Capped so a route with many flags cannot grow the card over the whole map; the
    // flag list scrolls inside it.
    maxHeight: '58%',
  },
  tabs: { gap: spacing.sm, paddingBottom: spacing.sm },
  tab: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surfaceVariant,
    alignItems: 'center',
  },
  tabActive: { backgroundColor: colors.primaryLight },
  tabText: { fontSize: fontSize.xs, color: colors.textSecondary, fontWeight: '600' },
  tabTextActive: { color: colors.primaryDark },
  tabScore: { fontSize: fontSize.xs, fontWeight: '700' },
  stats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.borderLight,
  },
  stat: { alignItems: 'center', flex: 1 },
  statValue: { fontSize: fontSize.sm, fontWeight: '700', color: colors.text },
  statLabel: { fontSize: 10, color: colors.textMuted },
  explanation: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 19,
    paddingTop: spacing.sm,
  },
  caveat: {
    flexDirection: 'row',
    gap: spacing.xs,
    alignItems: 'flex-start',
    paddingTop: spacing.xs,
  },
  caveatText: { flex: 1, fontSize: fontSize.xs, color: colors.textSecondary, lineHeight: 16 },
  flagList: { marginTop: spacing.sm, maxHeight: 110 },
  flagRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start', paddingVertical: 3 },
  flagDot: { width: 9, height: 9, borderRadius: 5, borderWidth: 1.5, marginTop: 4 },
  flagText: { flex: 1, fontSize: fontSize.xs, color: colors.text, lineHeight: 16 },
  flagMeta: { color: colors.textMuted },
});
