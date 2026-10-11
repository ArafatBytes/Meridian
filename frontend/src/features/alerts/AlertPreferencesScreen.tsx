/**
 * Alert settings. B6a / S16, the user-facing half.
 *
 * S16 asks for "per-category user preferences". This is that screen, and it does
 * two other things that are not decoration:
 *
 * **It states the limits out loud.** The hourly cap, the severity floor, and —
 * the important one — that an alert is based on where the app last had your
 * location, because continuous background location is S17 and is not built. A
 * safety product that implies it is watching you walk when it is not is worse
 * than one that says plainly what it does. Both numbers come from the server
 * (`system_max_per_hour`, `location_max_age_hours`) rather than being written in
 * here, so they cannot drift from the values actually applied.
 *
 * **It makes the invisible checkable.** `Send a test alert` and the delivery
 * diagnosis answer "is this working?", and the alert history answers "why didn't
 * I get one?". Those two questions have no other answer: a notification that was
 * refused by the rate cap and one that was never sent because FCM credentials are
 * missing look identical from the lock screen.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import NotificationService from '../../services/notification.service';
import { borderRadius, fontSize, spacing } from '../../theme';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassBar, glassSurface } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily } from '../../theme/type';
import {
  blockingPushProblem,
  type AlertHistoryEntry,
  type AlertPreferences,
  type PushDiagnosis,
} from '../../types/contracts/notifications';
import type { ProfileStackParamList } from '../../types';

type Navigation = NativeStackNavigationProp<ProfileStackParamList, 'AlertPreferences'>;

interface Props {
  navigation: Navigation;
}

/**
 * The severity floor, as choices rather than a slider.
 *
 * A slider over 0–100 invites precision that does not exist — the difference
 * between 43 and 47 is noise, and nobody can predict what either will do to how
 * often their phone buzzes. Four labelled steps describe the *consequence*, which
 * is the thing being chosen.
 */
const SEVERITY_STEPS: readonly { value: number; label: string; hint: string }[] = [
  { value: 20, label: 'Everything', hint: 'Including minor delays' },
  { value: 40, label: 'Moderate and above', hint: 'The default' },
  { value: 60, label: 'Serious only', hint: 'Fewer alerts' },
  { value: 80, label: 'Severe only', hint: 'Rarely' },
];

const QUIET_NIGHT = { start: 22, end: 7 };

const AlertPreferencesScreen: React.FC<Props> = ({ navigation }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();
  const [prefs, setPrefs] = useState<AlertPreferences | null>(null);
  const [systemCap, setSystemCap] = useState<number | null>(null);
  const [locationMaxAgeHours, setLocationMaxAgeHours] = useState<number | null>(null);
  const [diagnosis, setDiagnosis] = useState<PushDiagnosis | null>(null);
  const [history, setHistory] = useState<AlertHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [settings, diag, past] = await Promise.all([
        NotificationService.getPreferences(),
        NotificationService.diagnose(),
        NotificationService.getHistory(20),
      ]);
      setPrefs(settings.preferences);
      setSystemCap(settings.systemMaxPerHour);
      setLocationMaxAgeHours(settings.locationMaxAgeHours);
      setDiagnosis(diag);
      setHistory(past);
    } catch (error: any) {
      Alert.alert(
        'Could not load alert settings',
        error?.message ?? 'The server did not answer.',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /**
   * Save, optimistically.
   *
   * The switch moves immediately and reverts if the server refuses. A switch that
   * waits for a round trip feels broken on a Dhaka mobile connection, and the
   * failure case here is recoverable and visible.
   */
  const update = async (patch: Partial<AlertPreferences>) => {
    if (!prefs) return;
    const previous = prefs;
    const next = { ...prefs, ...patch };
    setPrefs(next);
    setSaving(true);
    try {
      setPrefs(await NotificationService.savePreferences(next));
    } catch (error: any) {
      setPrefs(previous);
      Alert.alert('Not saved', error?.message ?? 'The server rejected the change.');
    } finally {
      setSaving(false);
    }
  };

  const onToggleChronic = (value: boolean) => {
    if (!value) {
      update({ chronic_alerts: false });
      return;
    }
    // Confirmed rather than silently applied, because the cost is not obvious
    // from the label. Dhaka has dozens of chronic flags, each good for one
    // alert, and they draw on the same hourly budget as alerts about things
    // actually happening now.
    Alert.alert(
      'Turn on historical alerts?',
      'These are long-term patterns, not events happening now. They cover large ' +
        'areas, there are many of them, and they share your hourly alert limit ' +
        'with alerts about live incidents.',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Turn on', onPress: () => update({ chronic_alerts: true }) },
      ],
    );
  };

  const onTest = async () => {
    setTesting(true);
    try {
      const result = await NotificationService.sendTestAlert();
      // `detail` is rendered verbatim. The server distinguishes "no device
      // registered" from "rate cap reached" from "Expo rejected it", and
      // collapsing those into "failed" would throw away the diagnosis.
      Alert.alert(result.sent > 0 ? 'Test alert sent' : 'Nothing sent', result.detail);
      setHistory(await NotificationService.getHistory(20));
    } catch (error: any) {
      Alert.alert('Test failed', error?.message ?? 'The server did not answer.');
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.centred]}>
        <ActivityIndicator size="large" color={t.brand} />
      </View>
    );
  }

  const problem = diagnosis ? blockingPushProblem(diagnosis) : null;
  const quietOn = prefs?.quiet_hours_start !== null && prefs?.quiet_hours_start !== undefined;

  return (
    <View style={styles.container}>
      {/* The ambient field, behind everything. `glassSurface` is a
          translucent fill and needs something to be translucent over —
          see the note in theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Alerts</Text>
        <View style={styles.headerSpacer}>
          {saving ? <ActivityIndicator size="small" color={t.brand} /> : null}
        </View>
      </View>

      <ScrollView
        contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xxl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      >
        {/* The blocking problem, if any, before anything else — toggling
            preferences is pointless while push cannot be delivered at all. */}
        {problem ? (
          <View style={styles.problem}>
            <Ionicons name="alert-circle" size={18} color={t.warn} />
            <Text style={styles.problemText}>{problem}</Text>
          </View>
        ) : null}

        {/* The honest limit. Stated first among the explanatory text because it
            is the one a user would otherwise assume the opposite of. */}
        <View style={styles.notice}>
          <Ionicons name="information-circle-outline" size={18} color={t.info} />
          <Text style={styles.noticeText}>
            Alerts are based on where the app last had your location — Meridian does
            not track you in the background, so it cannot warn you as you walk
            toward something. Open the app to refresh your position.
            {locationMaxAgeHours
              ? ` A position older than ${Math.round(locationMaxAgeHours)} hours is not used.`
              : ''}
          </Text>
        </View>

        <Text style={styles.sectionTitle}>What to alert me about</Text>

        <Row
          icon="navigate-circle-outline"
          title="Happening now"
          subtitle="A road affected near where you last were"
          value={prefs?.corridor_alerts ?? false}
          onChange={value => update({ corridor_alerts: value })}
        />
        <Row
          icon="time-outline"
          title="Expected later today"
          subtitle="Announced in advance — a road due to be blocked"
          value={prefs?.scheduled_alerts ?? false}
          onChange={value => update({ scheduled_alerts: value })}
        />
        <Row
          icon="layers-outline"
          title="Historical patterns"
          subtitle="Long-term records, not live events. Off by default."
          value={prefs?.chronic_alerts ?? false}
          onChange={onToggleChronic}
        />

        <Text style={styles.sectionTitle}>How much is worth a buzz</Text>
        <View style={styles.chips}>
          {SEVERITY_STEPS.map(step => {
            const active = prefs?.min_severity === step.value;
            return (
              <TouchableOpacity
                key={step.value}
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => update({ min_severity: step.value })}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>
                  {step.label}
                </Text>
                <Text style={[styles.chipHint, active && styles.chipHintActive]}>
                  {step.hint}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <Text style={styles.sectionTitle}>Quiet hours</Text>
        <Row
          icon="moon-outline"
          title={`Silence ${QUIET_NIGHT.start}:00 – ${QUIET_NIGHT.end}:00`}
          subtitle="Dhaka time. Emergency SOS is never silenced."
          value={quietOn}
          onChange={value =>
            update(
              value
                ? { quiet_hours_start: QUIET_NIGHT.start, quiet_hours_end: QUIET_NIGHT.end }
                : { quiet_hours_start: null, quiet_hours_end: null },
            )
          }
        />

        {/* The cap, read from the server. Phrased as a promise rather than a
            setting, because it is one: the user cannot raise it. */}
        {systemCap !== null ? (
          <View style={styles.notice}>
            <Ionicons name="shield-checkmark-outline" size={18} color={t.ok} />
            <Text style={styles.noticeText}>
              At most {systemCap} alert{systemCap === 1 ? '' : 's'} per hour, whatever
              happens. You can ask for fewer, never more.
            </Text>
          </View>
        ) : null}

        <TouchableOpacity
          style={[styles.testButton, testing && styles.testButtonDisabled]}
          onPress={onTest}
          disabled={testing}
        >
          {testing ? (
            <ActivityIndicator size="small" color={t.onBrand} />
          ) : (
            <Ionicons name="paper-plane-outline" size={18} color={t.onBrand} />
          )}
          <Text style={styles.testButtonText}>
            {testing ? 'Sending…' : 'Send me a test alert'}
          </Text>
        </TouchableOpacity>

        <Text style={styles.sectionTitle}>Recent alerts</Text>
        {history.length === 0 ? (
          <Text style={styles.empty}>
            Nothing yet. Anything Meridian sends you will be listed here, including
            why it was or was not delivered.
          </Text>
        ) : (
          history.map(entry => (
            <View key={`${entry.flag_id}-${entry.sent_at}`} style={styles.historyRow}>
              <View
                style={[
                  styles.historyDot,
                  {
                    backgroundColor:
                      entry.delivery === 'accepted'
                        ? t.ok
                        : entry.delivery === 'rejected'
                          ? t.danger
                          : t.textFaint,
                  },
                ]}
              />
              <View style={styles.historyBody}>
                {/* Rendered verbatim: this is the server-framed text as it was
                    sent. The screen composes nothing about any place. */}
                <Text style={styles.historyText}>{entry.body}</Text>
                <Text style={styles.historyMeta}>
                  {new Date(entry.sent_at).toLocaleString()} · {entry.category}
                  {entry.error ? ` · ${entry.error}` : ''}
                </Text>
              </View>
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
};

const Row: React.FC<{
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  value: boolean;
  onChange: (value: boolean) => void;
}> = ({ icon, title, subtitle, value, onChange }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  return (
  <View style={styles.row}>
    <Ionicons name={icon} size={22} color={t.textSoft} />
    <View style={styles.rowBody}>
      <Text style={styles.rowTitle}>{title}</Text>
      <Text style={styles.rowSubtitle}>{subtitle}</Text>
    </View>
    <Switch
      value={value}
      onValueChange={onChange}
      trackColor={{ false: t.line, true: t.brandStrong }}
      thumbColor={value ? t.brand : t.textFaint}
    />
  </View>
  );
};

export default AlertPreferencesScreen;

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: { flex: 1, backgroundColor: t.bg },
    centred: { alignItems: 'center', justifyContent: 'center' },
    header: {
      ...glassBar(t),
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: spacing.lg,
      paddingBottom: spacing.md,
    },
    backButton: { padding: spacing.sm },
    headerTitle: { fontFamily: fontFamily.display, fontSize: fontSize.xl,color: t.text },
    headerSpacer: { width: 40, alignItems: 'center' },
    sectionTitle: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.sm,
      color: t.textFaint,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      marginTop: spacing.xl,
      marginBottom: spacing.sm,
      marginHorizontal: spacing.lg,
    },
    row: {
      ...glassSurface(t),
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      marginHorizontal: spacing.lg,
      marginBottom: spacing.sm,
    },
    rowBody: { flex: 1 },
    rowTitle: { fontFamily: fontFamily.bodySemi, fontSize: fontSize.md,color: t.text },
    rowSubtitle: { fontFamily: fontFamily.body, fontSize: fontSize.xs, color: t.textSoft, marginTop: 2 },
    chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, paddingHorizontal: spacing.lg },
    chip: {
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: borderRadius.md,
      backgroundColor: t.lineSoft,
      borderWidth: 1,
      borderColor: t.lineSoft,
    },
    chipActive: { backgroundColor: t.brandStrong, borderColor: t.brand },
    chipText: { fontFamily: fontFamily.bodySemi, fontSize: fontSize.sm,color: t.textSoft },
    chipTextActive: { color: t.onBrand },
    chipHint: { fontFamily: fontFamily.body, fontSize: 10, color: t.textFaint },
    chipHintActive: { color: t.onBrand, opacity: 0.85 },
    notice: {
      flexDirection: 'row',
      gap: spacing.sm,
      alignItems: 'flex-start',
      backgroundColor: t.lineSoft,
      padding: spacing.md,
      marginHorizontal: spacing.lg,
      marginTop: spacing.md,
      borderRadius: borderRadius.md,
    },
    noticeText: { fontFamily: fontFamily.body, flex: 1, fontSize: fontSize.xs, color: t.textSoft, lineHeight: 17 },
    problem: {
      flexDirection: 'row',
      gap: spacing.sm,
      alignItems: 'flex-start',
      backgroundColor: 'rgba(245, 158, 11, 0.12)',
      padding: spacing.md,
      marginHorizontal: spacing.lg,
      marginTop: spacing.md,
      borderRadius: borderRadius.md,
      borderWidth: 1,
      borderColor: t.warn,
    },
    problemText: { fontFamily: fontFamily.body, flex: 1, fontSize: fontSize.sm, color: t.text, lineHeight: 18 },
    testButton: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: spacing.sm,
      backgroundColor: t.brand,
      paddingVertical: spacing.md,
      marginHorizontal: spacing.lg,
      marginTop: spacing.xl,
      borderRadius: borderRadius.md,
    },
    testButtonDisabled: { opacity: 0.6 },
    testButtonText: { fontFamily: fontFamily.bodySemi, color: t.onBrand, fontSize: fontSize.md,},
    empty: {
      fontFamily: fontFamily.body,
      fontSize: fontSize.xs,
      color: t.textFaint,
      marginHorizontal: spacing.lg,
      lineHeight: 17,
    },
    historyRow: {
      ...glassSurface(t),
      flexDirection: 'row',
      gap: spacing.sm,
      alignItems: 'flex-start',
      padding: spacing.md,
      marginHorizontal: spacing.lg,
      marginBottom: spacing.sm,
    },
    historyDot: { width: 8, height: 8, borderRadius: 4, marginTop: 5 },
    historyBody: { flex: 1 },
    historyText: { fontFamily: fontFamily.body, fontSize: fontSize.sm, color: t.text, lineHeight: 18 },
    historyMeta: { fontFamily: fontFamily.body, fontSize: 10, color: t.textFaint, marginTop: 3 },
  });
