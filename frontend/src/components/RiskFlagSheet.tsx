import React from 'react';
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, borderRadius, fontSize } from '../theme';
import type { RiskFlag } from '../types/contracts/risk';

/**
 * The flag detail sheet. Demo beat 2's container.
 *
 * Tap a pin and see what the surface actually knows: what kind of thing it is, how
 * severe it is **right now** versus when it was observed, its half-life, how long it
 * has left, and whether it has been confirmed.
 *
 * D04 fills in the source strip with real headlines and outlets; D05 adds the
 * confirmation time and the promotion. The shape is here now so neither sprint has to
 * build a screen as well as a pipeline.
 *
 * Two rules this component follows, and both are load-bearing
 * -----------------------------------------------------------
 * **1. `mobilityStatement` is the only flag prose it renders.** That string was
 * produced by `app/policy/framing.py` and nothing else may produce one. Building a
 * headline here from `kind` would put the word "clash" on a map that has committed
 * never to say it (concept document §9), and it would do it in a component where no
 * invariant test is watching.
 *
 * **2. It computes nothing.** Severity now, the half-life and the expiry all arrive
 * from the server. The only arithmetic below is formatting a duration that is already
 * decided by `expiresAt`. A client that decayed flags itself would disagree with the
 * server about when one vanishes, and the disagreement would show up as a pin that is
 * on the map with zero severity.
 */

export interface RiskFlagSheetProps {
  flag: RiskFlag | null;
  /** The instant the surface was evaluated at, so the sheet can say "as of". */
  asOf: string | null;
  onClose: () => void;
}

/**
 * The severity bands, shared with the map's pin colours.
 *
 * Exported because `MapScreen` colours pins from the same table — two copies would
 * drift, and a sheet that said "High" next to an orange pin the map called "Severe"
 * reads as a bug in the data rather than in the palette.
 */
export const RISK_SEVERITY_BANDS: { min: number; color: string; label: string }[] = [
  { min: 70, color: '#D32F2F', label: 'Severe' },
  { min: 50, color: '#F57C00', label: 'High' },
  { min: 30, color: '#FBC02D', label: 'Moderate' },
  { min: 0, color: '#78909C', label: 'Low' },
];

export const riskBand = (severity: number) =>
  RISK_SEVERITY_BANDS.find(band => severity >= band.min) ??
  RISK_SEVERITY_BANDS[RISK_SEVERITY_BANDS.length - 1];

/**
 * A neutral category label.
 *
 * Deliberately **not** a translation of every `IncidentKind`. `clash` maps to
 * "Disruption", not to "Clash", because the kind is an internal routing decision and
 * the product does not characterise events to users — that is the same commitment
 * `framing.py` enforces on the server, restated in the one place a client could break
 * it. A kind with no entry falls back to "Disruption" rather than to its raw value, so
 * adding an `IncidentKind` cannot leak a new word onto the screen.
 */
const KIND_LABELS: Record<string, string> = {
  road_accident: 'Road incident',
  fire: 'Fire service activity',
  blockade: 'Road closure',
  procession: 'Large gathering',
  clash: 'Disruption',
  waterlogging: 'Standing water',
  construction: 'Road works',
  utility_outage: 'Utility works',
  chronic: 'Recurring condition',
  other: 'Disruption',
};

const kindLabel = (kind: string) => KIND_LABELS[kind] ?? 'Disruption';

/**
 * "3h 20m", "18m", "6 days" — how long until this flag leaves the surface.
 *
 * Coarsens as the number grows, because precision that cannot be acted on is noise: a
 * road-works flag with five weeks left does not need its minutes. Returns null once
 * the flag has expired, and the caller renders that case as its own line rather than
 * as "0m".
 */
function timeRemaining(expiresAt: string, from: string | null): string | null {
  const end = new Date(expiresAt).getTime();
  const start = from ? new Date(from).getTime() : Date.now();
  const minutes = Math.round((end - start) / 60000);

  if (!Number.isFinite(minutes) || minutes <= 0) return null;
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 60 * 24) {
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `${hours}h ${rest}m` : `${hours}h`;
  }
  const days = Math.round(minutes / (60 * 24));
  return days === 1 ? '1 day' : `${days} days`;
}

/** "14:31" in the device's own timezone, which for this demo is Dhaka. */
function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const RiskFlagSheet: React.FC<RiskFlagSheetProps> = ({ flag, asOf, onClose }) => {
  if (!flag) return null;

  const band = riskBand(flag.severityNow);
  const remaining = timeRemaining(flag.expiresAt, asOf);
  const isConfirmed = flag.status === 'confirmed';

  // How much of the original severity is left. This is the "42% severity remaining"
  // in demo beat 2, and it is the clearest single statement that the surface decays.
  const remainingPercent =
    flag.severity0 > 0 ? Math.round((flag.severityNow / flag.severity0) * 100) : 0;

  const isScheduled = flag.validFrom !== null;

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          {/* The one string the server produced through framing.py. */}
          <View style={styles.header}>
            <View style={[styles.severityDot, { backgroundColor: band.color }]} />
            <Text style={styles.statement}>{flag.mobilityStatement}</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeButton} hitSlop={12}>
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <View style={styles.badges}>
            <View style={[styles.badge, { backgroundColor: `${band.color}22` }]}>
              <Text style={[styles.badgeText, { color: band.color }]}>
                {band.label} · {Math.round(flag.severityNow)}/100
              </Text>
            </View>

            {/* The verification tier, visible at a glance. D05 renders the same
                distinction on the map itself; this is the explanation behind it. */}
            <View
              style={[
                styles.badge,
                {
                  backgroundColor: isConfirmed
                    ? `${colors.success}22`
                    : colors.surfaceVariant,
                },
              ]}
            >
              <Ionicons
                name={isConfirmed ? 'checkmark-circle' : 'help-circle-outline'}
                size={13}
                color={isConfirmed ? colors.success : colors.textSecondary}
              />
              <Text
                style={[
                  styles.badgeText,
                  { color: isConfirmed ? colors.success : colors.textSecondary },
                ]}
              >
                {isConfirmed
                  ? `Confirmed · ${flag.sourceCount} sources`
                  : 'Unconfirmed · 1 source'}
              </Text>
            </View>

            {isScheduled && (
              <View style={[styles.badge, { backgroundColor: `${colors.info}22` }]}>
                <Ionicons name="calendar-outline" size={13} color={colors.info} />
                <Text style={[styles.badgeText, { color: colors.info }]}>Scheduled</Text>
              </View>
            )}
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            <Row label="Category" value={kindLabel(flag.kind)} />
            <Row label="Observed" value={clockTime(flag.observedAt)} />

            {/* The decay story, in three lines. "74 when observed, 31 now, 42%
                remaining" is what makes beat 5 legible without narration. */}
            <Row label="Severity when observed" value={`${Math.round(flag.severity0)}/100`} />
            <Row label="Severity now" value={`${Math.round(flag.severityNow)}/100`} />
            <Row label="Remaining" value={`${remainingPercent}% of original`} />

            <Row
              label="Half-life"
              value={
                flag.halfLifeHours >= 48
                  ? `${Math.round(flag.halfLifeHours / 24)} days`
                  : `${flag.halfLifeHours}h`
              }
            />
            <Row
              label="Leaves the map"
              value={remaining ? `in ${remaining}` : 'expired'}
            />
            <Row
              label="Area"
              value={
                flag.radiusM >= 1000
                  ? `${(flag.radiusM / 1000).toFixed(1)} km radius`
                  : `${flag.radiusM} m radius`
              }
            />

            {/* Source strip. D04 replaces these with real headlines and outlets; today
                every entry is marked `sample_` on purpose, so that nobody — including
                us, at midnight on the 23rd — can mistake the fixture for live data. */}
            {flag.sources.length > 0 && (
              <View style={styles.sources}>
                <Text style={styles.sourcesHeading}>
                  {flag.sources.length === 1 ? 'Source' : 'Sources'}
                </Text>
                {flag.sources.map((source, index) => (
                  <View key={`${source.sourceId}-${index}`} style={styles.source}>
                    <Text style={styles.sourceId}>{source.sourceId}</Text>
                    {source.title ? (
                      <Text style={styles.sourceTitle} numberOfLines={2}>
                        {source.title}
                      </Text>
                    ) : null}
                  </View>
                ))}
              </View>
            )}

            <Text style={styles.footnote}>
              Severity decays on its own. Nothing here is a judgement about a place or
              the people in it — only about getting through it.
            </Text>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: colors.overlay,
  },
  sheet: {
    backgroundColor: colors.backgroundLight,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    maxHeight: '75%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  severityDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: spacing.sm,
  },
  statement: {
    flex: 1,
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
  },
  closeButton: {
    marginLeft: spacing.sm,
    padding: spacing.xs,
  },
  badges: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.full,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  body: {
    flexGrow: 0,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.divider,
  },
  rowLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  rowValue: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  sources: {
    marginTop: spacing.lg,
  },
  sourcesHeading: {
    fontSize: fontSize.xs,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.xs,
  },
  source: {
    paddingVertical: spacing.xs,
  },
  sourceId: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  sourceTitle: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  footnote: {
    marginTop: spacing.lg,
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 16,
  },
});

export default RiskFlagSheet;
