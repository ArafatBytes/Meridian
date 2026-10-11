/**
 * Guardian — the one screen where the automatic protections are armed, tuned
 * and proved. B6a / B8.
 *
 * Three features that share one job: noticing trouble without being asked.
 *
 *   Risk zone alerts   background GPS → a notification as you approach a flagged road
 *   Voice SOS          a shouted hot word → SOS, automatically
 *   Shake SOS          shaking the phone hard → SOS, automatically
 *
 * ## Why they live on one screen
 *
 * Because they are one promise to the user, and because **all three have a
 * threshold that is wrong until it is calibrated on the actual phone**. A shout
 * is a different number on every microphone; a violent shake is a different
 * number on every handset. So each section pairs its switch with a **live meter**
 * and a stepper, and the honest instruction is "watch the number, then set the
 * line just under it".
 *
 * That is also what makes the features demonstrable. Every one of them is
 * invisible by nature — a background geofence, a microphone, an accelerometer —
 * and "I shook it and nothing happened" has several possible causes. The meters
 * turn each of them into something you can point at.
 *
 * ## The limits are on the screen, not in a comment
 *
 * Voice SOS works while the app is open. It cannot run with the app closed:
 * Android has restricted microphone access for background apps since Android 9,
 * and holding the mic needs a foreground service that no Expo module provides.
 * Zone alerts *do* work with the app closed, because the OS does the watching.
 * Shake needs the app open, like voice.
 *
 * A user who believes all three are watching from a pocket is worse off than one
 * who knows which two are, so each section says which it is.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Accelerometer } from 'expo-sensors';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { borderRadius, colors, fontSize, spacing } from '../../theme';
import type { ProfileStackParamList } from '../../types';
import { downloadOfflineModel } from '../voice/recognizer';
import {
  SHAKE_RANGE,
  SHOUT_RANGE,
  useGuardianStore,
} from './guardianStore';
import { useLiveMeters } from './liveMeters';
import {
  refreshZones,
  simulateNearestZoneCrossing,
  stopZones,
  zoneWatchStatus,
  type ZoneWatchStatus,
} from '../geofence/service';
import { clearZoneLog, loadZoneLog, type ZoneEvent } from '../geofence/storage';

type Navigation = NativeStackNavigationProp<ProfileStackParamList, 'Guardian'>;

interface Props {
  navigation: Navigation;
}

/** Live accelerometer reading, for calibrating the shake threshold. */
function useShakeMeter(active: boolean): number {
  const [magnitude, setMagnitude] = useState(1);
  const peak = useRef(1);

  useEffect(() => {
    if (!active) return;
    // Separate from the trigger subscription in `GuardianProvider`, on purpose:
    // this one exists so the number can be *watched*, and it runs while the
    // screen is open whether or not shake-to-SOS is armed — you cannot calibrate
    // a threshold you have to arm first. Two accelerometer listeners is fine;
    // they are independent and the sensor is cheap.
    Accelerometer.setUpdateInterval(120);
    const subscription = Accelerometer.addListener(({ x, y, z }) => {
      const value = Math.sqrt(x * x + y * y + z * z);
      // Decay the peak rather than resetting it: an instantaneous readout of a
      // shake is unreadable, because the number is only high for ~100 ms.
      peak.current = Math.max(value, peak.current * 0.92);
      setMagnitude(peak.current);
    });
    return () => subscription?.remove();
  }, [active]);

  return magnitude;
}

export const GuardianScreen: React.FC<Props> = ({ navigation }) => {
  const insets = useSafeAreaInsets();

  const {
    zoneAlertsEnabled,
    voiceArmed,
    shakeEnabled,
    shoutThreshold,
    shakeThresholdG,
    confirmCountdown,
    setZoneAlertsEnabled,
    setVoiceArmed,
    setShakeEnabled,
    setShoutThreshold,
    setShakeThresholdG,
    setConfirmCountdown,
  } = useGuardianStore();

  const meters = useLiveMeters();
  const shakeMagnitude = useShakeMeter(true);

  const [zoneStatus, setZoneStatus] = useState<ZoneWatchStatus | null>(null);
  const [zoneLog, setZoneLog] = useState<ZoneEvent[]>([]);
  const [zoneBusy, setZoneBusy] = useState(false);

  /**
   * Read the zone state for the status block. Never rejects.
   *
   * This runs on mount, before the user has granted anything, and it is called
   * again by pull-to-refresh. `zoneWatchStatus` is written not to throw, but this
   * is a mount path and the cost of being wrong about that is an unhandled
   * rejection in a red box over the screen — which is how the
   * `hasStartedGeofencingAsync` / "Not authorized to use background location
   * services" rejection first showed up. A status block that renders nothing is
   * recoverable; a screen that throws on open is not.
   */
  const loadZoneState = useCallback(async () => {
    try {
      setZoneStatus(await zoneWatchStatus());
    } catch (problem) {
      console.warn('Could not read zone status:', problem);
    }
    try {
      setZoneLog(await loadZoneLog());
    } catch (problem) {
      console.warn('Could not read the zone log:', problem);
    }
  }, []);

  useEffect(() => {
    void loadZoneState();
  }, [loadZoneState]);

  // -----------------------------------------------------------------------
  // Zone alerts
  // -----------------------------------------------------------------------

  const onToggleZones = async (value: boolean) => {
    setZoneBusy(true);
    try {
      if (!value) {
        await stopZones();
        setZoneAlertsEnabled(false);
        await loadZoneState();
        return;
      }
      const status = await refreshZones();
      setZoneStatus(status);
      if (status.permission !== 'granted') {
        setZoneAlertsEnabled(false);
        Alert.alert(
          'Location permission needed',
          status.permission === 'no-background'
            ? 'Zone alerts need location access "all the time". Android only offers that ' +
                'in system settings — open Meridian\'s permissions and choose ' +
                '"Allow all the time", then switch this on again.'
            : 'Meridian needs location access to know when you are near a flagged road.',
          [
            { text: 'Not now', style: 'cancel' },
            { text: 'Open settings', onPress: () => Linking.openSettings() },
          ],
        );
        return;
      }
      setZoneAlertsEnabled(true);
      if (status.regionCount === 0) {
        Alert.alert(
          'Nothing to watch yet',
          'No live risk flags near you cleared the threshold, so there is nothing to ' +
            'monitor. Zone alerts are on and will pick up new flags next time you open ' +
            'the app.',
        );
      }
      await loadZoneState();
    } catch (problem: any) {
      setZoneAlertsEnabled(false);
      Alert.alert('Could not start zone alerts', problem?.message ?? 'Unknown error.');
    } finally {
      setZoneBusy(false);
    }
  };

  /**
   * Prove the alert path without walking to a flagged road.
   *
   * Runs the same code the background task runs on a real crossing — same zone
   * table, same debounce, same notification. The only thing simulated is Android
   * deciding you moved, which cannot be done in a room.
   */
  const onTestZoneAlert = async () => {
    setZoneBusy(true);
    try {
      const result = await simulateNearestZoneCrossing();
      Alert.alert(
        result.ok ? 'Zone alert sent' : 'Nothing sent',
        result.detail,
      );
      await loadZoneState();
    } catch (problem: any) {
      Alert.alert('Test failed', problem?.message ?? 'Unknown error.');
    } finally {
      setZoneBusy(false);
    }
  };

  const onRefreshZones = async () => {
    setZoneBusy(true);
    try {
      setZoneStatus(await refreshZones());
      await loadZoneState();
    } catch (problem: any) {
      Alert.alert('Refresh failed', problem?.message ?? 'Unknown error.');
    } finally {
      setZoneBusy(false);
    }
  };

  // -----------------------------------------------------------------------
  // Voice
  // -----------------------------------------------------------------------

  const onToggleVoice = (value: boolean) => {
    // The guard does its own preflight and will switch this back off with a
    // reason if the phone cannot listen privately — so the switch is set
    // optimistically and `meters.unavailable` is what reports the outcome.
    setVoiceArmed(value);
  };

  const onDownloadPack = async () => {
    try {
      const result = await downloadOfflineModel('en-US');
      Alert.alert(
        'Offline language pack',
        result.status === 'opened_dialog'
          ? 'Android has opened its download dialog. Finish it, then come back and arm ' +
              'Voice SOS again — the system does not tell the app when it is done.'
          : `${result.status.replace('_', ' ')}: ${result.message}`,
      );
    } catch (problem: any) {
      Alert.alert('Could not request the language pack', problem?.message ?? 'Unknown error.');
    }
  };

  const shoutReady = meters.peakLoudness >= shoutThreshold;
  const shakeReady = shakeMagnitude >= shakeThresholdG;

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Guardian</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xxl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={loadZoneState} />}
      >
        <Text style={styles.intro}>
          Three ways Meridian can act without being asked. Each one needs a threshold
          that is different on every phone — watch the live reading, then set the line
          just under what you can reach.
        </Text>

        {/* ============================= ZONES ============================= */}
        <Text style={styles.sectionTitle}>Risk zone alerts</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Ionicons name="navigate-circle-outline" size={22} color={colors.textSecondary} />
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>Warn me as I approach</Text>
              <Text style={styles.rowSubtitle}>
                Works with the app closed. The phone&apos;s own geofencing watches the
                zones, so this costs very little battery.
              </Text>
            </View>
            {zoneBusy ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Switch
                value={zoneAlertsEnabled}
                onValueChange={onToggleZones}
                trackColor={{ false: colors.border, true: colors.primaryLight }}
                thumbColor={zoneAlertsEnabled ? colors.primary : colors.gray400}
              />
            )}
          </View>

          {zoneStatus ? (
            <View style={styles.statusBox}>
              <StatusLine
                label="System monitoring"
                // Three states, not two. "Not running" because nothing qualified
                // is a correct, healthy outcome — the OS is not asked to watch an
                // empty region set — and showing it in warning yellow beside
                // "Zones being watched: 0" made a working app look broken. Which
                // is exactly what happened on the first run away from Dhaka.
                value={
                  zoneStatus.monitoring
                    ? 'Active'
                    : zoneStatus.permission === 'granted' && zoneStatus.regionCount === 0
                      ? 'Idle — nothing nearby to watch'
                      : 'Not running'
                }
                good={
                  zoneStatus.monitoring ||
                  (zoneStatus.permission === 'granted' && zoneStatus.regionCount === 0)
                }
              />
              <StatusLine
                label="Location permission"
                value={
                  zoneStatus.permission === 'granted'
                    ? 'All the time'
                    : zoneStatus.permission === 'no-background'
                      ? 'Only while app is open'
                      : 'Not granted'
                }
                good={zoneStatus.permission === 'granted'}
              />
              <StatusLine
                label="Zones being watched"
                value={String(zoneStatus.regionCount)}
                // Zero is only a problem if we were never allowed to look. With
                // permission granted it means there is no live flag within about
                // 19 km, which is the honest answer and not a fault.
                good={zoneStatus.regionCount > 0 || zoneStatus.permission === 'granted'}
              />
              {zoneStatus.dropped > 0 ? (
                <StatusLine
                  label="Not watched (over the limit)"
                  value={String(zoneStatus.dropped)}
                  good={false}
                />
              ) : null}
              {/* The "0 zones" case needs its own sentence. Without it the user
                  is left reading "0 skipped for that reason" and concluding the
                  feature is broken, when the truth is that there is no live flag
                  within reach of where they are standing. */}
              {zoneStatus.regionCount === 0 && zoneStatus.permission === 'granted' ? (
                <Text style={styles.statusNote}>
                  No live risk flag within about 19 km of you, so there is nothing to
                  watch. This is working correctly — zone alerts stay on and will pick
                  up flags as soon as you are near some, or next time you open the app.
                </Text>
              ) : (
                <Text style={styles.statusNote}>
                  Historical-pattern zones are never watched — they cover kilometres and
                  never expire, so a geofence on one would fire every time you left the
                  house. {zoneStatus.skipped.chronic} skipped for that reason,{' '}
                  {zoneStatus.skipped.lowSeverity} as too minor to interrupt you.
                </Text>
              )}
            </View>
          ) : null}

          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={onRefreshZones}
              disabled={zoneBusy}
            >
              <Ionicons name="refresh" size={16} color={colors.primary} />
              <Text style={styles.secondaryButtonText}>Refresh zones</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={() => Linking.openSettings()}
            >
              <Ionicons name="settings-outline" size={16} color={colors.primary} />
              <Text style={styles.secondaryButtonText}>Permissions</Text>
            </TouchableOpacity>
          </View>

          {/* The only way to show this feature indoors. A real crossing needs the
              person to physically walk through a boundary hundreds of metres
              wide, which is not a step anybody can run in front of an audience. */}
          <TouchableOpacity
            style={[styles.testButton, zoneBusy && styles.testButtonDisabled]}
            onPress={onTestZoneAlert}
            disabled={zoneBusy}
          >
            <Ionicons name="flash-outline" size={18} color={colors.white} />
            <Text style={styles.testButtonText}>Test the nearest zone now</Text>
          </TouchableOpacity>
          <Text style={styles.statusNote}>
            Runs the real alert — same zones, same six-hour debounce, same
            notification. Only the &quot;you moved&quot; part is simulated.
          </Text>
        </View>

        {/* ============================= VOICE ============================= */}
        <Text style={styles.sectionTitle}>Voice SOS — shout a hot word</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Ionicons
              name={meters.listening ? 'mic' : 'mic-off-outline'}
              size={22}
              color={meters.listening ? colors.error : colors.textSecondary}
            />
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>
                {meters.listening ? 'Listening on this device' : 'Listen for my phrase'}
              </Text>
              <Text style={styles.rowSubtitle}>
                Only while the app is open — Android does not let any app hold the
                microphone in the background. No audio leaves the phone.
              </Text>
            </View>
            <Switch
              value={voiceArmed}
              onValueChange={onToggleVoice}
              trackColor={{ false: colors.border, true: colors.primaryLight }}
              thumbColor={voiceArmed ? colors.error : colors.gray400}
            />
          </View>

          {meters.unavailable ? (
            <View style={styles.problem}>
              <Ionicons name="alert-circle" size={16} color={colors.warning} />
              <Text style={styles.problemText}>{meters.unavailable}</Text>
            </View>
          ) : null}

          {meters.unavailable?.includes('language pack') ? (
            <TouchableOpacity style={styles.secondaryButton} onPress={onDownloadPack}>
              <Ionicons name="cloud-download-outline" size={16} color={colors.primary} />
              <Text style={styles.secondaryButtonText}>Install an offline language pack</Text>
            </TouchableOpacity>
          ) : null}

          {/* The meter. Without it the shout threshold is unsettable: the scale is
              Android's RMS value, not decibels, and it means something different
              on every microphone. */}
          <Meter
            label="Loudness now"
            value={meters.loudness}
            peak={meters.peakLoudness}
            min={-2}
            max={10}
            threshold={shoutThreshold}
            ready={shoutReady}
            idle={!meters.listening}
          />
          <Stepper
            label="Shout threshold"
            value={shoutThreshold}
            onChange={setShoutThreshold}
            min={SHOUT_RANGE.min}
            max={SHOUT_RANGE.max}
            step={0.5}
            hint="Arm it, speak normally, then shout. Set the line between the two."
          />

          {meters.listening ? (
            <View style={styles.heardBox}>
              <Text style={styles.heardLabel}>Heard · stays on this phone</Text>
              <Text style={styles.heardText} numberOfLines={2}>
                {meters.heard ? `“${meters.heard}”` : 'Say something…'}
              </Text>
            </View>
          ) : null}

          {meters.error ? (
            <View style={styles.problem}>
              <Ionicons name="information-circle-outline" size={16} color={colors.info} />
              <Text style={styles.problemText}>{meters.error}</Text>
            </View>
          ) : null}

          <TouchableOpacity
            style={styles.linkRow}
            onPress={() => navigation.navigate('SOSHotWords')}
          >
            <Ionicons name="list-outline" size={16} color={colors.primary} />
            <Text style={styles.linkText}>Manage my hot words</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
          </TouchableOpacity>
        </View>

        {/* ============================= SHAKE ============================= */}
        <Text style={styles.sectionTitle}>Shake SOS</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Ionicons name="phone-portrait-outline" size={22} color={colors.textSecondary} />
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>Shake hard to call for help</Text>
              <Text style={styles.rowSubtitle}>
                Only while the app is open. Nothing is recorded until it triggers.
              </Text>
            </View>
            <Switch
              value={shakeEnabled}
              onValueChange={setShakeEnabled}
              trackColor={{ false: colors.border, true: colors.primaryLight }}
              thumbColor={shakeEnabled ? colors.error : colors.gray400}
            />
          </View>

          <Meter
            label="Shake force now"
            value={shakeMagnitude}
            peak={shakeMagnitude}
            min={0}
            max={SHAKE_RANGE.max + 2}
            threshold={shakeThresholdG}
            ready={shakeReady}
            unit="g"
          />
          <Stepper
            label="Shake threshold"
            value={shakeThresholdG}
            onChange={setShakeThresholdG}
            min={SHAKE_RANGE.min}
            max={SHAKE_RANGE.max}
            step={0.5}
            unit="g"
            hint="Shake as you would in an emergency, read the peak, then set the line below it. Resting is about 1g."
          />
        </View>

        {/* ========================== THE SAFETY NET ======================= */}
        <Text style={styles.sectionTitle}>When something triggers</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <Ionicons name="timer-outline" size={22} color={colors.textSecondary} />
            <View style={styles.rowBody}>
              <Text style={styles.rowTitle}>5-second cancel window</Text>
              <Text style={styles.rowSubtitle}>
                Still automatic — no tap needed. Turn this off to send the instant a
                trigger fires, once you trust your thresholds.
              </Text>
            </View>
            <Switch
              value={confirmCountdown}
              onValueChange={setConfirmCountdown}
              trackColor={{ false: colors.border, true: colors.primaryLight }}
              thumbColor={confirmCountdown ? colors.primary : colors.gray400}
            />
          </View>
          <Text style={styles.statusNote}>
            Either way, an SOS records a short video, takes your location, and emails
            your emergency contacts. Set those up first or there is nobody to alert.
          </Text>
        </View>

        {/* ============================ ZONE LOG =========================== */}
        <Text style={styles.sectionTitle}>Zone alert history</Text>
        {zoneLog.length === 0 ? (
          <Text style={styles.empty}>
            Nothing yet. Every zone crossing is listed here — including the ones that
            were suppressed, with the reason, so you can tell &quot;it worked and stayed
            quiet&quot; from &quot;it never fired&quot;.
          </Text>
        ) : (
          <>
            {zoneLog.map((event, index) => (
              <View key={`${event.flagId}-${event.at}-${index}`} style={styles.logRow}>
                <View
                  style={[
                    styles.logDot,
                    { backgroundColor: event.notified ? colors.success : colors.textMuted },
                  ]}
                />
                <View style={styles.rowBody}>
                  {/* Server-framed text, rendered verbatim. */}
                  <Text style={styles.logText}>{event.body}</Text>
                  <Text style={styles.logMeta}>
                    {new Date(event.at).toLocaleString()}
                    {event.notified ? ' · notified' : ` · suppressed: ${event.reason ?? '—'}`}
                  </Text>
                </View>
              </View>
            ))}
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={async () => {
                await clearZoneLog();
                setZoneLog([]);
              }}
            >
              <Ionicons name="trash-outline" size={16} color={colors.primary} />
              <Text style={styles.secondaryButtonText}>Clear history</Text>
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </View>
  );
};

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

const StatusLine: React.FC<{ label: string; value: string; good: boolean }> = ({
  label,
  value,
  good,
}) => (
  <View style={styles.statusLine}>
    <Ionicons
      name={good ? 'checkmark-circle' : 'close-circle'}
      size={14}
      color={good ? colors.success : colors.warning}
    />
    <Text style={styles.statusLabel}>{label}</Text>
    <Text style={[styles.statusValue, { color: good ? colors.success : colors.warning }]}>
      {value}
    </Text>
  </View>
);

/**
 * A live bar with the threshold drawn on it.
 *
 * The threshold marker is the whole point: a number on its own tells you nothing
 * about whether you can reach it, and "shout and see if the bar passes the line"
 * is a calibration anybody can do in five seconds.
 */
const Meter: React.FC<{
  label: string;
  value: number;
  peak: number;
  min: number;
  max: number;
  threshold: number;
  ready: boolean;
  unit?: string;
  idle?: boolean;
}> = ({ label, value, peak, min, max, threshold, ready, unit = '', idle = false }) => {
  const pct = (input: number) =>
    Math.max(0, Math.min(100, ((input - min) / (max - min)) * 100));
  return (
    <View style={styles.meterWrap}>
      <View style={styles.meterHead}>
        <Text style={styles.meterLabel}>{label}</Text>
        <Text style={[styles.meterValue, ready && !idle && styles.meterValueHot]}>
          {idle ? '—' : `${value.toFixed(1)}${unit}`}
          {!idle && peak > value ? `  (peak ${peak.toFixed(1)}${unit})` : ''}
        </Text>
      </View>
      <View style={styles.meterTrack}>
        <View
          style={[
            styles.meterFill,
            {
              width: `${idle ? 0 : pct(value)}%`,
              backgroundColor: ready && !idle ? colors.error : colors.primary,
            },
          ]}
        />
        {!idle && peak > value ? (
          <View style={[styles.meterPeak, { left: `${pct(peak)}%` }]} />
        ) : null}
        <View style={[styles.meterThreshold, { left: `${pct(threshold)}%` }]} />
      </View>
    </View>
  );
};

const Stepper: React.FC<{
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  unit?: string;
  hint?: string;
}> = ({ label, value, onChange, min, max, step, unit = '', hint }) => (
  <View style={styles.stepperWrap}>
    <View style={styles.stepperRow}>
      <Text style={styles.stepperLabel}>{label}</Text>
      <View style={styles.stepperControls}>
        <TouchableOpacity
          style={styles.stepperButton}
          onPress={() => onChange(Math.max(min, Number((value - step).toFixed(1))))}
          disabled={value <= min}
        >
          <Ionicons name="remove" size={18} color={colors.primary} />
        </TouchableOpacity>
        <Text style={styles.stepperValue}>
          {value.toFixed(1)}
          {unit}
        </Text>
        <TouchableOpacity
          style={styles.stepperButton}
          onPress={() => onChange(Math.min(max, Number((value + step).toFixed(1))))}
          disabled={value >= max}
        >
          <Ionicons name="add" size={18} color={colors.primary} />
        </TouchableOpacity>
      </View>
    </View>
    {hint ? <Text style={styles.stepperHint}>{hint}</Text> : null}
  </View>
);

export default GuardianScreen;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: { padding: spacing.sm },
  headerTitle: { fontSize: fontSize.xl, fontWeight: 'bold', color: colors.text },
  headerSpacer: { width: 40 },
  intro: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    lineHeight: 17,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
    marginHorizontal: spacing.lg,
  },
  card: {
    backgroundColor: colors.white,
    marginHorizontal: spacing.lg,
    padding: spacing.lg,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  rowBody: { flex: 1 },
  rowTitle: { fontSize: fontSize.md, fontWeight: '600', color: colors.text },
  rowSubtitle: { fontSize: fontSize.xs, color: colors.textSecondary, marginTop: 2, lineHeight: 16 },
  statusBox: {
    backgroundColor: colors.surfaceVariant,
    borderRadius: borderRadius.sm,
    padding: spacing.md,
    gap: 4,
  },
  statusLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  statusLabel: { flex: 1, fontSize: fontSize.xs, color: colors.textSecondary },
  statusValue: { fontSize: fontSize.xs, fontWeight: '700' },
  statusNote: {
    fontSize: 11,
    color: colors.textMuted,
    lineHeight: 15,
    marginTop: spacing.xs,
  },
  buttonRow: { flexDirection: 'row', gap: spacing.sm },
  secondaryButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  secondaryButtonText: { fontSize: fontSize.xs, color: colors.primary, fontWeight: '600' },
  problem: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'flex-start',
    backgroundColor: colors.surfaceVariant,
    padding: spacing.md,
    borderRadius: borderRadius.sm,
  },
  problemText: { flex: 1, fontSize: fontSize.xs, color: colors.text, lineHeight: 17 },
  meterWrap: { gap: 4, marginTop: spacing.xs },
  meterHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  meterLabel: { fontSize: fontSize.xs, color: colors.textSecondary },
  meterValue: {
    fontSize: fontSize.xs,
    fontWeight: '700',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  meterValueHot: { color: colors.error },
  meterTrack: {
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.surfaceVariant,
    overflow: 'visible',
    justifyContent: 'center',
  },
  meterFill: { height: 10, borderRadius: 5 },
  meterPeak: {
    position: 'absolute',
    width: 2,
    height: 10,
    backgroundColor: colors.textMuted,
  },
  meterThreshold: {
    position: 'absolute',
    width: 3,
    height: 18,
    borderRadius: 2,
    backgroundColor: colors.text,
  },
  stepperWrap: { marginTop: spacing.sm },
  stepperRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  stepperLabel: { fontSize: fontSize.sm, color: colors.text, fontWeight: '600' },
  stepperControls: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  stepperButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepperValue: {
    minWidth: 48,
    textAlign: 'center',
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.text,
    fontVariant: ['tabular-nums'],
  },
  stepperHint: { fontSize: 11, color: colors.textMuted, marginTop: 4, lineHeight: 15 },
  heardBox: {
    backgroundColor: colors.surfaceVariant,
    borderRadius: borderRadius.sm,
    padding: spacing.md,
  },
  heardLabel: {
    fontSize: 10,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  heardText: { fontSize: fontSize.sm, color: colors.text, marginTop: 2, fontStyle: 'italic' },
  testButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    marginTop: spacing.xs,
  },
  testButtonDisabled: { opacity: 0.6 },
  testButtonText: { color: colors.white, fontSize: fontSize.sm, fontWeight: '700' },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  linkText: { flex: 1, fontSize: fontSize.sm, color: colors.primary, fontWeight: '600' },
  empty: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginHorizontal: spacing.lg,
    lineHeight: 17,
  },
  logRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'flex-start',
    backgroundColor: colors.white,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: borderRadius.md,
  },
  logDot: { width: 8, height: 8, borderRadius: 4, marginTop: 5 },
  logText: { fontSize: fontSize.sm, color: colors.text, lineHeight: 18 },
  logMeta: { fontSize: 10, color: colors.textMuted, marginTop: 3 },
});
