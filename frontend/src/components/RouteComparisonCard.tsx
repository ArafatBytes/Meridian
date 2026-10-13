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
 *
 * ## It must also not cover the route
 *
 * The card used to render everything at once under a `maxHeight: '58%'` cap. With
 * four stats, an explanation, up to three caveats and a flag list, it reached
 * that cap routinely — and 58% of the screen, anchored to the bottom, is most of
 * the map. The user could read about the route but not see it, which defeats the
 * point of drawing it.
 *
 * So it is now a sheet with two states:
 *
 * * **Collapsed** (the default) — the ranked tabs, the four stats, and the
 *   explanation clamped to two lines. Capped at 34% of the screen, so two
 *   thirds of the map stays visible with the route on it.
 * * **Expanded** — the same header with everything below it in one scroll view:
 *   the full explanation, every caveat, every flag. Capped at 76%.
 *
 * One `ScrollView` for the body rather than the old arrangement, where only the
 * flag list scrolled and everything above it could overflow the cap and be
 * clipped with nothing to indicate it.
 *
 * The tabs and stats stay outside the scroll view on purpose: switching between
 * routes is the card's main job, and a control that scrolls away is a control
 * you have to go looking for.
 */

import React, { useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { Glass } from './motion';

import { useTheme } from '../theme/ThemeProvider';
import { useStyles } from '../theme/useStyles';
import type { Palette } from '../theme/palette';
import { fontFamily, radius, space, type } from '../theme/type';
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
export const safetyColour = (score: number, t: Palette): string => {
  if (score >= 75) return t.ok;
  if (score >= 50) return t.warn;
  return t.danger;
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
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  // Collapsed by default: the first thing a user wants after asking for a route
  // is to see the route.
  const [expanded, setExpanded] = useState(false);
  const route = routes[selectedIndex];
  if (!route) return null;

  const colour = safetyColour(route.safety_score, t);
  const caveats = [...route.notes, engineNote(route.engine)].filter(
    (note): note is string => Boolean(note),
  );

  // Is there anything behind the chevron? With one route, no caveats and no
  // flags, the collapsed view is already the whole card, and offering to expand
  // onto an empty panel is worse than offering nothing.
  // Optional on the wire, so a backend from before B13 reads as "no clusters"
  // rather than crashing the card.
  const clusters = route.clusters ?? [];

  const hasDetail =
    caveats.length > 0 ||
    route.flags.length > 0 ||
    clusters.length > 0 ||
    routes.length === 1 ||
    route.filter_relaxed ||
    route.explanation.length > 110;

  return (
    <Glass
      style={[
        styles.card,
        expanded ? styles.cardExpanded : styles.cardCollapsed,
        { bottom: bottomInset + space.lg },
      ]}
      contentStyle={styles.body}
      radius={radius.card}
      padding={space.lg}
      intensity={26}
      elevated
    >
      {/* Ranked tabs. The recommended route is index 0 by composite score, and saying so
          beats leaving the user to infer it from the order. Kept outside the scroll
          view: switching routes is this card's main job, and a control that
          scrolls away is one you have to go looking for. */}
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
                  { color: active ? safetyColour(candidate.safety_score, t) : t.textFaint },
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
          <Ionicons name="shield-checkmark" size={16} color={colour} />
          {/* NN/100 — not a percentage. See the module docstring. */}
          <Text style={[styles.statValue, { color: colour }]}>
            {Math.round(route.safety_score)}/100
          </Text>
          <Text style={styles.statLabel}>safety</Text>
        </View>

        <View style={styles.stat}>
          <Ionicons name="time-outline" size={16} color={t.text} />
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
          <MaterialCommunityIcons name="map-marker-distance" size={16} color={t.text} />
          <Text style={styles.statValue}>{route.distance_km.toFixed(1)} km</Text>
          <Text style={styles.statLabel}>distance</Text>
        </View>

        <View style={styles.stat}>
          <Ionicons
            name="alert-circle-outline"
            size={16}
            color={route.flags.length > 0 ? t.warn : t.ok}
          />
          <Text style={styles.statValue}>{route.flags.length}</Text>
          <Text style={styles.statLabel}>
            {route.flags.length === 1 ? 'flag' : 'flags'}
          </Text>
        </View>
      </View>

      {expanded ? (
        // Everything below the stats, in ONE scroll view. The old card scrolled
        // only the flag list, so an explanation plus three caveats could overflow
        // the height cap and be clipped with nothing to say so.
        <ScrollView
          style={styles.scroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scrollBody}
        >
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
              <Ionicons name="git-branch-outline" size={14} color={t.textFaint} />
              <Text style={styles.caveatText}>
                Only one sensible route exists between these points, so there is nothing
                to compare. Nothing on it was worth a detour.
              </Text>
            </View>
          )}

          {route.filter_relaxed && (
            <View style={styles.caveat}>
              <Ionicons name="information-circle-outline" size={14} color={t.info} />
              <Text style={styles.caveatText}>
                Every available route exceeds your safety preference. These are shown
                best-first rather than hiding them.
              </Text>
            </View>
          )}

          {caveats.map(note => (
            <View key={note} style={styles.caveat}>
              <Ionicons name="warning-outline" size={14} color={t.warn} />
              <Text style={styles.caveatText}>{note}</Text>
            </View>
          ))}

          {/* The flags themselves, so the score is auditable rather than asserted.
              Chronic flags are labelled, because "this area has a history" and "there is
              a fire here now" are different claims and must not look the same.

              No `maxHeight` and no nested scroll any more: the list is part of the
              sheet's one scroll view, so a route with nine flags reads as nine
              flags instead of a 110pt window with its own hidden scrollbar. */}
          {route.flags.length > 0 && (
            <View style={styles.flagList}>
              {route.flags.map(flag => (
                <View key={flag.flag_id} style={styles.flagRow}>
                  <View
                    style={[
                      styles.flagDot,
                      {
                        backgroundColor:
                          flag.status === 'confirmed' ? t.danger : 'transparent',
                        borderColor: t.danger,
                      },
                    ]}
                  />
                  <Text style={styles.flagText}>
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
            </View>
          )}

          {/* Community clusters, in their own block below the flags rather than
              mixed into them. B13.

              A flag and a cluster are different claims -- one is the product's own
              mobility statement from edited sources, the other a count of what
              residents reported -- and interleaving them is the Defect 54 confusion
              in list form. The section label is what makes the distinction legible
              without the user having to infer it from a dot style.

              Same dot grammar as the flags above: solid is corroborated, hollow is
              not. One rule across both lists, in the accent colour rather than a
              severity colour, because a cluster carries no severity grade -- see
              `CommunityClusterMarker` for why that restraint is deliberate. */}
          {clusters.length > 0 && (
            <View style={styles.flagList}>
              <Text style={styles.clusterLabel}>Community reports</Text>
              {clusters.map(cluster => (
                <View key={cluster.cluster_id} style={styles.flagRow}>
                  <View
                    style={[
                      styles.flagDot,
                      {
                        backgroundColor:
                          cluster.status === 'corroborated' ? t.accent : 'transparent',
                        borderColor: t.accent,
                      },
                    ]}
                  />
                  <Text style={styles.flagText}>
                    {cluster.statement}
                    <Text style={styles.flagMeta}>
                      {`  ·  ${cluster.reporter_count} ${
                        cluster.reporter_count === 1 ? 'person' : 'people'
                      }${
                        cluster.report_count > cluster.reporter_count
                          ? ` from ${cluster.report_count} reports`
                          : ''
                      }${cluster.status === 'corroborated' ? '' : ', not yet corroborated'}`}
                    </Text>
                  </Text>
                </View>
              ))}
            </View>
          )}
        </ScrollView>
      ) : (
        // Collapsed: two lines of the explanation, clamped rather than shortened,
        // so expanding shows the same sentence in full.
        <Text style={styles.explanation} numberOfLines={2}>
          {route.explanation}
        </Text>
      )}

      {hasDetail && (
        <Pressable
          onPress={() => setExpanded(current => !current)}
          style={styles.toggle}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={expanded ? 'Hide route details' : 'Show route details'}
        >
          <Text style={styles.toggleText}>
            {expanded
              ? 'Hide details'
              : route.flags.length > 0
                ? `Details · ${route.flags.length} ${
                    route.flags.length === 1 ? 'flag' : 'flags'
                  } on this route`
                : // Flags first when there are any: they are the stronger claim and
                  // what the score is mostly made of. Clusters get the label only
                  // when they are the only thing there is to say, which is also the
                  // case where a bare "Details" would hide the whole point.
                  clusters.length > 0
                  ? `Details · ${clusters.length} report ${
                      clusters.length === 1 ? 'area' : 'areas'
                    } on this route`
                  : 'Details'}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-down' : 'chevron-up'}
            size={14}
            color={t.brand}
          />
        </Pressable>
      )}
    </Glass>
  );
};

export default RouteComparisonCard;

const makeStyles = (t: Palette) =>
StyleSheet.create({
    // `Glass` draws the fill, the border and the radius now, so this carries
    // placement only. The two height caps are the whole point of the rework:
    // collapsed leaves two thirds of the map visible, expanded is a sheet.
    card: { position: 'absolute', left: space.lg, right: space.lg },
    // The cap goes on the SHELL, not on the inner content box. A percentage
    // resolves against the parent's definite height, and the shell is
    // absolutely positioned with an auto height — so `maxHeight: '34%'` on a
    // child of it resolves against nothing and is silently ignored. On the
    // shell it resolves against the map container, which is what the old
    // single-piece card did.
    cardCollapsed: { maxHeight: '34%' },
    cardExpanded: { maxHeight: '76%' },
    // `flexShrink` down the chain, so the shell's cap actually reaches the
    // scroll view. Without it the content keeps its natural height and is
    // clipped by `overflow: 'hidden'` instead of becoming scrollable.
    body: { flexShrink: 1 },
    scroll: { flexShrink: 1 },
    scrollBody: { paddingBottom: space.xs },
    toggle: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 4,
      paddingTop: space.sm,
      marginTop: space.xs,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.line,
    },
    toggleText: {      ...type.caption, color: t.brand },
    tabs: { gap: space.sm, paddingBottom: space.sm },
    tab: {
      paddingHorizontal: space.lg,
      paddingVertical: space.xs,
      borderRadius: radius.md,
      backgroundColor: t.fillSoft,
      alignItems: 'center',
    },
    tabActive: { backgroundColor: t.brandStrong },
    tabText: {      ...type.caption, color: t.textSoft,},
    tabTextActive: { color: t.brandStrong },
    tabScore: {      ...type.caption, },
    stats: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      paddingVertical: space.sm,
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: t.lineSoft,
    },
    stat: { alignItems: 'center', flex: 1 },
    statValue: {      ...type.label, color: t.text },
    statLabel: { fontFamily: fontFamily.body, fontSize: 10, color: t.textFaint },
    explanation: {
      ...type.small,
      color: t.text,
      paddingTop: space.sm,
    },
    caveat: {
      flexDirection: 'row',
      gap: space.xs,
      alignItems: 'flex-start',
      paddingTop: space.xs,
    },
    caveatText: {      ...type.caption, flex: 1, color: t.textSoft, lineHeight: 16 },
    flagList: { marginTop: space.sm },
    flagRow: { flexDirection: 'row', gap: space.sm, alignItems: 'flex-start', paddingVertical: 3 },
    flagDot: { width: 9, height: 9, borderRadius: 5, borderWidth: 1.5, marginTop: 4 },
    flagText: {      ...type.caption, flex: 1, color: t.text, lineHeight: 16 },
    flagMeta: { color: t.textFaint },
    // An overline, matching the section labels everywhere else in the app.
    clusterLabel: {
      ...type.overline,
      color: t.textFaint,
      marginTop: space.sm,
      marginBottom: 2,
    },
  });
