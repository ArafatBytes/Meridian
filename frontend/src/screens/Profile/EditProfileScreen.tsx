import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  Image,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useAuthStore } from '../../store';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import * as ImagePicker from 'expo-image-picker';
import { ProfileStackParamList } from '../../types';

type EditProfileScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'EditProfile'
>;

interface Props {
  navigation: EditProfileScreenNavigationProp;
}

const EditProfileScreen: React.FC<Props> = ({ navigation }) => {
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

  const pickImage = async () => {
    // Request permission
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Permission needed',
        'Please grant camera roll permissions to upload a profile picture.',
      );
      return;
    }

    // Launch image picker
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
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

      // Get current user
      const {
        data: { user: authUser },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !authUser) {
        throw new Error('User not authenticated');
      }

      // Create file name with subfolder (required by storage policies)
      const fileExt = uri.split('.').pop();
      const fileName = `${authUser.id}-${Date.now()}.${fileExt}`;
      const filePath = `${authUser.id}/${fileName}`; // Include user ID as subfolder

      // Read file as base64 and convert to ArrayBuffer for upload
      const response = await fetch(uri);
      const arrayBuffer = await response.arrayBuffer();

      // Upload to Supabase Storage using ArrayBuffer
      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(filePath, arrayBuffer, {
          contentType: `image/${fileExt}`,
          upsert: true,
        });

      if (uploadError) {
        throw uploadError;
      }

      // Get public URL
      const {
        data: { publicUrl },
      } = supabase.storage.from('avatars').getPublicUrl(filePath);

      setAvatar(publicUrl);
      Alert.alert('Success', 'Profile picture uploaded successfully!');
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to upload image');
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleSaveProfile = async () => {
    // Validate name
    if (!name.trim()) {
      Alert.alert('Error', 'Name is required and cannot be empty');
      return;
    }

    // Validate phone number if provided
    if (phone.trim()) {
      const phoneDigits = phone.replace(/\D/g, ''); // Remove non-digits

      if (phoneDigits.length !== 11) {
        Alert.alert('Error', 'Phone number must be exactly 11 digits');
        return;
      }

      if (!phoneDigits.startsWith('01')) {
        Alert.alert(
          'Error',
          'Phone number must start with 01 (Bangladeshi format)',
        );
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
        Alert.alert('Error', 'Invalid Bangladeshi phone number format');
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

      Alert.alert('Success', 'Profile updated successfully!', [
        {
          text: 'OK',
          onPress: () => navigation.goBack(),
        },
      ]);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to update profile');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert('Error', 'Please fill in all password fields');
      return;
    }

    if (currentPassword.length < 6) {
      Alert.alert('Error', 'Please enter your current password');
      return;
    }

    if (newPassword.length < 8) {
      Alert.alert('Error', 'New password must be at least 8 characters');
      return;
    }

    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'New passwords do not match');
      return;
    }

    if (newPassword === currentPassword) {
      Alert.alert(
        'Error',
        'New password must be different from current password',
      );
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
        Alert.alert('Error', 'Current password is incorrect');
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

      Alert.alert('Success', 'Password changed successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setShowPasswordSection(false);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to change password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity
          style={styles.headerButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={colors.white} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Edit Profile</Text>
        <View style={styles.headerButton} />
      </View>

      <ScrollView
        style={styles.content}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + spacing.xl },
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
                <Ionicons name="person" size={60} color={colors.gray400} />
              </View>
            )}
            {isUploadingImage ? (
              <View style={styles.avatarOverlay}>
                <ActivityIndicator size="small" color={colors.white} />
              </View>
            ) : (
              <View style={styles.avatarEditIcon}>
                <Ionicons name="camera" size={20} color={colors.white} />
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
              <Ionicons name="mail-outline" size={20} color={colors.gray400} />
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
                color={colors.textSecondary}
              />
              <TextInput
                style={styles.textInput}
                value={name}
                onChangeText={setName}
                placeholder="Enter your name"
                placeholderTextColor={colors.gray400}
              />
            </View>
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Phone</Text>
            <View style={styles.input}>
              <Ionicons
                name="call-outline"
                size={20}
                color={colors.textSecondary}
              />
              <TextInput
                style={styles.textInput}
                value={phone}
                onChangeText={setPhone}
                placeholder="Enter your phone number"
                placeholderTextColor={colors.gray400}
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
              color={colors.textSecondary}
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
                    color={colors.textSecondary}
                  />
                  <TextInput
                    style={styles.textInput}
                    value={currentPassword}
                    onChangeText={setCurrentPassword}
                    placeholder="Enter current password"
                    placeholderTextColor={colors.gray400}
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
                    color={colors.textSecondary}
                  />
                  <TextInput
                    style={styles.textInput}
                    value={newPassword}
                    onChangeText={setNewPassword}
                    placeholder="Enter new password (min 6 characters)"
                    placeholderTextColor={colors.gray400}
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
                    color={colors.textSecondary}
                  />
                  <TextInput
                    style={styles.textInput}
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    placeholder="Confirm new password"
                    placeholderTextColor={colors.gray400}
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
                  <ActivityIndicator size="small" color={colors.white} />
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
            <ActivityIndicator size="small" color={colors.white} />
          ) : (
            <>
              <Ionicons
                name="checkmark-circle"
                size={24}
                color={colors.white}
              />
              <Text style={styles.saveButtonText}>Save Changes</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    backgroundColor: colors.primary,
  },
  headerButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.white,
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    padding: spacing.lg,
  },
  avatarSection: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  avatarContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    marginBottom: spacing.sm,
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
    backgroundColor: colors.gray200,
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
    backgroundColor: colors.primary,
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: colors.background,
  },
  avatarHint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  section: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    elevation: 1,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  inputContainer: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  input: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  inputDisabled: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.gray100,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  textInput: {
    flex: 1,
    marginLeft: spacing.sm,
    fontSize: fontSize.md,
    color: colors.textPrimary,
  },
  disabledText: {
    flex: 1,
    marginLeft: spacing.sm,
    fontSize: fontSize.md,
    color: colors.gray500,
  },
  hint: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  changePasswordButton: {
    backgroundColor: colors.secondary,
    borderRadius: borderRadius.sm,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  changePasswordButtonText: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.white,
  },
  saveButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 2,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
  },
  saveButtonText: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.white,
    marginLeft: spacing.sm,
  },
});

export default EditProfileScreen;
