import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Image,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import Dialog from '../../components/Dialog';
import { useDialog } from '../../components/useDialog';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface, lift } from '../../theme/surfaces';
import { Aurora } from '../../components/motion';
import { fontFamily, radius, space, type } from '../../theme/type';
import { useAuthStore } from '../../store';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { uploadAvatar } from '../../lib/supabase-storage';
import * as ImagePicker from 'expo-image-picker';
import { ProfileStackParamList } from '../../types';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

type EditProfileScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'EditProfile'
>;

interface Props {
  navigation: EditProfileScreenNavigationProp;
}

const EditProfileScreen: React.FC<Props> = ({ navigation }) => {
  const { t, g } = useTheme();
  const styles = useStyles(makeStyles);
  const insets = useSafeAreaInsets();
  const { user, setUser } = useAuthStore();

  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [avatar, setAvatar] = useState(user?.avatar_url || '');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploadingImage, setIsUploadingImage] = useState(false);

  // Password change fields
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswordSection, setShowPasswordSection] = useState(false);

  const dialog = useDialog();

  const pickImage = async () => {
    // Request permission
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      dialog.show({
        title: 'Photo access needed',
        message: 'Meridian needs your photos to set a profile picture.',
        tone: 'warn',
        icon: 'images-outline',
      });
      return;
    }

    // Launch image picker
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],  // MediaTypeOptions is deprecated in SDK 57
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.7,
    });

    if (!result.canceled && result.assets[0]) {
      await uploadImage(result.assets[0].uri);
    }
  };

  const uploadImage = async (uri: string) => {
    try {
      setIsUploadingImage(true);

      const {
        data: { user: authUser },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !authUser) {
        throw new Error('User not authenticated');
      }

      // Delegated to the shared helper instead of building the upload inline.
      //
      // The inline version set contentType to "image/" + fileExt, so a .jpg
      // file produced `image/jpg` -- which is not a valid IANA MIME type (the
      // real one is `image/jpeg`). The bucket's allowed_mime_types correctly
      // lists image/jpeg, so every .jpg upload was rejected with
      // "mime type image/jpg is not supported".
      //
      // uploadAvatar() maps the extension to a real MIME type, enforces the
      // `<uid>/` path that the storage RLS policy requires, and rejects empty
      // or oversized files before they reach the network.
      const publicUrl = await uploadAvatar(authUser.id, uri);

      setAvatar(publicUrl);
    } catch (error: any) {
      dialog.show({
        title: 'Could not upload that picture',
        message: error.message || 'The server did not answer. Try again.',
        tone: 'danger',
        icon: 'cloud-offline',
      });
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleSaveProfile = async () => {
    // Validate name
    if (!name.trim()) {
      dialog.show({
        title: 'Add your name',
        message: 'This is the name your contacts see on an alert.',
        tone: 'warn',
        icon: 'person-outline',
      });
      return;
    }

    // Validate phone number if provided
    if (phone.trim()) {
      const phoneDigits = phone.replace(/\D/g, ''); // Remove non-digits

      if (phoneDigits.length !== 11) {
        dialog.show({
          title: 'That number does not look right',
          message: 'A Bangladeshi mobile number is 11 digits, starting 01.',
          tone: 'warn',
          icon: 'call-outline',
        });
        return;
      }

      if (!phoneDigits.startsWith('01')) {
        dialog.show({
          title: 'That number does not look right',
          message: 'A Bangladeshi mobile number starts with 01.',
          tone: 'warn',
          icon: 'call-outline',
        });
        return;
      }

      // Check if second digit is valid (01[3-9])
      const secondDigit = phoneDigits[1];
      if (
        secondDigit !== '1' &&
        secondDigit !== '3' &&
        secondDigit !== '4' &&
        secondDigit !== '5' &&
        secondDigit !== '6' &&
        secondDigit !== '7' &&
        secondDigit !== '8' &&
        secondDigit !== '9'
      ) {
        dialog.show({
          title: 'That number does not look right',
          message: 'Check it against the format 01XXXXXXXXX.',
          tone: 'warn',
          icon: 'call-outline',
        });
        return;
      }
    }

    try {
      setIsLoading(true);

      // Get current user
      const {
        data: { user: authUser },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !authUser) {
        throw new Error('User not authenticated');
      }

      // Check if profile exists and update/insert accordingly
      const { data: existingProfile } = await supabase
        .from('profiles')
        .select('id')
        .eq('id', authUser.id)
        .single();

      let updateError;

      if (existingProfile) {
        // Profile exists, update it
        const { error } = await supabase
          .from('profiles')
          .update({
            name: name.trim(),
            phone: phone.trim() || null,
            avatar_url: avatar || null,
          })
          .eq('id', authUser.id);
        updateError = error;
      } else {
        // Profile doesn't exist, insert it
        const { error } = await supabase.from('profiles').insert({
          id: authUser.id,
          email: authUser.email || '',
          name: name.trim(),
          phone: phone.trim() || null,
          avatar_url: avatar || null,
        });
        updateError = error;
      }

      if (updateError) {
        throw updateError;
      }

      // Update local state
      if (user) {
        setUser({
          ...user,
          name: name.trim(),
          phone: phone.trim() || null,
          avatar_url: avatar || null,
        });
      }

      dialog.show({
        title: 'Profile saved',
        tone: 'info',
        icon: 'checkmark-circle-outline',
        actions: [{ label: 'Done', primary: true, onPress: () => navigation.goBack() }],
      });
    } catch (error: any) {
      dialog.show({
        title: 'Could not save your profile',
        message: error.message || 'The server did not answer. Nothing was changed.',
        tone: 'danger',
        icon: 'cloud-offline',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      dialog.show({
        title: 'Fill in all three fields',
        message: 'Current password, new password, and the new one again.',
        tone: 'warn',
        icon: 'key-outline',
      });
      return;
    }

    if (currentPassword.length < 6) {
      dialog.show({
        title: 'Enter your current password',
        message: 'This proves the account is yours.',
        tone: 'warn',
        icon: 'key-outline',
      });
      return;
    }

    if (newPassword.length < 8) {
      dialog.show({
        title: 'Too short',
        message: 'A password needs at least 8 characters.',
        tone: 'warn',
        icon: 'key-outline',
      });
      return;
    }

    if (newPassword !== confirmPassword) {
      dialog.show({
        title: 'Those do not match',
        message: 'Type the new password the same way twice.',
        tone: 'warn',
        icon: 'key-outline',
      });
      return;
    }

    if (newPassword === currentPassword) {
      dialog.show({
        title: 'That is your current password',
        message: 'Choose a different one.',
        tone: 'warn',
        icon: 'key-outline',
      });
      return;
    }

    try {
      setIsLoading(true);

      // First verify the current password by attempting to sign in
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user?.email) {
        throw new Error('User email not found');
      }

      // Verify current password by attempting to sign in
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: user.email,
        password: currentPassword,
      });

      if (signInError) {
        dialog.show({
          title: 'That password is not right',
          message: 'Check your current password and try again.',
          tone: 'warn',
          icon: 'key-outline',
        });
        setIsLoading(false);
        return;
      }

      // Current password is correct, now update to new password
      const { error } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (error) {
        throw error;
      }

      dialog.show({
        title: 'Password changed',
        message: 'Use the new one next time you sign in.',
        icon: 'checkmark-circle-outline',
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setShowPasswordSection(false);
    } catch (error: any) {
      dialog.show({
        title: 'Could not change your password',
        message: error.message || 'The server did not answer. Your password is unchanged.',
        tone: 'danger',
        icon: 'cloud-offline',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* The ambient field, behind everything. `glassSurface` is a
          translucent fill and needs something to be translucent over —
          see the note in theme/surfaces.ts. */}
      <Aurora intensity="ambient" />
      {/* Header */}
      <Grad
        colors={g.aurora}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.header, { paddingTop: insets.top + space.lg }]}>
        <TouchableOpacity
          style={styles.headerButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={t.onBrand} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Edit Profile</Text>
        <View style={styles.headerButton} />
      </Grad>

      <ScrollView
        style={styles.content}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + space.xxl },
        ]}
      >
        {/* Avatar Section */}
        <View style={styles.avatarSection}>
          <TouchableOpacity
            style={styles.avatarContainer}
            onPress={pickImage}
            disabled={isUploadingImage}
          >
            {avatar ? (
              <Image source={{ uri: avatar }} style={styles.avatar} />
            ) : (
              <View style={styles.avatarPlaceholder}>
                <Ionicons name="person" size={60} color={t.textFaint} />
              </View>
            )}
            {isUploadingImage ? (
              <View style={styles.avatarOverlay}>
                <ActivityIndicator size="small" color={t.onBrand} />
              </View>
            ) : (
              <View style={styles.avatarEditIcon}>
                <Ionicons name="camera" size={20} color={t.onBrand} />
              </View>
            )}
          </TouchableOpacity>
          <Text style={styles.avatarHint}>Tap to change profile picture</Text>
        </View>

        {/* Profile Information */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Profile Information</Text>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Email</Text>
            <View style={styles.inputDisabled}>
              <Ionicons name="mail-outline" size={20} color={t.textFaint} />
              <Text style={styles.disabledText}>{user?.email}</Text>
            </View>
            <Text style={styles.hint}>Email cannot be changed</Text>
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Name</Text>
            <View style={styles.input}>
              <Ionicons
                name="person-outline"
                size={20}
                color={t.textSoft}
              />
              <TextInput
                style={styles.textInput}
                value={name}
                onChangeText={setName}
                placeholder="Enter your name"
                placeholderTextColor={t.textFaint}
              />
            </View>
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Phone</Text>
            <View style={styles.input}>
              <Ionicons
                name="call-outline"
                size={20}
                color={t.textSoft}
              />
              <TextInput
                style={styles.textInput}
                value={phone}
                onChangeText={setPhone}
                placeholder="Enter your phone number"
                placeholderTextColor={t.textFaint}
                keyboardType="phone-pad"
              />
            </View>
          </View>
        </View>

        {/* Password Section */}
        <View style={styles.section}>
          <TouchableOpacity
            style={styles.sectionHeader}
            onPress={() => setShowPasswordSection(!showPasswordSection)}
          >
            <Text style={styles.sectionTitle}>Change Password</Text>
            <Ionicons
              name={showPasswordSection ? 'chevron-up' : 'chevron-down'}
              size={24}
              color={t.textSoft}
            />
          </TouchableOpacity>

          {showPasswordSection && (
            <>
              <View style={styles.inputContainer}>
                <Text style={styles.label}>Current Password</Text>
                <View style={styles.input}>
                  <Ionicons
                    name="lock-closed-outline"
                    size={20}
                    color={t.textSoft}
                  />
                  <TextInput
                    style={styles.textInput}
                    value={currentPassword}
                    onChangeText={setCurrentPassword}
                    placeholder="Enter current password"
                    placeholderTextColor={t.textFaint}
                    secureTextEntry
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <Text style={styles.label}>New Password</Text>
                <View style={styles.input}>
                  <Ionicons
                    name="lock-closed-outline"
                    size={20}
                    color={t.textSoft}
                  />
                  <TextInput
                    style={styles.textInput}
                    value={newPassword}
                    onChangeText={setNewPassword}
                    placeholder="Enter new password (min 6 characters)"
                    placeholderTextColor={t.textFaint}
                    secureTextEntry
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <Text style={styles.label}>Confirm New Password</Text>
                <View style={styles.input}>
                  <Ionicons
                    name="lock-closed-outline"
                    size={20}
                    color={t.textSoft}
                  />
                  <TextInput
                    style={styles.textInput}
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    placeholder="Confirm new password"
                    placeholderTextColor={t.textFaint}
                    secureTextEntry
                  />
                </View>
              </View>

              <TouchableOpacity
                style={styles.changePasswordButton}
                onPress={handleChangePassword}
                disabled={isLoading}
              >
                {isLoading ? (
                  <ActivityIndicator size="small" color={t.onBrand} />
                ) : (
                  <Text style={styles.changePasswordButtonText}>
                    Change Password
                  </Text>
                )}
              </TouchableOpacity>
            </>
          )}
        </View>

        {/* Save Button */}
        <TouchableOpacity
          style={styles.saveButton}
          onPress={handleSaveProfile}
          disabled={isLoading}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color={t.onBrand} />
          ) : (
            <>
              <Ionicons
                name="checkmark-circle"
                size={24}
                color={t.onBrand}
              />
              <Text style={styles.saveButtonText}>Save Changes</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>

      <Dialog {...dialog.props} />
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: t.bg,
    },
    header: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: space.xl,
    },
    headerButton: {
      width: 40,
      height: 40,
      justifyContent: 'center',
      alignItems: 'center',
    },
    headerTitle: {
      ...type.heading,
      color: t.onBrand,
    },
    content: {
      flex: 1,
    },
    scrollContent: {
      padding: space.xl,
    },
    avatarSection: {
      alignItems: 'center',
      marginBottom: space.xxl,
    },
    avatarContainer: {
      width: 120,
      height: 120,
      borderRadius: 60,
      marginBottom: space.sm,
      position: 'relative',
    },
    avatar: {
      width: 120,
      height: 120,
      borderRadius: 60,
    },
    avatarPlaceholder: {
      width: 120,
      height: 120,
      borderRadius: 60,
      backgroundColor: t.fillStrong,
      justifyContent: 'center',
      alignItems: 'center',
    },
    avatarOverlay: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      borderRadius: 60,
      justifyContent: 'center',
      alignItems: 'center',
    },
    avatarEditIcon: {
      position: 'absolute',
      bottom: 0,
      right: 0,
      backgroundColor: t.brand,
      width: 36,
      height: 36,
      borderRadius: 18,
      justifyContent: 'center',
      alignItems: 'center',
      borderWidth: 3,
      borderColor: t.bg,
    },
    avatarHint: {
      ...type.small,
      color: t.textSoft,
    },
    section: {
      ...glassSurface(t),
      padding: space.xl,
      marginBottom: space.lg,
      ...lift(t, 1),
    },
    sectionHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: space.lg,
    },
    sectionTitle: {
      ...type.bodyStrong,
      color: t.text,
      marginBottom: space.lg,
    },
    inputContainer: {
      marginBottom: space.lg,
    },
    label: {
      ...type.label,
      color: t.text,
      marginBottom: space.xs,
    },
    input: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: t.bg,
      borderRadius: radius.sm,
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderWidth: 1,
      borderColor: t.line,
    },
    inputDisabled: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: t.fillSoft,
      borderRadius: radius.sm,
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderWidth: 1,
      borderColor: t.line,
    },
    textInput: {
      ...type.body,
      flex: 1,
      marginLeft: space.sm,
      color: t.text,
    },
    disabledText: {
      ...type.body,
      flex: 1,
      marginLeft: space.sm,
      color: t.textSoft,
    },
    hint: {
      ...type.caption,
      color: t.textSoft,
      marginTop: space.xs,
    },
    changePasswordButton: {
      backgroundColor: t.accent,
      borderRadius: radius.sm,
      paddingVertical: space.lg,
      alignItems: 'center',
      marginTop: space.lg,
    },
    changePasswordButtonText: {
      ...type.bodyStrong,
      color: t.onBrand,
    },
    saveButton: {
      backgroundColor: t.brand,
      borderRadius: radius.md,
      paddingVertical: space.lg,
      flexDirection: 'row',
      justifyContent: 'center',
      alignItems: 'center',
      ...lift(t, 2, t.brand),
    },
    saveButtonText: {
      ...type.bodyStrong,
      color: t.onBrand,
      marginLeft: space.sm,
    },
  });

export default EditProfileScreen;
