/**
 * The General Diary review screen. D08, ADR 0007.
 *
 * Generate, read, edit, approve, print or copy. The order matters and so does
 * what is missing: there is no "submit to police" button, because Bangladesh
 * Police has no API and a cognizable offence cannot be closed online anyway.
 * The user takes it to the thana, or pastes it into the police's own app.
 *
 * **The approve gate is real, not decorative.** The button is disabled until the
 * user has scrolled the draft, and that is the courtesy; the rule is that
 * approving sends back the sha256 of the exact narrative the server issued, and
 * the server rejects anything else. Approving text you were never shown, or text
 * that has since changed, fails server-side with this screen's cooperation or
 * without it.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  NativeScrollEvent,
  NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import * as Print from 'expo-print';
import * as Clipboard from 'expo-clipboard';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import caseworkService, {
  Channel,
  channelsFor,
  GdDraft,
  GdProfile,
} from '../../services/casework.service';
import { crimeService } from '../../services/crime.service';
import { buildGdHtml, narrativeForOnlineGd } from '../../features/casework/gdDocument';

interface Props {
  navigation: any;
  route: { params: { reportId: string } };
}

/** The form's own words for each field, so the warning names what to go and type. */
const FIELD_LABEL: Record<string, string> = {
  full_name: 'নাম — your name as you will sign it',
  phone: 'মোবাইল — mobile number',
  gd_nid: 'জাতীয় পরিচয় পত্র নং — NID number',
  gd_father_name: 'পিতার নাম — father’s name',
  gd_mother_name: 'মাতার নাম — mother’s name',
  gd_permanent_address: 'ঠিকানা (স্থায়ী) — permanent address',
  gd_present_address: 'ঠিকানা (বর্তমান) — present address',
};

const GdDraftScreen: React.FC<Props> = ({ navigation, route }) => {
  const insets = useSafeAreaInsets();
  const { reportId } = route.params;

  const [draft, setDraft] = useState<GdDraft | null>(null);
  const [profile, setProfile] = useState<GdProfile | null>(null);
  const [report, setReport] = useState<any>(null);
  const [thanas, setThanas] = useState<string[]>([]);

  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [narrative, setNarrative] = useState('');
  const [readToEnd, setReadToEnd] = useState(false);
  const [pickingThana, setPickingThana] = useState(false);
  const [thanaQuery, setThanaQuery] = useState('');
  const [gdNumber, setGdNumber] = useState('');

  const approved = draft?.state === 'ready_to_file';
  // Null means the profile call failed, which for this purpose is the same as
  // empty: we cannot fill the form from it either way.
  const profileIncomplete = !profile || !profile.is_complete;

  const load = useCallback(async () => {
    // Settled, not all. These three are independent, and the profile in
    // particular is only needed to *print* — a draft can be generated, read,
    // edited and approved without one. An earlier version used Promise.all, so
    // a user with no profile row got "Could not load" instead of the screen.
    const [draftResult, profileResult, reportResult] = await Promise.allSettled([
      caseworkService.getDraft(reportId),
      caseworkService.getProfile(),
      crimeService.getReportById(reportId),
    ]);

    if (draftResult.status === 'fulfilled') {
      setDraft(draftResult.value);
      if (draftResult.value) {
        setNarrative(draftResult.value.narrative_bn);
        setGdNumber(draftResult.value.gd_number ?? '');
      }
    }
    setProfile(profileResult.status === 'fulfilled' ? profileResult.value : null);
    setReport(reportResult.status === 'fulfilled' ? reportResult.value : null);

    // Only the draft failing is worth interrupting for; the rest degrade.
    if (draftResult.status === 'rejected') {
      Alert.alert(
        'Could not load',
        draftResult.reason?.message ?? 'Something went wrong loading this draft.',
      );
    }
    setLoading(false);
  }, [reportId]);

  useEffect(() => {
    load();
  }, [load]);

  // Coming back from the details screen must show the result. `load` runs once
  // on mount, so without this the warning stayed up after the user had just
  // filled everything in.
  useEffect(
    () =>
      navigation.addListener('focus', () => {
        caseworkService
          .getProfile()
          .then(setProfile)
          .catch(() => undefined);
      }),
    [navigation],
  );

  const generate = async () => {
    setWorking('Writing your General Diary…');
    try {
      const fresh = await caseworkService.generateDraft(reportId);
      setDraft(fresh);
      setNarrative(fresh.narrative_bn);
      setReadToEnd(false);
    } catch (error: any) {
      Alert.alert('Could not write it', error.message);
    } finally {
      setWorking(null);
    }
  };

  const saveEdit = async () => {
    if (!draft) return;
    setWorking('Saving…');
    try {
      const updated = await caseworkService.editDraft(draft.id, {
        narrative_bn: narrative,
      });
      setDraft(updated);
      setEditing(false);
      // The text changed, so its hash changed. Whatever was read before is not
      // what would be approved now.
      setReadToEnd(false);
    } catch (error: any) {
      Alert.alert('Could not save', error.message);
    } finally {
      setWorking(null);
    }
  };

  const chooseThana = async (name: string) => {
    if (!draft) return;
    setPickingThana(false);
    setWorking('Saving…');
    try {
      const updated = await caseworkService.editDraft(draft.id, { thana_name: name });
      setDraft(updated);
    } catch (error: any) {
      Alert.alert('Could not save', error.message);
    } finally {
      setWorking(null);
    }
  };

  const approve = async () => {
    if (!draft) return;
    setWorking('Approving…');
    try {
      const updated = await caseworkService.approve(draft.id, draft.narrative_sha256);
      setDraft(updated);
    } catch (error: any) {
      Alert.alert('Not approved', error.message);
      await load();
    } finally {
      setWorking(null);
    }
  };

  const print = async () => {
    if (!draft) return;
    if (!profile || !profile.is_complete) {
      Alert.alert(
        'Your GD details are missing',
        'The form needs your name, mobile, NID, parents’ names and both addresses before it can be printed.',
        [
          { text: 'Not now', style: 'cancel' },
          { text: 'Add them', onPress: () => navigation.navigate('GdProfile') },
        ],
      );
      return;
    }
    try {
      await Print.printAsync({ html: buildGdHtml({ draft, profile }) });
    } catch (error: any) {
      Alert.alert('Could not print', error?.message ?? 'Printing is unavailable.');
    }
  };

  const copyNarrative = async () => {
    if (!draft) return;
    await Clipboard.setStringAsync(narrativeForOnlineGd(draft));
    Alert.alert(
      'Copied',
      'In the Online GD app choose অন্যান্য আবেদন, then সাধারন ডায়রী করার আবেদন, and paste this into বিবরণ.',
    );
  };

  const saveGdNumber = async () => {
    if (!draft || !gdNumber.trim()) return;
    setWorking('Saving…');
    try {
      const updated = await caseworkService.recordGdNumber(draft.id, gdNumber.trim());
      setDraft(updated);
    } catch (error: any) {
      Alert.alert('Could not save', error.message);
    } finally {
      setWorking(null);
    }
  };

  const onScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
    if (layoutMeasurement.height + contentOffset.y >= contentSize.height - 48) {
      setReadToEnd(true);
    }
  };

  const channels: Channel[] = useMemo(
    () => channelsFor(report?.category ?? 'other'),
    [report?.category],
  );

  const filteredThanas = useMemo(() => {
    const query = thanaQuery.trim().toLowerCase();
    const list = query
      ? thanas.filter(name => name.toLowerCase().includes(query))
      : thanas;
    return list.slice(0, 40);
  }, [thanas, thanaQuery]);

  const openThanaPicker = async () => {
    if (!thanas.length) setThanas(await caseworkService.listThanas());
    setPickingThana(true);
  };

  if (loading) {
    return (
      <View style={styles.centre}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.iconButton}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>General Diary</Text>
        <TouchableOpacity onPress={() => navigation.navigate('GdProfile')} style={styles.iconButton}>
          <Ionicons name="person-circle-outline" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing.xl }]}
        onScroll={onScroll}
        scrollEventThrottle={64}
        keyboardShouldPersistTaps="handled"
      >
        {/* The official form has an identity block above the narrative, and we
            store none of it. Saying so here — before anything is generated —
            rather than at the print button, where it arrives as a refusal. */}
        {profileIncomplete && (
          <View style={[styles.card, styles.cardWarn]}>
            <View style={styles.warnHead}>
              <Ionicons name="alert-circle-outline" size={20} color={colors.warning} />
              <Text style={styles.warnTitle}>Your GD details are missing</Text>
            </View>
            <Text style={styles.cardHint}>
              The General Diary form asks for these above your statement. You
              type them once and every GD you make uses them. You can still
              read and approve the draft without them — but it cannot be
              printed.
            </Text>
            {(profile?.missing_fields ?? Object.keys(FIELD_LABEL)).map(field => (
              <Text key={field} style={styles.missingItem}>
                •  {FIELD_LABEL[field] ?? field}
              </Text>
            ))}
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => navigation.navigate('GdProfile')}
            >
              <Ionicons name="person-add-outline" size={18} color={colors.white} />
              <Text style={styles.primaryButtonText}>Add your details</Text>
            </TouchableOpacity>
          </View>
        )}

        {!draft ? (
          <View style={styles.emptyCard}>
            <MaterialCommunityIcons
              name="file-document-edit-outline"
              size={44}
              color={colors.primary}
            />
            <Text style={styles.emptyTitle}>Write the General Diary</Text>
            <Text style={styles.emptyBody}>
              Your report becomes a formal Bangla GD application addressed to the
              right thana. You read it, change anything you want, and approve it.
              {'\n\n'}
              Meridian does not file it. You print it and take it to the thana, or
              paste it into the police’s own Online GD app.
            </Text>
            <TouchableOpacity style={styles.primaryButton} onPress={generate}>
              <Text style={styles.primaryButtonText}>Generate GD</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Thana */}
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Addressed to the officer-in-charge of</Text>
              <View style={styles.thanaRow}>
                <Text style={styles.thanaName}>
                  {draft.thana_name || 'No station chosen yet'}
                </Text>
                {!approved && (
                  <TouchableOpacity onPress={openThanaPicker}>
                    <Text style={styles.link}>Change</Text>
                  </TouchableOpacity>
                )}
              </View>
              <Text style={styles.cardHint}>
                Nearest station to where it happened. Check it — thana boundaries
                are not circles, and the duty officer will send you away if it is
                the wrong one.
              </Text>
            </View>

            {pickingThana && (
              <View style={styles.card}>
                <TextInput
                  style={styles.input}
                  value={thanaQuery}
                  onChangeText={setThanaQuery}
                  placeholder="Search police stations"
                  placeholderTextColor={colors.textMuted}
                  autoFocus
                />
                {filteredThanas.map(name => (
                  <TouchableOpacity
                    key={name}
                    style={styles.thanaOption}
                    onPress={() => chooseThana(name)}
                  >
                    <Text style={styles.thanaOptionText}>{name}</Text>
                  </TouchableOpacity>
                ))}
                <TouchableOpacity onPress={() => setPickingThana(false)}>
                  <Text style={[styles.link, { marginTop: spacing.sm }]}>Cancel</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* The narrative */}
            <View style={styles.card}>
              <View style={styles.thanaRow}>
                <Text style={styles.cardLabel}>আপনার বিবরণ</Text>
                {!approved && !editing && (
                  <TouchableOpacity onPress={() => setEditing(true)}>
                    <Text style={styles.link}>Edit</Text>
                  </TouchableOpacity>
                )}
              </View>

              {editing ? (
                <>
                  <TextInput
                    style={styles.narrativeInput}
                    value={narrative}
                    onChangeText={setNarrative}
                    multiline
                    textAlignVertical="top"
                  />
                  <View style={styles.editActions}>
                    <TouchableOpacity
                      onPress={() => {
                        setNarrative(draft.narrative_bn);
                        setEditing(false);
                      }}
                    >
                      <Text style={styles.link}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={saveEdit}>
                      <Text style={[styles.link, styles.linkStrong]}>Save</Text>
                    </TouchableOpacity>
                  </View>
                </>
              ) : (
                <Text style={styles.narrative}>{draft.narrative_bn}</Text>
              )}

              <Text style={styles.summary}>{draft.summary_en}</Text>
            </View>

            {/* What the officer will ask for */}
            {draft.missing_details.length > 0 && !approved && (
              <View style={[styles.card, styles.cardWarn]}>
                <Text style={styles.cardLabel}>The duty officer will ask you for</Text>
                {draft.missing_details.map(item => (
                  <Text key={item} style={styles.missingItem}>
                    •  {item}
                  </Text>
                ))}
                <Text style={styles.cardHint}>
                  Add anything you actually know by tapping Edit. Leave the rest —
                  you cannot invent a detail on a police document.
                </Text>
              </View>
            )}

            {/* The gate */}
            {!approved ? (
              <View style={styles.card}>
                <Text style={styles.cardLabel}>Before you can print or copy</Text>
                <Text style={styles.cardHint}>
                  You are the one signing this. Read it to the end, then approve it.
                </Text>
                <TouchableOpacity
                  style={[styles.primaryButton, !readToEnd && styles.buttonDisabled]}
                  onPress={approve}
                  disabled={!readToEnd || editing}
                >
                  <Text style={styles.primaryButtonText}>
                    {readToEnd ? 'I have read this — approve' : 'Scroll to the end to approve'}
                  </Text>
                </TouchableOpacity>
                {editing && (
                  <Text style={styles.blockedReason}>Save your edit first.</Text>
                )}
              </View>
            ) : (
              <View style={[styles.card, styles.cardOk]}>
                <View style={styles.thanaRow}>
                  <Ionicons name="checkmark-circle" size={20} color={colors.success} />
                  <Text style={styles.approvedText}>Approved — ready to file</Text>
                </View>

                <TouchableOpacity style={styles.primaryButton} onPress={print}>
                  <Ionicons name="print-outline" size={18} color={colors.white} />
                  <Text style={styles.primaryButtonText}>Print the form</Text>
                </TouchableOpacity>
                <Text style={styles.cardHint}>
                  Print two copies, sign both, and hand them to the duty officer.
                  He keeps one and signs the other back to you with the GD number.
                </Text>

                <TouchableOpacity style={styles.secondaryButton} onPress={copyNarrative}>
                  <Ionicons name="copy-outline" size={18} color={colors.primary} />
                  <Text style={styles.secondaryButtonText}>Copy for the Online GD app</Text>
                </TouchableOpacity>
                <Text style={styles.cardHint}>
                  অন্যান্য আবেদন → সাধারন ডায়রী করার আবেদন → paste into বিবরণ.
                  You sign in there with your own NID and OTP.
                </Text>
              </View>
            )}

            {/* Closing the loop */}
            {approved && (
              <View style={styles.card}>
                <Text style={styles.cardLabel}>Got a GD number?</Text>
                <Text style={styles.cardHint}>
                  Whatever the thana wrote on your copy. We did not file it, so
                  this is the only record we have that it happened.
                </Text>
                <View style={styles.gdNumberRow}>
                  <TextInput
                    style={[styles.input, styles.gdNumberInput]}
                    value={gdNumber}
                    onChangeText={setGdNumber}
                    placeholder="GD no."
                    placeholderTextColor={colors.textMuted}
                  />
                  <TouchableOpacity style={styles.saveSmall} onPress={saveGdNumber}>
                    <Text style={styles.saveSmallText}>Save</Text>
                  </TouchableOpacity>
                </View>
                {draft.gd_number ? (
                  <Text style={styles.recorded}>Recorded: {draft.gd_number}</Text>
                ) : null}
              </View>
            )}

            {/* Where else */}
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Where else you can take this</Text>
              {channels.map(channel => (
                <TouchableOpacity
                  key={channel.number}
                  style={styles.channel}
                  onPress={() => Linking.openURL(`tel:${channel.number.replace(/[^0-9+]/g, '')}`)}
                >
                  <Ionicons name="call-outline" size={18} color={colors.primary} />
                  <View style={styles.channelText}>
                    <Text style={styles.channelLabel}>
                      {channel.label} · {channel.number}
                    </Text>
                    <Text style={styles.channelReason}>{channel.reason}</Text>
                  </View>
                </TouchableOpacity>
              ))}
            </View>

            {!approved && (
              <TouchableOpacity style={styles.regenerate} onPress={generate}>
                <Text style={styles.link}>Write it again from my report</Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </ScrollView>

      {working && (
        <View style={styles.overlay}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.overlayText}>{working}</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centre: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  iconButton: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: colors.text, fontSize: fontSize.lg, fontWeight: '700' },
  body: { paddingHorizontal: spacing.md },

  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: fontSize.xl,
    fontWeight: '700',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  emptyBody: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
    lineHeight: 21,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },

  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  cardWarn: { borderColor: colors.warning },
  warnHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  warnTitle: { color: colors.warning, fontSize: fontSize.md, fontWeight: '700' },
  cardOk: { borderColor: colors.success },
  cardLabel: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.xs,
  },
  cardHint: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    lineHeight: 18,
    marginTop: spacing.sm,
  },

  thanaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  thanaName: { color: colors.text, fontSize: fontSize.md, fontWeight: '600', flex: 1 },
  link: { color: colors.primary, fontSize: fontSize.sm, fontWeight: '600' },
  linkStrong: { fontWeight: '700' },
  thanaOption: {
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  thanaOptionText: { color: colors.text, fontSize: fontSize.sm },

  narrative: {
    color: colors.text,
    fontSize: fontSize.md,
    lineHeight: 30,
    marginTop: spacing.sm,
  },
  narrativeInput: {
    color: colors.text,
    fontSize: fontSize.md,
    lineHeight: 28,
    marginTop: spacing.sm,
    minHeight: 200,
    backgroundColor: colors.glassDark,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
  },
  editActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.lg,
    marginTop: spacing.sm,
  },
  summary: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    fontStyle: 'italic',
    lineHeight: 18,
    marginTop: spacing.md,
  },
  missingItem: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
    lineHeight: 22,
  },

  primaryButton: {
    flexDirection: 'row',
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    // The empty card centres its children, which makes anything inside it
    // shrink-wrap to its text. Without this the label sits against the button's
    // own edges.
    alignSelf: 'stretch',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  primaryButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '700',
    textAlign: 'center',
  },
  buttonDisabled: { backgroundColor: colors.surfaceHover },
  blockedReason: {
    color: colors.warning,
    fontSize: fontSize.xs,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  secondaryButton: {
    flexDirection: 'row',
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'stretch',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  secondaryButtonText: { color: colors.primary, fontSize: fontSize.md, fontWeight: '700' },
  approvedText: {
    color: colors.success,
    fontSize: fontSize.md,
    fontWeight: '700',
    marginLeft: spacing.sm,
    flex: 1,
  },

  input: {
    backgroundColor: colors.glassDark,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    color: colors.text,
    fontSize: fontSize.md,
  },
  gdNumberRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  gdNumberInput: { flex: 1 },
  saveSmall: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    justifyContent: 'center',
  },
  saveSmallText: { color: colors.white, fontWeight: '700' },
  recorded: { color: colors.success, fontSize: fontSize.sm, marginTop: spacing.sm },

  channel: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  channelText: { marginLeft: spacing.sm, flex: 1 },
  channelLabel: { color: colors.text, fontSize: fontSize.sm, fontWeight: '600' },
  channelReason: { color: colors.textMuted, fontSize: fontSize.xs, marginTop: 1 },

  regenerate: { alignItems: 'center', paddingVertical: spacing.md },

  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.78)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  overlayText: { color: colors.text, marginTop: spacing.md, fontSize: fontSize.sm },
});

export default GdDraftScreen;
