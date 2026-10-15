/**
 * System status — are the agents behind the map actually running. B9.
 *
 * ## Why a user gets this screen at all
 *
 * B6b asked for a page showing what the ingestion pipeline read and what it
 * discarded, and the owner declined it: *"I don't want to show the users this
 * information."* That judgement was about **provenance** — the audience for "371
 * read, 34 discarded" is an operator, not somebody checking whether a road is
 * safe tonight.
 *
 * This is a different question with a different audience. "Is what I am looking
 * at current" is the user's question, and today the app has no answer to it: if
 * the news agent had stopped at 2am, the map would look exactly as it does when
 * everything works. A map that is confidently empty and a map that is empty
 * because nothing has run are the same picture.
 *
 * ## The two rules this screen holds
 *
 * **It never says healthy when the data is stale.** `health.py` refuses to call
 * a stale success working, and `STATE_LABELS` keeps `late` as "Running behind"
 * rather than collapsing amber into green to make the page look calm.
 *
 * **It says when a red card does not affect the user.** `expiry_sweep` is the
 * case that forced this: its name suggests the map depends on it, and its own
 * docstring says the opposite — every surface stops serving an expired row
 * whether the sweep has ever run or not. So a user is told that one is our
 * problem and not theirs. Without that, an honest status page becomes a page
 * that frightens people about the wrong things.
 *
 * Operator detail — error text, item counts, failure tallies, the stuck-run
 * distinction — is not here and is not withheld by accident. It is in
 * `python -m app.agents status`, where the reader can act on it.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import agentsService, { type FleetStatus } from '../../services/agents.service';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassBar, glassSurface } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { radius, space, type } from '../../theme/type';
import type { ProfileStackParamList } from '../../types';
import {
  STATE_LABELS,
  describeAge,
  describeAgent,
  describeCadence,
  type StateLabel,
} from './agentCatalogue';

type Navigation = NativeStackNavigationProp<ProfileStackParamList, 'SystemStatus'>;

interface Props {
  navigation: Navigation;
}

/**
 * The headline, derived from the worst card rather than from a count.
 *
 * "4 of 5 working" is the tempting summary and it is the wrong one: it reads as
 * 80% fine, when the one that is down might be the one putting warnings on the
 * map. The worst state is what a user needs to act on.
 */
function summarise(fleet: FleetStatus): { text: string; tone: StateLabel['tone']; icon: string } {
  if (fleet.mode === 'replay') {
    return {
      text: 'Running in offline demo mode. Nothing is being fetched live, and the map is showing a saved snapshot.',
      tone: 'idle',
      icon: 'archive-outline',
    };
  }
  if (fleet.agents.length === 0) {
    return { text: 'No parts reported in.', tone: 'idle', icon: 'help-circle-outline' };
  }
  if (fleet.agents.some((agent) => agent.state === 'problem')) {
    return {
      text: 'Something is not working. The parts marked below are affected.',
      tone: 'bad',
      icon: 'alert-circle',
    };
  }
  if (fleet.agents.some((agent) => agent.state === 'late')) {
    return {
      text: 'Everything is running, but some parts are behind schedule. What you see may be a little out of date.',
      tone: 'warn',
      icon: 'time-outline',
    };
  }
  return { text: 'Everything is working and up to date.', tone: 'ok', icon: 'checkmark-circle' };
}

const SystemStatusScreen: React.FC<Props> = ({ navigation }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();

  const [fleet, setFleet] = useState<FleetStatus | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setFleet(await agentsService.status());
      setFailed(false);
    } catch {
      // Deliberately not merged with the fleet state. "We could not ask" and
      // "we asked and everything is fine" must never render the same way, which
      // is the whole reason `agents.service.ts` throws here instead of
      // swallowing like `geo.service.ts` does.
      setFailed(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toneColour = (tone: StateLabel['tone']): string =>
    tone === 'ok' ? t.ok : tone === 'warn' ? t.warn : tone === 'bad' ? t.danger : t.textFaint;

  const toneFill = (tone: StateLabel['tone']): string =>
    tone === 'ok' ? t.okSoft : tone === 'warn' ? t.warnSoft : tone === 'bad' ? t.dangerSoft : t.fillSoft;

  const summary = fleet ? summarise(fleet) : null;

  return (
    <View style={styles.container}>
      {/* `glassSurface` is a translucent fill and needs something to be
          translucent over — see theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      <View style={[styles.header, { paddingTop: insets.top + space.lg }]}>
        <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>System status</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        contentContainerStyle={{ paddingBottom: insets.bottom + space.huge }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              void load();
            }}
          />
        }
      >
        <Text style={styles.intro}>
          Meridian runs several background parts that keep your map current. This page says whether
          each one is working, so you are never guessing whether a quiet map means a quiet city.
        </Text>

        {loading ? (
          <View style={styles.centred}>
            <ActivityIndicator size="small" color={t.brand} />
          </View>
        ) : null}

        {failed ? (
          <View style={[styles.banner, { backgroundColor: toneFill('bad') }]}>
            <Ionicons name="cloud-offline-outline" size={20} color={t.danger} />
            <Text style={styles.bannerText}>
              Could not reach Meridian to check. This says nothing about whether the background
              parts are working — only that we could not ask. Pull down to try again.
            </Text>
          </View>
        ) : null}

        {summary ? (
          <View style={[styles.banner, { backgroundColor: toneFill(summary.tone) }]}>
            <Ionicons
              name={summary.icon as keyof typeof Ionicons.glyphMap}
              size={20}
              color={toneColour(summary.tone)}
            />
            <Text style={styles.bannerText}>{summary.text}</Text>
          </View>
        ) : null}

        {fleet && fleet.mode === 'live' && fleet.agents.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>The parts</Text>
            {fleet.agents.map((agent) => {
              const described = describeAgent(agent.agent);
              // `?? unknown` is not defensive noise. The server owns this
              // vocabulary, so a state added there reaches an older build as a
              // key with no entry, and `label.text` on `undefined` would throw
              // inside a map callback — a blank screen instead of one unlabelled
              // card. `test_the_fleet_state_vocabulary_matches_the_client` is
              // what stops it reaching a release; this is what it does meanwhile.
              const label = STATE_LABELS[agent.state] ?? STATE_LABELS.unknown;
              const cadence = describeCadence(agent.cadenceSeconds);
              const unhealthy = agent.state === 'problem' || agent.state === 'late';
              return (
                <View key={agent.agent} style={styles.card}>
                  <View style={styles.cardHead}>
                    <Text style={styles.cardTitle}>{described.title}</Text>
                    <View style={[styles.pill, { backgroundColor: toneFill(label.tone) }]}>
                      <Text style={[styles.pillText, { color: toneColour(label.tone) }]}>
                        {label.text}
                      </Text>
                    </View>
                  </View>

                  <Text style={styles.cardMeta}>
                    Last ran {describeAge(agent.secondsSinceLastRun)}
                    {cadence ? ` · runs ${cadence}` : ''}
                  </Text>

                  <Text style={styles.cardBlurb}>{described.blurb}</Text>

                  {/* The reassurance, and only where it is true. Shown for a
                      part that is behind or down but does not change what the
                      user sees — `expiry_sweep` is the real case. */}
                  {unhealthy && !described.affectsWhatYouSee ? (
                    <View style={styles.note}>
                      <Ionicons name="information-circle-outline" size={16} color={t.info} />
                      <Text style={styles.noteText}>
                        Nothing on your map is wrong because of this. It is our housekeeping to fix.
                      </Text>
                    </View>
                  ) : null}

                  {unhealthy && described.affectsWhatYouSee ? (
                    <View style={styles.note}>
                      <Ionicons name="alert-circle-outline" size={16} color={t.warn} />
                      <Text style={styles.noteText}>
                        While this is behind, treat what you see here as possibly incomplete — and
                        keep using your own judgement about where you are going.
                      </Text>
                    </View>
                  ) : null}
                </View>
              );
            })}

            {/* A wall-clock time, not "checked 4 minutes ago". A relative age
                here would mean calling `Date.now()` during render, which is
                impure and recomputes on every unrelated re-render
                (`react-hooks/purity` — the rule MapScreen already trips). A
                clock time is also simply better: it stays correct however long
                the screen sits open, where a frozen relative age would not. */}
            <Text style={styles.footnote}>
              Checked at {fleet.checkedAt.toLocaleTimeString()}. Pull down to check again.
            </Text>
          </>
        ) : null}
      </ScrollView>
    </View>
  );
};

export default SystemStatusScreen;

const makeStyles = (t: Palette) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: t.bg },
    centred: { alignItems: 'center', justifyContent: 'center', paddingVertical: space.xl },
    header: {
      ...glassBar(t),
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: space.xl,
      paddingBottom: space.lg,
    },
    backButton: { padding: space.sm },
    headerTitle: { ...type.heading, color: t.text },
    headerSpacer: { width: 40 },
    intro: {
      ...type.small,
      color: t.textSoft,
      marginHorizontal: space.xl,
      marginTop: space.xl,
      marginBottom: space.lg,
    },
    sectionTitle: {
      ...type.overline,
      color: t.textFaint,
      marginTop: space.xl,
      marginBottom: space.sm,
      marginHorizontal: space.xl,
    },
    banner: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: space.md,
      marginHorizontal: space.xl,
      marginBottom: space.sm,
      padding: space.lg,
      borderRadius: radius.md,
    },
    bannerText: { ...type.small, color: t.text, flex: 1 },
    card: {
      ...glassSurface(t),
      marginHorizontal: space.xl,
      marginBottom: space.sm,
      padding: space.lg,
      gap: space.sm,
    },
    cardHead: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: space.md,
    },
    cardTitle: { ...type.bodyStrong, color: t.text, flex: 1 },
    pill: {
      paddingHorizontal: space.md,
      paddingVertical: space.xs,
      borderRadius: radius.pill,
    },
    pillText: { ...type.caption },
    cardMeta: { ...type.caption, color: t.textFaint },
    cardBlurb: { ...type.small, color: t.textSoft },
    note: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: space.sm,
      marginTop: space.xs,
    },
    noteText: { ...type.caption, color: t.textSoft, flex: 1 },
    footnote: {
      ...type.caption,
      color: t.textFaint,
      marginHorizontal: space.xl,
      marginTop: space.lg,
    },
  });
