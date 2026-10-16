/**
 * What is happening to this journey, and who knows about it. JG3.
 *
 * Reached by tapping the journey card on the map. Three things, in order of how
 * urgently somebody wants them:
 *
 * 1. **The state, in a sentence.** "Ammu has been emailed" is the answer to the
 *    question people actually open this screen with.
 * 2. **The answer button**, for as long as a question is outstanding — on every
 *    rung, including the last. This is the second place it exists, after the
 *    card and the lock-screen notification, and the reason is the same one
 *    written in `MapScreen`: a safety question with one way to answer it is one
 *    failed notification away from being unanswerable.
 * 3. **The timeline**, built from the journey row's own timestamps.
 *
 * ## Why there is no map here
 *
 * The position this journey reports is for the guardian's email, not for the
 * traveller's screen — they are standing where it is. Drawing it here would be
 * the app presenting somebody's own location back to them as a safety feature,
 * and it would make the one position JG3 stores look like a tracking log, which
 * is specifically what it is not: one overwritten point, sent only when a
 * guardian exists.
 *
 * ## Why it reads the hook rather than fetching
 *
 * `useJourney` is already the one definition of "the open journey", and it is
 * already refreshed when the app comes back to the foreground. A second fetch
 * here would be a second copy of that state, free to disagree with the card
 * that opened this screen — and it is the disagreement, not the staleness, that
 * would make somebody distrust the page.
 */
import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Aurora } from '../../components/motion';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface } from '../../theme/surfaces';
import { fontFamily, radius, space, type } from '../../theme/type';
import { useJourney } from '../../features/journey/useJourney';
import { isAwaitingAnswer } from '../../features/journey/deadline';
import { startedAtLabel } from '../../features/journey/resume';
import {
  clockTime,
  guardianLine,
  journeyStatus,
  journeyTimeline,
  type Tone,
} from '../../features/journey/escalation';

const JourneyScreen: React.FC = () => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();

  const journey = useJourney();
  const [answerFailed, setAnswerFailed] = useState(false);

  const open = journey.journey;

  const answer = useCallback(() => {
    void (async () => {
      setAnswerFailed(false);
      // False only when the server still says a question is outstanding, so
      // this does not fire for an answer that landed through the notification
      // instead -- the common race, not a rare one. See `useJourney`.
      if (!(await journey.checkIn())) setAnswerFailed(true);
    })();
  }, [journey]);

  const tone = (value: Tone) =>
    value === 'alarm' ? t.danger : value === 'waiting' ? t.warn : t.brand;

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* `glassSurface` is a translucent fill and needs something to be
          translucent over -- see theme/surfaces.ts. */}
      <Aurora intensity="ambient" />

      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={12}>
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>This journey</Text>
        <View style={{ width: 24 }} />
      </View>

      {journey.loading && (
        <View style={styles.centre}>
          <ActivityIndicator color={t.brand} />
        </View>
      )}

      {!journey.loading && !open && (
        <View style={styles.centre}>
          <Text style={styles.empty}>
            No journey is running. Start one from the map and it will show up
            here.
          </Text>
        </View>
      )}

      {open && (
        <ScrollView
          contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + space.xl }]}
        >
          {(() => {
            const status = journeyStatus(open);
            const waiting = isAwaitingAnswer(open);
            const told = guardianLine(open);
            return (
              <>
                <View style={styles.card}>
                  <Text style={[styles.headline, { color: tone(status.tone) }]}>
                    {status.headline}
                  </Text>
                  {status.detail && <Text style={styles.detail}>{status.detail}</Text>}

                  <Text style={styles.where}>
                    {`${Math.round(open.duration_minutes)} min to ${open.destination_label}`}
                  </Text>
                  {/* The deadline as an instant, not a countdown, for the reason
                      the card gives: a duration is a number nothing is
                      maintaining once nobody is looking at it. */}
                  {open.state === 'active' && startedAtLabel(open.deadline_at) !== '' && (
                    <Text style={styles.where}>
                      {`Check in by ${startedAtLabel(open.deadline_at)}`}
                    </Text>
                  )}
                  {told && <Text style={styles.told}>{told}</Text>}
                </View>

                {waiting && (
                  <TouchableOpacity
                    style={styles.answer}
                    onPress={answer}
                    accessibilityRole="button"
                    accessibilityLabel="I'm fine"
                  >
                    <Ionicons name="checkmark-circle" size={18} color={t.onBrand} />
                    <Text style={styles.answerText}>I&apos;m fine</Text>
                  </TouchableOpacity>
                )}

                {/* Inline rather than a dialog. This screen is not going
                    anywhere, the person is reading it, and a modal that has to
                    be dismissed before the retry button is reachable is a modal
                    in the way of the only thing they came here to do. */}
                {answerFailed && (
                  <Text style={styles.failed}>
                    That did not reach the server. The journey is still running —
                    try again in a moment.
                  </Text>
                )}

                <Text style={styles.sectionTitle}>What has happened</Text>
                <View style={styles.card}>
                  {journeyTimeline(open).map((item, index) => (
                    <View key={`${item.at}-${index}`} style={styles.entry}>
                      <View style={[styles.dot, { backgroundColor: tone(item.tone) }]} />
                      <Text style={styles.entryTime}>{clockTime(item.at)}</Text>
                      <Text style={styles.entryLabel}>{item.label}</Text>
                    </View>
                  ))}
                </View>

                {/* The honest footnote. Somebody reading a screen that says
                    "all of your contacts were emailed" may well assume more is
                    already in motion, and it is not: no 999, no thana, no
                    police record -- that is JG7. Saying so here is better than
                    letting the silence imply otherwise. */}
                <Text style={styles.footnote}>
                  Meridian only emails the people you chose. It does not call the
                  police.
                </Text>
              </>
            );
          })()}
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
      paddingHorizontal: space.xl,
      paddingVertical: space.lg,
    },
    headerTitle: { ...type.heading, color: t.text },

    centre: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.xl },
    empty: { ...type.body, color: t.textSoft, textAlign: 'center' },

    body: { paddingHorizontal: space.xl, gap: space.lg },
    card: { ...glassSurface(t), padding: space.lg, gap: space.xs },

    headline: { ...type.heading },
    detail: { ...type.body, color: t.text },
    where: { ...type.caption, color: t.textSoft },
    told: { ...type.caption, color: t.brand, marginTop: space.xs },

    answer: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: space.xs,
      height: 48,
      borderRadius: radius.md,
      backgroundColor: t.brandStrong,
    },
    answerText: { ...type.label, fontFamily: fontFamily.bodySemi, color: t.onBrand },
    failed: { ...type.caption, color: t.danger },

    sectionTitle: { ...type.label, color: t.textSoft },
    entry: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
    dot: { width: 8, height: 8, borderRadius: 4 },
    // Fixed width so the labels line up into a column rather than stepping in
    // and out as the times change width ("9:05 PM" against "11:40 PM").
    entryTime: { ...type.caption, color: t.textSoft, width: 68 },
    entryLabel: { ...type.caption, color: t.text, flex: 1 },

    footnote: { ...type.caption, color: t.textSoft },
  });

export default JourneyScreen;
