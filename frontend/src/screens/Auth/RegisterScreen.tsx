import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AuthStackParamList } from '../../types';
import { useAuthStore } from '../../store';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import LoadingScreen from './LoadingScreen';

type RegisterScreenNavigationProp = NativeStackNavigationProp<
  AuthStackParamList,
  'Register'
>;

interface Props {
  navigation: RegisterScreenNavigationProp;
}

const RegisterScreen: React.FC<Props> = ({ navigation }) => {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    phone: '',
    password: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showLoading, setShowLoading] = useState(false);
  const isLoadingRef = useRef(false);

  const { registerWithoutAuth, setAuthenticated, error } = useAuthStore();
  const insets = useSafeAreaInsets();

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.fullName.trim()) {
      newErrors.fullName = 'Full name is required';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Invalid email format';
    }

    if (!formData.phone.trim()) {
      newErrors.phone = 'Phone number is required';
    } else if (!/^01[3-9]\d{8}$/.test(formData.phone)) {
      newErrors.phone = 'Invalid Bangladesh phone number';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleRegister = async () => {
    if (!validateForm()) {
      return;
    }

    // Prevent multiple clicks
    if (isLoadingRef.current) return;

    // Show loading screen immediately
    isLoadingRef.current = true;
    setShowLoading(true);

    // Use requestAnimationFrame to ensure state updates before async operation
    requestAnimationFrame(async () => {
      try {
        // Small delay to ensure render
        await new Promise(resolve => setTimeout(resolve, 100));

        // Perform registration without setting auth state
        const user = await registerWithoutAuth({
          name: formData.fullName,
          email: formData.email,
          phone: formData.phone,
          password: formData.password,
        });

        // Keep loading screen visible for 2 seconds
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Now set authenticated state to trigger navigation
        setAuthenticated(user);
      } catch (err) {
        // Hide loading screen on error
        isLoadingRef.current = false;
        setShowLoading(false);
        // Error handled by store
      }
    });
  };

  const updateField = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => ({ ...prev, [field]: '' }));
  };

  // Show loading screen - use ref to ensure it stays true
  if (showLoading || isLoadingRef.current) {
    return <LoadingScreen />;
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingTop: insets.top, paddingBottom: insets.bottom + 20 },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>Sign up to get started</Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Full Name</Text>
            <TextInput
              style={[styles.input, errors.fullName ? styles.inputError : null]}
              placeholder="Enter your full name"
              placeholderTextColor={colors.gray400}
              value={formData.fullName}
              onChangeText={text => updateField('fullName', text)}
              autoCapitalize="words"
            />
            {errors.fullName ? (
              <Text style={styles.errorText}>{errors.fullName}</Text>
            ) : null}
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={[styles.input, errors.email ? styles.inputError : null]}
              placeholder="Enter your email"
              placeholderTextColor={colors.gray400}
              value={formData.email}
              onChangeText={text => updateField('email', text)}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
            {errors.email ? (
              <Text style={styles.errorText}>{errors.email}</Text>
            ) : null}
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Phone Number</Text>
            <TextInput
              style={[styles.input, errors.phone ? styles.inputError : null]}
              placeholder="01XXXXXXXXX"
              placeholderTextColor={colors.gray400}
              value={formData.phone}
              onChangeText={text => updateField('phone', text)}
              keyboardType="phone-pad"
              maxLength={11}
            />
            {errors.phone ? (
              <Text style={styles.errorText}>{errors.phone}</Text>
            ) : null}
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={[styles.input, errors.password ? styles.inputError : null]}
              placeholder="Create a password"
              placeholderTextColor={colors.gray400}
              value={formData.password}
              onChangeText={text => updateField('password', text)}
              secureTextEntry
              autoCapitalize="none"
            />
            {errors.password ? (
              <Text style={styles.errorText}>{errors.password}</Text>
            ) : null}
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Confirm Password</Text>
            <TextInput
              style={[
                styles.input,
                errors.confirmPassword ? styles.inputError : null,
              ]}
              placeholder="Confirm your password"
              placeholderTextColor={colors.gray400}
              value={formData.confirmPassword}
              onChangeText={text => updateField('confirmPassword', text)}
              secureTextEntry
              autoCapitalize="none"
            />
            {errors.confirmPassword ? (
              <Text style={styles.errorText}>{errors.confirmPassword}</Text>
            ) : null}
          </View>

          {error ? <Text style={styles.serverError}>{error}</Text> : null}

          <TouchableOpacity
            style={[styles.button, showLoading && styles.buttonDisabled]}
            onPress={handleRegister}
            disabled={showLoading}
          >
            {showLoading ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <Text style={styles.buttonText}>Sign Up</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() => navigation.goBack()}
            disabled={showLoading}
          >
            <Text style={styles.secondaryButtonText}>
              Already have an account? Login
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  header: {
    marginBottom: spacing.xl,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  form: {
    width: '100%',
  },
  inputContainer: {
    marginBottom: spacing.lg,
  },
  label: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.textPrimary,
  },
  inputError: {
    borderColor: colors.error,
  },
  errorText: {
    color: colors.error,
    fontSize: fontSize.sm,
    marginTop: spacing.xs,
  },
  serverError: {
    color: colors.error,
    fontSize: fontSize.sm,
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  secondaryButton: {
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  secondaryButtonText: {
    color: colors.primary,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});

export default RegisterScreen;
