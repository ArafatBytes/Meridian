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

type LoginScreenNavigationProp = NativeStackNavigationProp<
  AuthStackParamList,
  'Login'
>;

interface Props {
  navigation: LoginScreenNavigationProp;
}

const LoginScreen: React.FC<Props> = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [showLoading, setShowLoading] = useState(false);
  const isLoadingRef = useRef(false);

  const { loginWithoutAuth, setAuthenticated, error } = useAuthStore();
  const insets = useSafeAreaInsets();

  const validateEmail = (text: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(text);
  };

  const handleLogin = async () => {
    setEmailError('');
    setPasswordError('');

    if (!email) {
      setEmailError('Email is required');
      return;
    }

    if (!validateEmail(email)) {
      setEmailError('Invalid email format');
      return;
    }

    if (!password) {
      setPasswordError('Password is required');
      return;
    }

    if (password.length < 8) {
      setPasswordError('Password must be at least 8 characters');
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

        // Perform login without setting auth state
        const user = await loginWithoutAuth(email, password);

        // Keep loading screen visible for 2 seconds
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Now set authenticated state to trigger navigation
        setAuthenticated(user);
      } catch (err) {
        // Hide loading screen on error
        isLoadingRef.current = false;
        setShowLoading(false);
        // Error is handled by the store
      }
    });
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
          <Text style={styles.title}>Welcome Back</Text>
          <Text style={styles.subtitle}>Sign in to continue</Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={[styles.input, emailError ? styles.inputError : null]}
              placeholder="Enter your email"
              placeholderTextColor={colors.gray400}
              value={email}
              onChangeText={text => {
                setEmail(text);
                setEmailError('');
              }}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
            {emailError ? (
              <Text style={styles.errorText}>{emailError}</Text>
            ) : null}
          </View>

          <View style={styles.inputContainer}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={[styles.input, passwordError ? styles.inputError : null]}
              placeholder="Enter your password"
              placeholderTextColor={colors.gray400}
              value={password}
              onChangeText={text => {
                setPassword(text);
                setPasswordError('');
              }}
              secureTextEntry
              autoCapitalize="none"
            />
            {passwordError ? (
              <Text style={styles.errorText}>{passwordError}</Text>
            ) : null}
          </View>

          {error ? <Text style={styles.serverError}>{error}</Text> : null}

          <TouchableOpacity
            style={[styles.button, showLoading && styles.buttonDisabled]}
            onPress={handleLogin}
            disabled={showLoading}
          >
            {showLoading ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <Text style={styles.buttonText}>Login</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() => navigation.navigate('Register')}
            disabled={showLoading}
          >
            <Text style={styles.secondaryButtonText}>
              Don't have an account? Sign Up
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

export default LoginScreen;
