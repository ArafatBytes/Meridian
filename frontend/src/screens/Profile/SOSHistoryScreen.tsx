/**
 * Every SOS this user has sent. D09, the second half of demo beat 9.
 *
 * The beat is "trigger SOS, the email arrives — **and here is the record**". An
 * alert that vanishes after the alert is an alert nobody can check: not the person
 * who sent it, not a contact asking whether it really went out, not us. So each row
 * says when, where, how many people were notified, and whether it was delivered.
 *
 * Two things this screen deliberately does not show.
 *
 * **Who was notified.** The audit row holds contact *ids* and a count, never email
 * addresses — the addresses live in `emergency_contacts` and copying them into a
 * second table with its own lifetime would be duplicating personal data for a line
 * of text. "2 contacts notified" is the whole requirement.
 *
 * **The video.** It is attached to the alert and then deleted; nothing retains
 * footage recorded under duress, because that would need a bucket, a retention
 * window and an access policy that do not exist. The row records that a clip *was*
 * attached, which is the honest amount to claim.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { spacing, borderRadius, typography } from '../../theme';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily } from '../../theme/type';
import { sosService, type SosHistoryEntry } from '../../services/sos.service';
import { messageOf } from '../../services/casework.service';

/** "10 Oct 2026, 21:40" — a date, because an SOS from last month is not "3 weeks ago". */
function sentAt(iso: string): string {
  const at = new Date(iso);
  return `${at.toLocaleDateString([], {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })}, ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

/**
 * How the delivery state reads. Three states, not two.
 *
 * `null` is a row written before the audit blob existed, and it says so rather than
 * resolving to "failed" — telling someone their emergency alert failed when it did
 * not is the worse of the two errors available here.
 */
function delivery(entry: SosHistoryEntry, t: Palette): {
  label: string;
  colour: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
} {
  if (entry.delivered === true) {
    return { label: 'Delivered', colour: t.ok, icon: 'checkmark-circle' };
  }
  if (entry.delivered === false) {
    return { label: 'Not delivered', colour: t.danger, icon: 'close-circle' };
  }
  return { label: 'Delivery not recorded', colour: t.textSoft, icon: 'help-circle' };
}

const SOSHistoryScreen: React.FC = () => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();

  const [entries, setEntries] = useState<SosHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await sosService.getHistory();
      setEntries(result.incidents);
      setError(null);
    } catch (problem: any) {
      // No 404 special case: the endpoint answers an empty list for someone who
      // has never sent one, because "no alerts" is a fact about them, not a
      // missing resource.
      setError(messageOf(problem, 'Could not load your SOS history.'));
      setEntries([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* The ambient field, behind everything. `glassSurface` is a
          translucent fill and needs something to be translucent over —
          see the note in theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={12}>
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>SOS History</Text>
        <View style={{ width: 24 }} />
      </View>

      {entries === null ? (
        <View style={styles.centre}>
          <ActivityIndicator size="large" color={t.brand} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing.xl }]}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
        >
          {error && (
            <View style={styles.errorCard}>
              <Ionicons name="warning-outline" size={18} color={t.danger} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {!error && entries.length === 0 && (
            <View style={styles.emptyCard}>
              <Ionicons name="shield-checkmark-outline" size={40} color={t.textSoft} />
              <Text style={styles.emptyTitle}>No SOS alerts yet</Text>
              <Text style={styles.emptyText}>
                When you trigger an SOS, the record of it appears here — when it was sent,
                where you were, and whether it reached your contacts.
              </Text>
            </View>
          )}

          {entries.map(entry => {
            const state = delivery(entry, t);
            return (
              <View key={entry.id} style={styles.card}>
                <View style={styles.cardTop}>
                  <Text style={styles.when}>{sentAt(entry.timestamp)}</Text>
                  <View style={[styles.pill, { backgroundColor: `${state.colour}22` }]}>
                    <Ionicons name={state.icon} size={13} color={state.colour} />
                    <Text style={[styles.pillText, { color: state.colour }]}>{state.label}</Text>
                  </View>
                </View>

                <Text style={styles.detail}>
                  {entry.recipient_count === 0
                    ? 'No contacts were notified'
                    : `${entry.recipient_count} ${
                        entry.recipient_count === 1 ? 'contact' : 'contacts'
                      } notified`}
                </Text>

                <Text style={styles.coords}>
                  {/* Six decimals is about 10 cm, which is more precision than the
                      fix has. Five is the honest width for a phone GPS reading. */}
                  {entry.latitude.toFixed(5)}, {entry.longitude.toFixed(5)}
                </Text>

                <View style={styles.tags}>
                  {entry.video_attached && (
                    <View style={styles.tag}>
                      <Ionicons name="videocam-outline" size={12} color={t.textSoft} />
                      <Text style={styles.tagText}>Video attached</Text>
                    </View>
                  )}
                  {entry.voice_activated && (
                    <View style={styles.tag}>
                      <Ionicons name="mic-outline" size={12} color={t.textSoft} />
                      <Text style={styles.tagText}>Voice activated</Text>
                    </View>
                  )}
                  {entry.police_station_count > 0 && (
                    <View style={styles.tag}>
                      <Ionicons name="business-outline" size={12} color={t.textSoft} />
                      <Text style={styles.tagText}>
                        {entry.police_station_count} station
                        {entry.police_station_count === 1 ? '' : 's'}
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            );
          })}

          {entries.length > 0 && (
            <Text style={styles.footnote}>
              The video recorded with an alert is sent and then deleted — nothing keeps
              footage taken under duress. Contacts are recorded as a count, not as
              addresses.
            </Text>
          )}
        </ScrollView>
      )}
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: { flex: 1, backgroundColor: t.bg },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: spacing.lg,
      paddingVertical: spacing.md,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.line,
    },
    headerTitle: { ...typography.h4, color: t.text },
    centre: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    body: { padding: spacing.lg, gap: spacing.md },

    card: {
      ...glassSurface(t),
      padding: spacing.md,
      gap: spacing.xs,
    },
    cardTop: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: spacing.sm,
    },
    when: { ...typography.body, fontFamily: fontFamily.bodySemi, color: t.text, flexShrink: 1 },
    pill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: borderRadius.sm,
    },
    pillText: { ...typography.caption, fontFamily: fontFamily.bodySemi,},
    detail: { ...typography.bodySmall, color: t.text },
    coords: { ...typography.caption, color: t.textSoft },
    tags: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: 2 },
    tag: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      backgroundColor: t.lineSoft,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      borderRadius: borderRadius.sm,
    },
    tagText: { ...typography.caption, color: t.textSoft },

    errorCard: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      backgroundColor: `${t.danger}11`,
      borderRadius: borderRadius.md,
      padding: spacing.md,
    },
    errorText: { ...typography.bodySmall, color: t.danger, flex: 1 },

    emptyCard: {
      alignItems: 'center',
      gap: spacing.sm,
      paddingVertical: spacing.xxl,
      paddingHorizontal: spacing.lg,
    },
    emptyTitle: { ...typography.h4, color: t.text },
    emptyText: { ...typography.bodySmall, color: t.textSoft, textAlign: 'center' },

    footnote: {
      ...typography.caption,
      color: t.textSoft,
      marginTop: spacing.sm,
      lineHeight: 16,
    },
  });

export default SOSHistoryScreen;
