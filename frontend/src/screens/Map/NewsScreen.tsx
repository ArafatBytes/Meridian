/**
 * The headlines behind the map. D09.
 *
 * Two jobs, and the second is why it looks the way it does.
 *
 * **For the demo**, it is the article beside the pin: beat 8's procession stops
 * being a square on a map and becomes an announcement you can point at, with an
 * outlet and a time on it.
 *
 * **Day to day, it is the ingestion dashboard.** Live ingestion is currently thin
 * and the fix is next phase; this is the screen that will show it improving. So the
 * header carries the agent's own last-run numbers, every sample headline is
 * labelled as sample, and the counter says *n real of m* rather than quietly
 * presenting fixture data as a day's work. A page that flattered the pipeline would
 * be worse than no page.
 *
 * It reads `GET /risk/flags` twice — once at now, once at +24h — and regroups what
 * the map already had. No new endpoint, and nothing here re-derives severity or
 * decay; `types/contracts/risk.ts` explains why that arithmetic stays on the
 * server.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing, borderRadius, typography } from '../../theme';
import { riskService, type IngestionStatus, type MapRegion } from '../../services/risk.service';
import { messageOf } from '../../services/casework.service';
import { riskBand } from '../../components/RiskFlagSheet';
import {
  newsFromFlags,
  splitByTense,
  realCount,
  outletName,
  isWebLink,
  type NewsEntry,
} from '../../features/risk/news';
import { windowText } from '../../features/risk/scheduled';
import { DEFAULT_MAP_REGION } from '../../constants';

type Tab = 'today' | 'tomorrow';

/** "11:40" or "Fri 11:40" once it is not today. */
function stamp(iso: string | null): string {
  if (!iso) return 'time not given';
  const at = new Date(iso);
  const today = new Date().toDateString() === at.toDateString();
  const time = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return today ? time : `${at.toLocaleDateString([], { weekday: 'short' })} ${time}`;
}

/** The agent's own last run, in one line. Null when it has never run. */
function ingestionLine(status: IngestionStatus | null): string {
  if (!status) return 'ingestion status unavailable';
  if (status.mode === 'replay') return 'offline replay — no live reading';
  const run = status.lastRun;
  if (!run) return 'the news agent has not run yet';
  const when = stamp(run.finishedAt ?? run.startedAt);
  if (run.status === 'running') return `reading news now (started ${when})`;
  return `last read ${when} · ${run.documentsRead} article${
    run.documentsRead === 1 ? '' : 's'
  }, ${run.flagsPublished} flag${run.flagsPublished === 1 ? '' : 's'}`;
}

const NewsScreen: React.FC = () => {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();

  const [tab, setTab] = useState<Tab>('today');
  const [entries, setEntries] = useState<NewsEntry[] | null>(null);
  const [ingestion, setIngestion] = useState<IngestionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const region: MapRegion = DEFAULT_MAP_REGION;
    const tomorrow = new Date(Date.now() + 24 * 3600 * 1000);

    // Both instants, and the ingestion status, in one pass. `allSettled` because a
    // failed status read should not cost us the headlines — D08's lesson, where one
    // benign 404 made a whole screen look broken.
    const [now, ahead, status] = await Promise.allSettled([
      riskService.getFlagsInRegion(region),
      riskService.getFlagsInRegion(region, tomorrow),
      riskService.getIngestionStatus(),
    ]);

    if (status.status === 'fulfilled') setIngestion(status.value);

    if (now.status === 'rejected' && ahead.status === 'rejected') {
      setError(messageOf(now.reason, 'Could not load the news behind the map.'));
      setEntries([]);
      return;
    }

    const flags = [
      ...(now.status === 'fulfilled' ? now.value.flags : []),
      ...(ahead.status === 'fulfilled' ? ahead.value.flags : []),
    ];
    setEntries(newsFromFlags(flags));
    setError(null);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const { live, scheduled } = useMemo(
    () => splitByTense(entries ?? []),
    [entries],
  );
  const shown = tab === 'today' ? live : scheduled;

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={12}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>What we read</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* The pipeline's own numbers, not a summary of this list. On a day when
          ingestion did nothing, this line is how you find that out in one glance. */}
      <View style={styles.statusBar}>
        <Ionicons name="pulse-outline" size={14} color={colors.textSecondary} />
        <Text style={styles.statusText} numberOfLines={2}>
          {ingestionLine(ingestion)}
        </Text>
      </View>

      <View style={styles.tabs}>
        {(
          [
            ['today', `Today · ${live.length}`],
            ['tomorrow', `Tomorrow · ${scheduled.length}`],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <TouchableOpacity
            key={value}
            style={[styles.tab, tab === value && styles.tabActive]}
            onPress={() => setTab(value)}
          >
            <Text style={[styles.tabText, tab === value && styles.tabTextActive]}>
              {label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {entries === null ? (
        <View style={styles.centre}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={[
            styles.body,
            { paddingBottom: insets.bottom + spacing.xl },
          ]}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {error && (
            <View style={styles.errorCard}>
              <Ionicons name="warning-outline" size={18} color={colors.error} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {shown.length > 0 && (
            <Text style={styles.counter}>
              {/* Said plainly. `0 real of 22` is the honest reading of a seeded
                  surface, and it is the number that should change next phase. */}
              {realCount(shown)} real of {shown.length} · the rest is sample data
            </Text>
          )}

          {shown.length === 0 && !error && (
            <View style={styles.emptyCard}>
              <Ionicons name="newspaper-outline" size={40} color={colors.textSecondary} />
              <Text style={styles.emptyTitle}>
                {tab === 'today' ? 'Nothing read yet' : 'Nothing announced'}
              </Text>
              <Text style={styles.emptyText}>
                {tab === 'today'
                  ? 'Flags on the map that came from an article appear here, newest first. The chronic layer has no article behind it, so it never shows.'
                  : 'Announcements of processions, closures and works that have not happened yet appear here, with the window they cover.'}
              </Text>
            </View>
          )}

          {shown.map(entry => {
            const band = riskBand(entry.flag.severityNow);
            const linked = isWebLink(entry.url);
            const confirmed = entry.flag.status === 'confirmed';
            return (
              <TouchableOpacity
                key={entry.key}
                style={styles.card}
                activeOpacity={linked ? 0.7 : 1}
                disabled={!linked}
                onPress={() => linked && Linking.openURL(entry.url)}
              >
                <View style={styles.cardTop}>
                  <Text style={styles.outlet}>{outletName(entry.outletId)}</Text>
                  <Text style={styles.time}>{stamp(entry.publishedAt)}</Text>
                </View>

                <Text style={[styles.title, linked && styles.titleLink]}>{entry.title}</Text>

                {/* What the article turned into. The reason this page is not a feed
                    reader: every card is an article AND the claim it produced. */}
                <View style={styles.outcome}>
                  <View style={[styles.dot, { backgroundColor: band.color }]} />
                  <Text style={styles.outcomeText} numberOfLines={2}>
                    {entry.flag.mobilityStatement}
                  </Text>
                </View>

                <View style={styles.tags}>
                  <View style={styles.tag}>
                    <Ionicons
                      name={confirmed ? 'checkmark-circle' : 'help-circle-outline'}
                      size={12}
                      color={confirmed ? colors.success : colors.textSecondary}
                    />
                    <Text style={styles.tagText}>
                      {confirmed
                        ? `Confirmed · ${entry.flag.sourceCount}`
                        : `Unconfirmed · ${entry.flag.sourceCount}`}
                    </Text>
                  </View>

                  {entry.flag.validFrom && (
                    <View style={[styles.tag, { backgroundColor: `${colors.info}22` }]}>
                      <Ionicons name="calendar-outline" size={12} color={colors.info} />
                      <Text style={[styles.tagText, { color: colors.info }]}>
                        {windowText(entry.flag.validFrom, entry.flag.validTo)}
                      </Text>
                    </View>
                  )}

                  {entry.isSample && (
                    <View style={[styles.tag, { backgroundColor: `${colors.warning}22` }]}>
                      <Ionicons name="flask-outline" size={12} color={colors.warning} />
                      <Text style={[styles.tagText, { color: colors.warning }]}>
                        Sample data
                      </Text>
                    </View>
                  )}
                </View>
              </TouchableOpacity>
            );
          })}

          {shown.length > 0 && (
            <Text style={styles.footnote}>
              Sample headlines come from the seeded surface and their links do not open.
              Real articles open in your browser. Flags from the chronic layer are not
              listed here, because no article produced them.
            </Text>
          )}
        </ScrollView>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  headerTitle: { ...typography.h4, color: colors.text },

  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  statusText: { ...typography.caption, color: colors.textSecondary, flex: 1 },

  tabs: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  tab: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: borderRadius.sm,
    backgroundColor: colors.surfaceVariant,
  },
  tabActive: { backgroundColor: colors.primary },
  tabText: { ...typography.bodySmall, color: colors.textSecondary, fontWeight: '600' },
  tabTextActive: { color: colors.white },

  centre: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  body: { paddingHorizontal: spacing.lg, gap: spacing.md },
  counter: { ...typography.caption, color: colors.textSecondary },

  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.xs,
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.sm },
  outlet: { ...typography.caption, color: colors.primary, fontWeight: '700' },
  time: { ...typography.caption, color: colors.textSecondary },
  title: { ...typography.body, color: colors.text, fontWeight: '600', lineHeight: 21 },
  titleLink: { color: colors.primary },

  outcome: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  outcomeText: { ...typography.bodySmall, color: colors.textSecondary, flex: 1 },

  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: 4 },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.surfaceVariant,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  tagText: { ...typography.caption, color: colors.textSecondary },

  errorCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: `${colors.error}11`,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  errorText: { ...typography.bodySmall, color: colors.error, flex: 1 },

  emptyCard: {
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.md,
  },
  emptyTitle: { ...typography.h4, color: colors.text },
  emptyText: { ...typography.bodySmall, color: colors.textSecondary, textAlign: 'center' },

  footnote: {
    ...typography.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    lineHeight: 16,
  },
});

export default NewsScreen;
