/**
 * Login. The first screen anyone sees, so it carries the full design language:
 * a vivid Aurora field, the form on one pane of glass, a staggered entrance.
 *
 * ## `intensity="vivid"` here, `ambient` everywhere else
 *
 * There is almost nothing on this screen but the background, so the background
 * is allowed to be the subject. On a content screen the same field would
 * compete with what the user is reading — hence the two levels, and hence
 * `Aurora` taking a prop rather than being tuned per screen.
 *
 * ## The dead loading branch is gone
 *
 * The submit button used to render an `ActivityIndicator` when `showLoading`
 * was true, and was `disabled={showLoading}`. Neither could ever happen: the
 * component returns `<LoadingScreen />` above this point whenever `showLoading`
 * or `isLoadingRef.current` is set, so by the time the button renders both are
 * false. Three pieces of state-handling that could not run.
 *
 * The guard that does the work — `isLoadingRef`, which blocks a second submit
 * between the tap and the re-render — is unchanged. Only the unreachable UI
 * went.
 */

import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Pressable,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AuthStackParamList } from '../../types';
import { useAuthStore } from '../../store';
import { useTheme } from '../../theme/ThemeProvider';
import { onGradient } from '../../theme/type';
import { Aurora, Glass, Reveal, Pressable3D, ThemeToggle } from '../../components/motion';
import { Field } from '../../components/Field';
import LoadingScreen from './LoadingScreen';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

type LoginScreenNavigationProp = NativeStackNavigationProp<AuthStackParamList, 'Login'>;

interface Props {
  navigation: LoginScreenNavigationProp;
}

const LoginScreen: React.FC<Props> = ({ navigation }) => {
  const { t, g, type, space, radius } = useTheme();
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

    // Prevent multiple clicks. A ref, not state: this has to be true before the
    // next render, and a second tap can land in that gap.
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
      } catch {
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
    <Aurora intensity="vivid" style={styles.fill}>
      <KeyboardAvoidingView
        style={styles.fill}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* Absolute so it does not take part in the centred layout below. */}
        <View style={[styles.toggle, { top: insets.top + space.sm, right: space.lg }]}>
          <ThemeToggle size={38} />
        </View>

        <ScrollView
          contentContainerStyle={[
            styles.scrollContent,
            {
              padding: space.lg,
              paddingTop: insets.top + space.huge,
              paddingBottom: insets.bottom + space.xl,
            },
          ]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Reveal index={0} from="scale">
            <View style={[styles.brand, { marginBottom: space.xl }]}>
              <Grad
                colors={g.aurora}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={[styles.mark, { borderRadius: radius.card }]}
              >
                <Ionicons name="shield-checkmark" size={30} color="#FFFFFF" />
              </Grad>
              <Text style={[type.hero, { color: t.text, marginTop: space.lg }]}>
                Welcome back
              </Text>
              <Text style={[type.body, { color: t.textSoft, marginTop: space.xs }]}>
                Sign in to continue
              </Text>
            </View>
          </Reveal>

          <Reveal index={1}>
            <Glass padding={space.lg} radius={radius.sheet} elevated>
              <Field
                label="Email"
                placeholder="you@example.com"
                value={email}
                onChangeText={text => {
                  setEmail(text);
                  setEmailError('');
                }}
                error={emailError}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
              />

              <Field
                label="Password"
                placeholder="At least 8 characters"
                value={password}
                onChangeText={text => {
                  setPassword(text);
                  setPasswordError('');
                }}
                error={passwordError}
                secure
                autoCapitalize="none"
              />

              {error ? (
                <Text
                  style={[
                    type.small,
                    styles.serverError,
                    { color: t.danger, marginBottom: space.md },
                  ]}
                >
                  {error}
                </Text>
              ) : null}

              <Pressable3D onPress={handleLogin} tilt={3} accessibilityLabel="Log in">
                <Grad
                  colors={g.aurora}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={[styles.button, { borderRadius: radius.md, padding: space.md }]}
                >
                  <Text style={[type.bodyStrong, onGradient, styles.buttonText]}>
                    Log in
                  </Text>
                </Grad>
              </Pressable3D>
            </Glass>
          </Reveal>

          <Reveal index={2}>
            <Pressable
              style={[styles.secondary, { marginTop: space.xl }]}
              onPress={() => navigation.navigate('Register')}
            >
              <Text style={[type.small, { color: t.textSoft }]}>
                Don't have an account?{' '}
                <Text style={[type.bodyStrong, { color: t.brand }]}>Sign up</Text>
              </Text>
            </Pressable>
          </Reveal>
        </ScrollView>
      </KeyboardAvoidingView>
    </Aurora>
  );
};

const styles = StyleSheet.create({
  fill: { flex: 1 },
  toggle: { position: 'absolute', zIndex: 2 },
  scrollContent: { flexGrow: 1, justifyContent: 'center' },
  brand: { alignItems: 'center' },
  mark: { width: 60, height: 60, alignItems: 'center', justifyContent: 'center' },
  serverError: { textAlign: 'center' },
  button: { alignItems: 'center' },
  buttonText: { color: '#FFFFFF' },
  secondary: { alignItems: 'center' },
});

export default LoginScreen;
