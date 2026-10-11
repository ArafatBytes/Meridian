/**
 * The modals an SOS puts on screen: the camera, the progress overlay, then the
 * outcome.
 *
 * Separate from `useSOS` so that a screen adds SOS with one element rather than
 * forty lines of copied JSX — which is how `MapScreen` ended up with a red button
 * and no implementation behind it (defect 14).
 */
import React from 'react';
import { View, Text, StyleSheet, Modal, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, borderRadius, typography, shadows } from '../../theme';
import { SOSCameraModal } from '../../components/SOSCameraModal';
import type { SosController } from './useSOS';

/**
 * The tab bar's height, from `navigation/MainNavigator.tsx`.
 *
 * Needed because the pill is rendered at the **app root** — `GuardianProvider`
 * sits outside the navigator — so its `bottom: 0` is the true bottom of the
 * screen, below the tab bar, not the bottom of the screen the user is looking
 * at. Duplicated rather than threaded through a context for one number; if the
 * tab bar changes height the pill rides over it, which is visible immediately.
 */
const TAB_BAR_HEIGHT = 54;

/**
 * One fact about the send.
 *
 * `value` is a string, not a number, because "Not recorded" belongs in the same
 * column as "2" — the row is "what happened to the video", and the answer is
 * sometimes a count and sometimes a state.
 */
const Fact: React.FC<{
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  muted?: boolean;
}> = ({ icon, label, value, muted }) => (
  <View style={styles.fact}>
    <Ionicons
      name={icon}
      size={18}
      color={muted ? colors.textMuted : colors.textSecondary}
      style={styles.factIcon}
    />
    <Text style={styles.factLabel}>{label}</Text>
    <Text style={[styles.factValue, muted && styles.factValueMuted]}>{value}</Text>
  </View>
);

export const SOSFlow: React.FC<{ sos: SosController }> = ({ sos }) => {
  const result = sos.result;
  const ok = result?.ok === true;
  const insets = useSafeAreaInsets();
  const busyLabel = sos.stage === 'sending' ? 'Alerting contacts' : 'Uploading evidence';

  return (
    <>
      <SOSCameraModal
        visible={sos.cameraVisible}
        onClose={sos.cancel}
        onVideoRecorded={sos.onVideoRecorded}
        onError={sos.onCameraError}
      />

      {/*
        Dismissable, not cancellable. Sending an SOS can take a while on a weak
        connection -- the server is talking to an SMTP relay -- and a full-screen
        modal through all of it means the person cannot look at the map, their
        contacts, or anything else, at the one moment they most need to. Hiding
        it leaves the upload exactly where it was and moves it to the pill below.
      */}
      <Modal transparent visible={sos.sending && !sos.minimized} onRequestClose={sos.minimize}>
        <View style={styles.overlay}>
          <View style={styles.card}>
            <ActivityIndicator size="large" color={colors.danger} />
            <Text style={styles.title}>
              {sos.stage === 'sending' ? 'Alerting your contacts...' : 'Uploading Evidence...'}
            </Text>

            <View style={styles.barTrack}>
              <View style={[styles.barFill, { width: `${sos.progress}%` }]} />
            </View>
            <Text style={styles.percent}>{sos.progress}% Completed</Text>

            <Text style={styles.subtitle}>
              {sos.stage === 'sending'
                ? 'Evidence uploaded. Sending the alert — do not close the app.'
                : 'Please do not close the app'}
            </Text>

            <TouchableOpacity
              style={styles.hide}
              onPress={sos.minimize}
              accessibilityRole="button"
              accessibilityLabel="Hide this and keep using the app. Sending continues."
            >
              <Ionicons name="chevron-down" size={16} color={colors.textSecondary} />
              <Text style={styles.hideText}>Keep using the app</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/*
        The send, in a corner. Bottom left on purpose: the SOS button is bottom
        right on every screen that has one, and covering that button during a
        send is the one thing this element must never do.

        Not inside a `Modal`. It is rendered from the app root already, so it
        floats over whatever screen is showing and survives a tab change --
        while a transparent full-screen Modal would swallow touches on Android,
        which is exactly what this change exists to stop.
      */}
      {sos.sending && sos.minimized && (
        <TouchableOpacity
          style={[styles.pill, { bottom: insets.bottom + TAB_BAR_HEIGHT + spacing.sm }]}
          onPress={sos.expand}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel={`${busyLabel}, ${sos.progress} percent. Tap for details.`}
        >
          <ActivityIndicator size="small" color={colors.danger} />
          <View style={styles.pillBody}>
            <Text style={styles.pillLabel} numberOfLines={1}>
              {busyLabel}
            </Text>
            <View style={styles.pillTrack}>
              <View style={[styles.pillFill, { width: `${sos.progress}%` }]} />
            </View>
          </View>
          <Text style={styles.pillPercent}>{sos.progress}%</Text>
        </TouchableOpacity>
      )}

      {/*
        The outcome. This replaced an `Alert.alert`, which put the single most
        important moment in the product behind a grey system dialog that could
        not show the counts as anything but a sentence with a newline in it.
      */}
      <Modal
        transparent
        animationType="fade"
        visible={result !== null}
        onRequestClose={sos.dismissResult}
      >
        <View style={styles.overlay}>
          <View style={styles.resultCard}>
            <View style={[styles.badge, ok ? styles.badgeOk : styles.badgeFail]}>
              <Ionicons
                name={ok ? 'checkmark-circle' : 'alert-circle'}
                size={44}
                color={ok ? colors.success : colors.danger}
              />
            </View>

            <Text style={styles.resultTitle}>{ok ? 'Help is on the way' : 'Alert not sent'}</Text>

            {ok && result ? (
              <>
                <Text style={styles.resultLead}>
                  {result.contactsNotified > 0
                    ? 'Your location has gone out to your emergency contacts.'
                    : 'Your location was recorded, but nobody was reachable.'}
                </Text>

                <View style={styles.facts}>
                  <Fact
                    icon="people"
                    label="Contacts notified"
                    value={String(result.contactsNotified)}
                    muted={result.contactsNotified === 0}
                  />
                  <Fact
                    icon="shield-checkmark"
                    label="Police stations nearby"
                    value={String(result.policeStationsFound)}
                    muted={result.policeStationsFound === 0}
                  />
                  <Fact
                    icon="videocam"
                    label="Video"
                    value={result.videoAttached ? 'Attached' : 'Not recorded'}
                    muted={!result.videoAttached}
                  />
                </View>

                {/*
                  Said plainly rather than hidden. Zero contacts means the alert
                  reached nobody, which the person needs to know now — not the
                  next time they need it.
                */}
                {result.contactsNotified === 0 && (
                  <Text style={styles.resultNote}>
                    Add an emergency contact in your profile so the next alert reaches someone.
                  </Text>
                )}
              </>
            ) : (
              <Text style={styles.resultLead}>{result?.message}</Text>
            )}

            <TouchableOpacity
              style={[styles.button, ok ? styles.buttonOk : styles.buttonFail]}
              onPress={sos.dismissResult}
              accessibilityRole="button"
            >
              <Text style={styles.buttonText}>{ok ? 'Done' : 'Close'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.white,
    padding: spacing.xl,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    ...shadows.lg,
  },
  title: {
    ...typography.h4,
    color: colors.text,
    marginTop: spacing.md,
    fontWeight: 'bold',
  },
  subtitle: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  barTrack: {
    width: 200,
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 4,
  },
  percent: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  hide: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.full,
    backgroundColor: colors.gray100,
  },
  hideText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    fontWeight: '600',
    marginLeft: spacing.xs,
  },

  // ------------------------------------------------------------- the pill --
  pill: {
    position: 'absolute',
    left: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.white,
    borderRadius: borderRadius.full,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadows.lg,
  },
  // A fixed width, not content-sized: "Uploading evidence" and "Alerting
  // contacts" are different lengths, and a pill that resized itself mid-send
  // would twitch at the stage change.
  pillBody: {
    width: 128,
    marginHorizontal: spacing.sm,
  },
  pillLabel: {
    ...typography.caption,
    color: colors.text,
    fontWeight: '600',
  },
  pillTrack: {
    height: 3,
    marginTop: 4,
    borderRadius: 2,
    backgroundColor: colors.gray200,
    overflow: 'hidden',
  },
  pillFill: {
    height: '100%',
    backgroundColor: colors.danger,
    borderRadius: 2,
  },
  pillPercent: {
    ...typography.caption,
    color: colors.textSecondary,
    fontWeight: '600',
    // Room for "100%" so the pill does not shrink as the number grows.
    minWidth: 34,
    textAlign: 'right',
  },

  // ----------------------------------------------------------- the outcome --
  resultCard: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    alignItems: 'center',
    ...shadows.xl,
  },
  // A tinted disc rather than a bare glyph: it gives the icon a size of its own
  // so the sheet reads as one object at a glance, which matters when the person
  // looking at it is not calm.
  badge: {
    width: 72,
    height: 72,
    borderRadius: borderRadius.full,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  badgeOk: {
    backgroundColor: 'rgba(16, 185, 129, 0.12)',
  },
  badgeFail: {
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
  },
  resultTitle: {
    ...typography.h4,
    color: colors.text,
    textAlign: 'center',
  },
  resultLead: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.xs,
  },
  facts: {
    alignSelf: 'stretch',
    marginTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  fact: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm + 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  factIcon: {
    marginRight: spacing.sm,
  },
  // `flex: 1` on the label, so the value stays pinned to the right edge however
  // long the label is — a column, not three words that drift.
  factLabel: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    flex: 1,
  },
  factValue: {
    ...typography.bodySmall,
    color: colors.text,
    fontWeight: '600',
  },
  factValueMuted: {
    color: colors.textMuted,
    fontWeight: '400',
  },
  resultNote: {
    ...typography.caption,
    color: colors.warning,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  button: {
    alignSelf: 'stretch',
    marginTop: spacing.md,
    paddingVertical: spacing.md - 2,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  buttonOk: {
    backgroundColor: colors.success,
  },
  buttonFail: {
    backgroundColor: colors.danger,
  },
  buttonText: {
    ...typography.body,
    color: colors.white,
    fontWeight: '600',
  },
});
