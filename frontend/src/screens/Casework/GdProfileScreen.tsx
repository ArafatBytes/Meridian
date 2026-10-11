/**
 * The five fields the official GD form asks for and we have never stored.
 *
 * Typed once, reused for every General Diary. Nothing here is validated against
 * anything — an NID is not checked against the Election Commission, because we
 * have no access and no business checking. The person signs the form; the
 * details are theirs to get right.
 */
import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { spacing, borderRadius, fontSize } from '../../theme';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily } from '../../theme/type';
import caseworkService, { GdProfile } from '../../services/casework.service';

interface Props {
  navigation: any;
}

const FIELDS: Array<{
  key: keyof GdProfile;
  bangla: string;
  english: string;
  placeholder: string;
  multiline?: boolean;
}> = [
  {
    key: 'full_name',
    bangla: 'নাম',
    english: 'Your full name, as you will sign it',
    placeholder: 'আবেদনে ও স্বাক্ষরে যে নাম থাকবে',
  },
  {
    key: 'phone',
    bangla: 'মোবাইল',
    english: 'Mobile number',
    placeholder: '০১XXXXXXXXX',
  },
  {
    key: 'gd_nid',
    bangla: 'জাতীয় পরিচয় পত্র নং',
    english: 'National ID number',
    placeholder: '১০, ১৩ বা ১৭ সংখ্যা',
  },
  {
    key: 'gd_father_name',
    bangla: 'পিতার নাম',
    english: "Father's name",
    placeholder: 'ফরমে যেভাবে লিখবেন',
  },
  {
    key: 'gd_mother_name',
    bangla: 'মাতার নাম',
    english: "Mother's name",
    placeholder: 'ফরমে যেভাবে লিখবেন',
  },
  {
    key: 'gd_permanent_address',
    bangla: 'ঠিকানা (স্থায়ী)',
    english: 'Permanent address',
    placeholder: 'গ্রাম/মহল্লা, ডাকঘর, উপজেলা, জেলা',
    multiline: true,
  },
  {
    key: 'gd_present_address',
    bangla: 'ঠিকানা (বর্তমান)',
    english: 'Present address',
    placeholder: 'বাসা/রোড, এলাকা, থানা, জেলা',
    multiline: true,
  },
];

const GdProfileScreen: React.FC<Props> = ({ navigation }) => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();
  const [profile, setProfile] = useState<Partial<GdProfile>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    caseworkService
      .getProfile()
      .then(setProfile)
      .catch((error: Error) => Alert.alert('Could not load', error.message))
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await caseworkService.saveProfile(profile);
      navigation.goBack();
    } catch (error: any) {
      Alert.alert('Could not save', error.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centre}>
        <ActivityIndicator size="large" color={t.brand} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {/* The ambient field, behind everything. `glassSurface` is a translucent
          fill and needs something to be translucent over — see the note in
          theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
          <Ionicons name="arrow-back" size={24} color={t.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>GD details</Text>
        <View style={styles.back} />
      </View>

      <ScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + spacing.xl }]}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.intro}>
          The official General Diary form asks for these above your statement.
          You type them once and every GD you generate uses them.
        </Text>

        {FIELDS.map(field => (
          <View key={field.key as string} style={styles.field}>
            <Text style={styles.labelBn}>{field.bangla}</Text>
            <Text style={styles.labelEn}>{field.english}</Text>
            <TextInput
              style={[styles.input, field.multiline && styles.inputMultiline]}
              value={(profile[field.key] as string) ?? ''}
              onChangeText={value => setProfile(p => ({ ...p, [field.key]: value }))}
              placeholder={field.placeholder}
              placeholderTextColor={t.textFaint}
              multiline={field.multiline}
              keyboardType={
                field.key === 'gd_nid' || field.key === 'phone'
                  ? 'number-pad'
                  : 'default'
              }
            />
          </View>
        ))}

        <Text style={styles.note}>
          These stay on your account and are only used to fill the form. They are
          never sent to the AI that writes your statement.
        </Text>

        <TouchableOpacity
          style={[styles.save, saving && styles.saveDisabled]}
          onPress={save}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator color={t.onBrand} />
          ) : (
            <Text style={styles.saveText}>Save</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: { flex: 1, backgroundColor: t.bg },
    centre: {
      flex: 1,
      backgroundColor: t.bg,
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
    back: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
    headerTitle: { fontFamily: fontFamily.bodySemi, color: t.text, fontSize: fontSize.lg,},
    body: { paddingHorizontal: spacing.md },
    intro: {
      fontFamily: fontFamily.body,
      color: t.textSoft,
      fontSize: fontSize.sm,
      lineHeight: 20,
      marginBottom: spacing.lg,
    },
    field: { marginBottom: spacing.md },
    labelBn: { fontFamily: fontFamily.bodySemi, color: t.text, fontSize: fontSize.md,},
    labelEn: {
      fontFamily: fontFamily.body,
      color: t.textFaint,
      fontSize: fontSize.xs,
      marginTop: 2,
      marginBottom: spacing.xs,
    },
    input: {
      ...glassSurface(t),
      fontFamily: fontFamily.body,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm + 2,
      color: t.text,
      fontSize: fontSize.md,
    },
    inputMultiline: { minHeight: 76, textAlignVertical: 'top' },
    note: {
      fontFamily: fontFamily.body,
      color: t.textFaint,
      fontSize: fontSize.xs,
      lineHeight: 18,
      marginTop: spacing.sm,
      marginBottom: spacing.lg,
    },
    save: {
      backgroundColor: t.brand,
      borderRadius: borderRadius.md,
      paddingVertical: spacing.md,
      alignItems: 'center',
    },
    saveDisabled: { opacity: 0.6 },
    saveText: { fontFamily: fontFamily.bodySemi, color: t.onBrand, fontSize: fontSize.md,},
  });

export default GdProfileScreen;
