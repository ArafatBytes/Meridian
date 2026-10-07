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
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { useAuthStore } from '../../store';
import { SOSHotWord, ProfileStackParamList } from '../../types';
import { speechService } from '../../services';
import { useVoiceRecorder } from '../../hooks/useVoiceRecorder';

type SOSHotWordsScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'SOSHotWords'
>;

interface Props {
  navigation: SOSHotWordsScreenNavigationProp;
}

const SOSHotWordsScreen: React.FC<Props> = ({ navigation }) => {
  const { user } = useAuthStore();
  const insets = useSafeAreaInsets();
  const [hotWords, setHotWords] = useState<SOSHotWord[]>([]);
  const [newHotWord, setNewHotWord] = useState('');
  const [loading, setLoading] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  // Recording lives in the hook: expo-audio only exposes capture via
  // useAudioRecorder, and the hook also owns the 30s cap and unmount cleanup
  // that the old setInterval-on-a-function-property never did reliably.
  const recorder = useVoiceRecorder();
  const isListening = recorder.isRecording;
  const recordingDuration = recorder.durationSeconds;

  useEffect(() => {
    fetchHotWords();

    // No recording cleanup here any more -- useVoiceRecorder stops the
    // recorder and releases the audio session on unmount.
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
    if (!newHotWord.trim()) {
      Alert.alert('Error', 'Please enter a hot word or phrase');
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

  const startVoiceInput = async () => {
    if (isTranscribing) return;

    // Stop -> transcribe
    if (isListening) {
      setIsTranscribing(true);
      try {
        const audioUri = await recorder.stop();
        if (!audioUri) {
          Alert.alert('Nothing Recorded', 'No audio was captured. Please try again.');
          return;
        }

        const result = await speechService.transcribeAudio(audioUri, {
          language: 'en-US',
        });

        if (!result.text) {
          Alert.alert('No Speech Detected', 'Please try again and speak clearly.');
          return;
        }

        setNewHotWord(result.text);
        Alert.alert(
          'Transcription Complete',
          `Detected: "${result.text}"

Confidence: ${Math.round(result.confidence * 100)}%`,
        );
      } catch (error: any) {
        Alert.alert(
          'Transcription Failed',
          error.message || 'Could not convert speech to text. Please try again.',
        );
      } finally {
        setIsTranscribing(false);
      }
      return;
    }

    // Start. The hook requests permission and throws with an actionable
    // message if it is denied.
    try {
      await recorder.start();
    } catch (error: any) {
      Alert.alert('Microphone Unavailable', error.message || 'Could not start recording.');
    }
  };

  const renderHotWord = ({ item }: { item: SOSHotWord }) => (
    <View style={styles.hotWordItem}>
      <View style={styles.hotWordContent}>
        <Ionicons name="alert-circle" size={24} color={colors.error} />
        <Text style={styles.hotWordText}>{item.hot_word}</Text>
      </View>
      <TouchableOpacity
        onPress={() => deleteHotWord(item.id)}
        style={styles.deleteButton}
      >
        <Ionicons name="trash-outline" size={20} color={colors.error} />
      </TouchableOpacity>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      {/* Header with Back Button */}
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>SOS Hot Words</Text>
        <View style={styles.placeholder} />
      </View>

      <View style={styles.inputSection}>
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            placeholder="Enter SOS hot word or phrase..."
            placeholderTextColor={colors.textSecondary}
            value={newHotWord}
            onChangeText={setNewHotWord}
            multiline
            maxLength={200}
          />
        </View>

        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.voiceButton, isListening && styles.listeningButton]}
            onPress={startVoiceInput}
            disabled={isTranscribing}
          >
            {isTranscribing ? (
              <ActivityIndicator size="small" color={colors.white} />
            ) : (
              <Ionicons
                name={isListening ? 'stop' : 'mic'}
                size={24}
                color={isListening ? colors.white : colors.primary}
              />
            )}
            <Text
              style={[
                styles.voiceButtonText,
                isListening && styles.listeningButtonText,
              ]}
            >
              {isTranscribing
                ? 'Processing...'
                : isListening
                  ? `Stop (${recordingDuration}s)`
                  : 'Voice Input'}
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
            <Ionicons name="add" size={24} color={colors.white} />
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
              color={colors.gray400}
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
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
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
  backButton: {
    padding: spacing.sm,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
  },
  placeholder: {
    width: 40,
  },
  inputSection: {
    backgroundColor: colors.white,
    padding: spacing.lg,
    marginTop: spacing.md,
    marginHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    elevation: 2,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  inputContainer: {
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    minHeight: 80,
    marginBottom: spacing.md,
  },
  input: {
    fontSize: fontSize.md,
    color: colors.text,
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
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    gap: spacing.xs,
  },
  voiceButtonText: {
    fontSize: fontSize.md,
    color: colors.primary,
    fontWeight: '600',
  },
  listeningButton: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  listeningButtonText: {
    color: colors.white,
  },
  addButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    gap: spacing.xs,
  },
  addButtonText: {
    fontSize: fontSize.md,
    color: colors.white,
    fontWeight: '600',
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
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  listContent: {
    paddingBottom: spacing.xl,
  },
  hotWordItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.white,
    padding: spacing.lg,
    borderRadius: borderRadius.md,
    marginBottom: spacing.md,
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  hotWordContent: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  hotWordText: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '500',
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
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
    marginTop: spacing.lg,
    textAlign: 'center',
  },
  emptyStateSubtext: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: spacing.sm,
    textAlign: 'center',
    paddingHorizontal: spacing.xl,
  },
});

export default SOSHotWordsScreen;
