/**
 * The modals an SOS puts on screen: the camera, the progress overlay, then the
 * outcome.
 *
 * Separate from `useSOS` so that a screen adds SOS with one element rather than
 * forty lines of copied JSX — which is how `MapScreen` ended up with a red button
 * and no implementation behind it (defect 14).
 *
 * Both dialogs are `Sheet`s, so they are made of the same material as the rest
 * of the app. They used to be bare `<View backgroundColor: t.surface>` cards,
 * which is why opening one dropped the user out of the new UI and into a grey
 * box — see the note at the top of `Sheet.tsx`.
 */
import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { fontFamily, radius, space, type } from '../../theme/type';
import { Sheet } from '../../components/motion';
import { TAB_BAR_HEIGHT } from '../../navigation/metrics';
import { SOSCameraModal } from '../../components/SOSCameraModal';
import type { SosController } from './useSOS';

/**
 * One fact about the send.
 *
 * `value` is a string, not a number, because "Not recorded" belongs in the same
 * column as "2" — the row is "what happened to the video", and the answer is
 * sometimes a count and sometimes a state.
 *
 * It takes the palette from the hook rather than from a prop: `useStyles` exists
 * so that a file's sub-components can each reach the theme without `styles`
 * being threaded down through them.
 */
const Fact: React.FC<{
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  muted?: boolean;
}> = ({ icon, label, value, muted }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);

  return (
    <View style={styles.fact}>
      <Ionicons
        name={icon}
        size={18}
        color={muted ? t.textFaint : t.textSoft}
        style={styles.factIcon}
      />
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={[styles.factValue, muted && styles.factValueMuted]}>{value}</Text>
    </View>
  );
};

export const SOSFlow: React.FC<{ sos: SosController }> = ({ sos }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();
  const result = sos.result;
  const ok = result?.ok === true;
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

        `onClose` is `minimize`, so Android's back button puts it in the corner
        rather than doing nothing. The scrim is not tappable: a stray touch
        should not hide a send in progress.
      */}
      <Sheet
        visible={sos.sending && !sos.minimized}
        onClose={sos.minimize}
        padding={space.xl}
        contentStyle={styles.centred}
        style={styles.busyPane}
      >
        <ActivityIndicator size="large" color={t.danger} />
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
          <Ionicons name="chevron-down" size={16} color={t.textSoft} />
          <Text style={styles.hideText}>Keep using the app</Text>
        </TouchableOpacity>
      </Sheet>

      {/*
        The send, in a corner. Bottom left on purpose: the SOS button is bottom
        right on every screen that has one, and covering that button during a
        send is the one thing this element must never do.

        Not inside a `Modal`. It is rendered from the app root already, so it
        floats over whatever screen is showing and survives a tab change --
        while a transparent full-screen Modal would swallow touches on Android,
        which is exactly what this change exists to stop.

        `Math.max(insets.bottom, 10)` is the floating tab bar's own offset,
        repeated here because the pill lives at the app root and so sits beneath
        the bar unless it is lifted past it. The two have to agree, and the bar
        is the floor.
      */}
      {sos.sending && sos.minimized && (
        <TouchableOpacity
          style={[styles.pill, { bottom: Math.max(insets.bottom, 10) + TAB_BAR_HEIGHT + space.sm }]}
          onPress={sos.expand}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel={`${busyLabel}, ${sos.progress} percent. Tap for details.`}
        >
          <ActivityIndicator size="small" color={t.danger} />
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
      <Sheet visible={result !== null} onClose={sos.dismissResult} contentStyle={styles.centred}>
        <View style={[styles.badge, { backgroundColor: ok ? t.okSoft : t.dangerSoft }]}>
          <Ionicons
            name={ok ? 'checkmark-circle' : 'alert-circle'}
            size={44}
            color={ok ? t.ok : t.danger}
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
          style={[styles.button, { backgroundColor: ok ? t.ok : t.danger }]}
          onPress={sos.dismissResult}
          accessibilityRole="button"
        >
          <Text style={styles.buttonText}>{ok ? 'Done' : 'Close'}</Text>
        </TouchableOpacity>
      </Sheet>
    </>
  );
};

/**
 * Themed, not module-level.
 *
 * Every colour is a palette token rather than a literal, which is what makes
 * these surfaces follow the mode. Note the absence of `fontWeight` throughout:
 * the weight lives in the family name, because on Android a custom family
 * paired with a weight resolves to a variant that is not bundled and falls back
 * to Roboto. `theme.ui.test.ts` fails the build on that pairing.
 */
const makeStyles = (t: Palette) =>
  StyleSheet.create({
    centred: { alignItems: 'center' },
    // Narrower than a `Sheet` would be by default: a progress card is a line of
    // text and a bar, and at 420 it reads as a mostly-empty box.
    busyPane: { maxWidth: 340 },

    title: {
      ...type.heading,
      color: t.text,
      marginTop: space.md,
      textAlign: 'center',
    },
    subtitle: {
      ...type.small,
      color: t.textSoft,
      textAlign: 'center',
    },
    barTrack: {
      width: 200,
      height: 8,
      backgroundColor: t.fillStrong,
      borderRadius: 4,
      marginTop: space.md,
      marginBottom: space.xs,
      overflow: 'hidden',
    },
    barFill: {
      height: '100%',
      backgroundColor: t.brand,
      borderRadius: 4,
    },
    percent: {
      ...type.caption,
      color: t.textSoft,
      marginBottom: space.sm,
    },
    hide: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      marginTop: space.lg,
      paddingVertical: space.sm,
      paddingHorizontal: space.md,
      borderRadius: radius.pill,
      backgroundColor: t.fillSoft,
    },
    hideText: {
      ...type.label,
      color: t.textSoft,
      marginLeft: space.xs,
    },

    // ------------------------------------------------------------- the pill --
    pill: {
      position: 'absolute',
      left: space.lg,
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: t.surface,
      borderRadius: radius.pill,
      paddingVertical: space.sm,
      paddingHorizontal: space.md,
      borderWidth: StyleSheet.hairlineWidth * 2,
      borderColor: t.line,
      // `boxShadow`, not `elevation`: see the note in `Glass.tsx`.
      boxShadow: [{ offsetX: 0, offsetY: 6, blurRadius: 16, color: t.shadow }],
    },
    // A fixed width, not content-sized: "Uploading evidence" and "Alerting
    // contacts" are different lengths, and a pill that resized itself mid-send
    // would twitch at the stage change.
    pillBody: {
      width: 128,
      marginHorizontal: space.sm,
    },
    pillLabel: {
      ...type.caption,
      fontFamily: fontFamily.bodySemi,
      color: t.text,
    },
    pillTrack: {
      height: 3,
      marginTop: 4,
      borderRadius: 2,
      backgroundColor: t.fillStrong,
      overflow: 'hidden',
    },
    pillFill: {
      height: '100%',
      backgroundColor: t.danger,
      borderRadius: 2,
    },
    pillPercent: {
      ...type.caption,
      fontFamily: fontFamily.bodySemi,
      color: t.textSoft,
      // Room for "100%" so the pill does not shrink as the number grows.
      minWidth: 34,
      textAlign: 'right',
    },

    // ----------------------------------------------------------- the outcome --
    // A tinted disc rather than a bare glyph: it gives the icon a size of its
    // own so the sheet reads as one object at a glance, which matters when the
    // person looking at it is not calm. The tints are the palette's own soft
    // state colours, so the disc stays readable in dark mode instead of glowing.
    badge: {
      width: 72,
      height: 72,
      borderRadius: radius.pill,
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: space.md,
    },
    resultTitle: {
      ...type.title,
      color: t.text,
      textAlign: 'center',
    },
    resultLead: {
      ...type.small,
      color: t.textSoft,
      textAlign: 'center',
      marginTop: space.xs,
    },
    facts: {
      alignSelf: 'stretch',
      marginTop: space.md,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.line,
    },
    fact: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: space.md,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.line,
    },
    factIcon: {
      marginRight: space.sm,
    },
    // `flex: 1` on the label, so the value stays pinned to the right edge
    // however long the label is — a column, not three words that drift.
    factLabel: {
      ...type.small,
      color: t.textSoft,
      flex: 1,
    },
    factValue: {
      ...type.small,
      fontFamily: fontFamily.bodySemi,
      color: t.text,
    },
    factValueMuted: {
      fontFamily: fontFamily.body,
      color: t.textFaint,
    },
    resultNote: {
      ...type.caption,
      color: t.warn,
      textAlign: 'center',
      marginTop: space.sm,
    },
    button: {
      alignSelf: 'stretch',
      marginTop: space.lg,
      paddingVertical: space.md,
      borderRadius: radius.md,
      alignItems: 'center',
    },
    // `onBrand`, not white: in dark mode `ok` and `danger` are light enough that
    // white text on them is unreadable, and `onBrand` is the token that flips.
    buttonText: {
      ...type.bodyStrong,
      color: t.onBrand,
    },
  });
