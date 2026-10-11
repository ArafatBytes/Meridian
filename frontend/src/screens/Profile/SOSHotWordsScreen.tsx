/**
 * SOS hot words: storing the phrases, and — as of B8 — actually listening for them.
 *
 * Until this sprint the screen wrote `sos_hot_words` rows that **nothing read**.
 * `migrations/supabase/README.md` recorded it as a known dead loop, and
 * `/voice/analyze` compounded it: it ignored the stored phrases, used a hardcoded
 * list, and returned an empty transcript unconditionally, so `trigger` was always
 * false. The screen looked like a feature and was a form.
 *
 * Two things changed. The phrases are now **read** — by
 * `features/voice/useVoiceGuard`, which listens app-wide and fires a real SOS
 * when one of them is *shouted* — and the microphone button dictates **on the
 * device** instead of uploading a clip to `/ai/speech-to-text`, which removed
 * the last caller of a path that is broken anyway (defect 2, `pydub` commented
 * out).
 *
 * This screen is the phrase list only. Arming, the shout threshold and the live
 * meters are on the **Guardian** screen, because the recogniser session must
 * exist exactly once for the whole app — a second one here would be a second
 * session on the same microphone.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  FlatList,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { spacing, borderRadius, fontSize } from '../../theme';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassBar, glassSurface, lift } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily } from '../../theme/type';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { useAuthStore } from '../../store';
import { SOSHotWord, ProfileStackParamList } from '../../types';
import { hotWordProblem } from '../../features/voice/hotwords';
import { dictateOnce } from '../../features/voice/dictate';

type SOSHotWordsScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'SOSHotWords'
>;

interface Props {
  navigation: SOSHotWordsScreenNavigationProp;
}

const SOSHotWordsScreen: React.FC<Props> = ({ navigation }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const { user } = useAuthStore();
  const insets = useSafeAreaInsets();
  const [hotWords, setHotWords] = useState<SOSHotWord[]>([]);
  const [newHotWord, setNewHotWord] = useState('');
  const [loading, setLoading] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  // The SOS flow, so a hot word can fire the real thing rather than a stub. The
  // same controller the button and the shake gesture use -- there is one SOS
  // path and this is it.

  useEffect(() => {
    fetchHotWords();

    // No recording cleanup here: there is no recording. On-device dictation
    // owns its own session and `useHotWordListener` aborts the recogniser on
    // unmount.
  }, []);

  const fetchHotWords = async () => {
    if (!user?.id) return;

    try {
      const { data, error } = await supabase
        .from('sos_hot_words')
        .select('*')
        .eq('user_id', user.id)
        .order('created_at', { ascending: false });

      if (error) throw error;
      setHotWords(data || []);
    } catch (error: any) {
      console.error('Error fetching hot words:', error);
      Alert.alert('Error', 'Failed to load SOS hot words');
    }
  };

  const addHotWord = async () => {
    // Validated before the insert, with a reason. The old check was
    // `!newHotWord.trim()`, which accepted "sos" -- three characters, which a
    // recogniser mishears off street noise -- and accepted a phrase already
    // shadowed by a shorter one, which can never fire. See `hotWordProblem`.
    const problem = hotWordProblem(newHotWord, hotWords.map(hw => hw.hot_word));
    if (problem) {
      Alert.alert('Cannot use that phrase', problem);
      return;
    }

    if (!user?.id) return;

    setLoading(true);
    try {
      const { data, error } = await supabase
        .from('sos_hot_words')
        .insert([
          {
            user_id: user.id,
            hot_word: newHotWord.trim(),
          },
        ])
        .select()
        .single();

      if (error) throw error;

      setHotWords([data, ...hotWords]);
      setNewHotWord('');
      Alert.alert('Success', 'SOS hot word added successfully');
    } catch (error: any) {
      console.error('Error adding hot word:', error);
      Alert.alert('Error', 'Failed to add SOS hot word');
    } finally {
      setLoading(false);
    }
  };

  const deleteHotWord = async (id: string) => {
    Alert.alert(
      'Delete Hot Word',
      'Are you sure you want to delete this SOS hot word?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const { error } = await supabase
                .from('sos_hot_words')
                .delete()
                .eq('id', id);

              if (error) throw error;

              setHotWords(hotWords.filter(hw => hw.id !== id));
              Alert.alert('Success', 'SOS hot word deleted');
            } catch (error: any) {
              console.error('Error deleting hot word:', error);
              Alert.alert('Error', 'Failed to delete SOS hot word');
            }
          },
        },
      ],
    );
  };

  /**
   * Dictate a phrase, on the device.
   *
   * Replaces a round trip that recorded a clip with `expo-audio`, uploaded it to
   * `/ai/speech-to-text` and waited. Three things wrong with that: it sent audio
   * of the user's voice to a server to fill in a text field, the endpoint behind
   * it is broken (defect 2 -- `pydub` import commented out), and it needed a
   * stop button and a 30-second cap to manage a recording that did not need to
   * exist.
   *
   * `dictateOnce` uses the same on-device recogniser as the hot-word listener and
   * refuses, rather than falling back to the network, when the device cannot do
   * it privately. If it refuses, the text field still works -- typing was always
   * the primary path here.
   */
  const startVoiceInput = async () => {
    if (isTranscribing) return;
    setIsTranscribing(true);
    try {
      const result = await dictateOnce();
      if (!result.transcript) {
        Alert.alert('Nothing heard', 'Please try again and speak clearly.');
        return;
      }
      setNewHotWord(result.transcript);
    } catch (error: any) {
      Alert.alert(
        'Cannot dictate on this phone',
        error?.message ?? 'Type the phrase instead.',
      );
    } finally {
      setIsTranscribing(false);
    }
  };

  const renderHotWord = ({ item }: { item: SOSHotWord }) => (
    <View style={styles.hotWordItem}>
      <View style={styles.hotWordContent}>
        <Ionicons name="alert-circle" size={24} color={t.danger} />
        <Text style={styles.hotWordText}>{item.hot_word}</Text>
      </View>
      <TouchableOpacity
        onPress={() => deleteHotWord(item.id)}
        style={styles.deleteButton}
      >
        <Ionicons name="trash-outline" size={20} color={t.danger} />
      </TouchableOpacity>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      {/* The ambient field, behind everything. `glassSurface` is a translucent
          fill and needs something to be translucent over — see the note in
          theme/surfaces.ts. `<Aurora />` with no children is already absolutely
          positioned and `pointerEvents="box-none"`, so as the first child it
          sits behind the rest without touching the layout. */}
      <Aurora intensity="ambient" />
      {/* Header with Back Button */}
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>SOS Hot Words</Text>
        <View style={styles.placeholder} />
      </View>

      {/* B8. Listening itself is armed on the Guardian screen, not here.
          This screen manages the phrase list; Guardian owns the microphone,
          the shout threshold and the live meters -- and it owns them because
          the recogniser session must exist exactly once for the whole app. A
          second one here would be a second session on the same microphone. */}
      <TouchableOpacity
        style={styles.guardianLink}
        onPress={() => navigation.navigate('Guardian')}
      >
        <Ionicons name="shield-checkmark-outline" size={20} color={t.brand} />
        <View style={styles.guardianLinkBody}>
          <Text style={styles.guardianLinkTitle}>Arm Voice SOS</Text>
          <Text style={styles.guardianLinkSubtitle}>
            Listening, the shout threshold and the live meter are on the Guardian screen.
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={t.textFaint} />
      </TouchableOpacity>

      <View style={styles.inputSection}>
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            placeholder="Enter SOS hot word or phrase..."
            placeholderTextColor={t.textSoft}
            value={newHotWord}
            onChangeText={setNewHotWord}
            multiline
            maxLength={200}
          />
        </View>

        <View style={styles.buttonRow}>
          {/* No stop button and no duration any more. On-device dictation ends
              by itself when you stop speaking, so there is nothing to cap and
              nothing to stop -- the 30-second limit existed to bound a recording
              that was about to be uploaded. */}
          <TouchableOpacity
            style={[styles.voiceButton, isTranscribing && styles.listeningButton]}
            onPress={startVoiceInput}
            disabled={isTranscribing}
          >
            {isTranscribing ? (
              <ActivityIndicator size="small" color={t.onBrand} />
            ) : (
              <Ionicons name="mic" size={24} color={t.brand} />
            )}
            <Text
              style={[
                styles.voiceButtonText,
                isTranscribing && styles.listeningButtonText,
              ]}
            >
              {isTranscribing ? 'Listening…' : 'Dictate'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.addButton,
              (loading || isTranscribing) && styles.disabledButton,
            ]}
            onPress={addHotWord}
            disabled={loading || isTranscribing}
          >
            <Ionicons name="add" size={24} color={t.onBrand} />
            <Text style={styles.addButtonText}>Add Hot Word</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.listSection}>
        <Text style={styles.sectionTitle}>Your SOS Hot Words</Text>
        {hotWords.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons
              name="alert-circle-outline"
              size={64}
              color={t.textFaint}
            />
            <Text style={styles.emptyStateText}>No SOS hot words yet</Text>
            <Text style={styles.emptyStateSubtext}>
              Add words or phrases that will trigger emergency alerts
            </Text>
          </View>
        ) : (
          <FlatList
            data={hotWords}
            renderItem={renderHotWord}
            keyExtractor={item => item.id}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
          />
        )}
      </View>
      {/* Without this the camera and progress modals never render and
          `sos.start()` silently does nothing -- the same wiring HomeScreen and
          MapScreen do. */}
    </KeyboardAvoidingView>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: t.bg,
    },
    guardianLink: {
      ...glassSurface(t),
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
      marginHorizontal: spacing.lg,
      marginTop: spacing.md,
      padding: spacing.lg,
    },
    guardianLinkBody: { flex: 1 },
    guardianLinkTitle: { fontFamily: fontFamily.bodySemi, fontSize: fontSize.md,color: t.text },
    guardianLinkSubtitle: {
      fontFamily: fontFamily.body,
      fontSize: fontSize.xs,
      color: t.textSoft,
      marginTop: 2,
      lineHeight: 16,
    },
    header: {
      ...glassBar(t),
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: spacing.lg,
      paddingBottom: spacing.md,
    },
    backButton: {
      padding: spacing.sm,
    },
    headerTitle: {
      fontFamily: fontFamily.display,
      fontSize: fontSize.xl,
      color: t.text,
    },
    placeholder: {
      width: 40,
    },
    inputSection: {
      ...glassSurface(t),
      padding: spacing.lg,
      marginTop: spacing.md,
      marginHorizontal: spacing.lg,
      ...lift(t, 2),
    },
    inputContainer: {
      backgroundColor: t.bg,
      borderRadius: borderRadius.md,
      borderWidth: 1,
      borderColor: t.line,
      padding: spacing.md,
      minHeight: 80,
      marginBottom: spacing.md,
    },
    input: {
      fontFamily: fontFamily.body,
      fontSize: fontSize.md,
      color: t.text,
      textAlignVertical: 'top',
    },
    buttonRow: {
      flexDirection: 'row',
      gap: spacing.md,
    },
    voiceButton: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.sm,
      backgroundColor: t.bg,
      borderRadius: borderRadius.md,
      borderWidth: 1,
      borderColor: t.brand,
      gap: spacing.xs,
    },
    voiceButtonText: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.md,
      color: t.brand,
    },
    listeningButton: {
      backgroundColor: t.brand,
      borderColor: t.brand,
    },
    listeningButtonText: {
      color: t.onBrand,
    },
    addButton: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.sm,
      backgroundColor: t.brand,
      borderRadius: borderRadius.md,
      gap: spacing.xs,
    },
    addButtonText: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.md,
      color: t.onBrand,
    },
    disabledButton: {
      opacity: 0.5,
    },
    listSection: {
      flex: 1,
      marginTop: spacing.lg,
      paddingHorizontal: spacing.lg,
    },
    sectionTitle: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.lg,
      color: t.text,
      marginBottom: spacing.md,
    },
    listContent: {
      paddingBottom: spacing.xl,
    },
    hotWordItem: {
      ...glassSurface(t),
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: spacing.lg,
      marginBottom: spacing.md,
      ...lift(t, 1),
    },
    hotWordContent: {
      flex: 1,
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
    },
    hotWordText: {
      fontFamily: fontFamily.bodyMedium,
      flex: 1,
      fontSize: fontSize.md,
      color: t.text,
    },
    deleteButton: {
      padding: spacing.sm,
    },
    emptyState: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacing.xxl * 2,
    },
    emptyStateText: {
      fontFamily: fontFamily.display,
      fontSize: fontSize.xl,
      color: t.text,
      marginTop: spacing.lg,
      textAlign: 'center',
    },
    emptyStateSubtext: {
      fontFamily: fontFamily.body,
      fontSize: fontSize.md,
      color: t.textSoft,
      marginTop: spacing.sm,
      textAlign: 'center',
      paddingHorizontal: spacing.xl,
    },
  });

export default SOSHotWordsScreen;
