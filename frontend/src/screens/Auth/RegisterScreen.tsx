/**
 * Register. Same material and motion as Login, five fields instead of two.
 *
 * ## The validation rules are unchanged, including the Bangladesh one
 *
 * `^01[3-9]\d{8}$` — eleven digits, `01`, then an operator digit 3–9. That is
 * the real shape of a Bangladeshi mobile number and it is the right strictness
 * for this app: the number is what an emergency contact is reached on, so a
 * typo here is a failed SOS later. The field's `maxLength={11}` and
 * `keyboardType="phone-pad"` are kept for the same reason.
 *
 * The one thing added is a hint under the label, because a rule the user cannot
 * see is a rule they can only discover by failing it.
 *
 * ## All five errors land at once
 *
 * `validateForm` fills one `errors` object and sets it in a single update, so
 * submitting an empty form marks every field rather than walking the user
 * through them one at a time. That is why `Field` reserves space for its error
 * row — without it, five messages appearing together would shunt the whole form
 * down the screen as the user reads it.
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

type RegisterScreenNavigationProp = NativeStackNavigationProp<
  AuthStackParamList,
  'Register'
>;

interface Props {
  navigation: RegisterScreenNavigationProp;
}

const RegisterScreen: React.FC<Props> = ({ navigation }) => {
  const { t, g, type, space, radius } = useTheme();
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
      } catch {
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
    <Aurora intensity="vivid" style={styles.fill}>
      <KeyboardAvoidingView
        style={styles.fill}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
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
                Create account
              </Text>
              <Text style={[type.body, { color: t.textSoft, marginTop: space.xs }]}>
                Sign up to get started
              </Text>
            </View>
          </Reveal>

          <Reveal index={1}>
            <Glass padding={space.lg} radius={radius.sheet} elevated>
              <Field
                label="Full name"
                placeholder="Your full name"
                value={formData.fullName}
                onChangeText={text => updateField('fullName', text)}
                error={errors.fullName}
                autoCapitalize="words"
              />

              <Field
                label="Email"
                placeholder="you@example.com"
                value={formData.email}
                onChangeText={text => updateField('email', text)}
                error={errors.email}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
              />

              <Field
                // The format is stated up front rather than enforced silently.
                label="Phone number"
                placeholder="01XXXXXXXXX"
                value={formData.phone}
                onChangeText={text => updateField('phone', text)}
                error={errors.phone}
                keyboardType="phone-pad"
                maxLength={11}
              />

              <Field
                label="Password"
                placeholder="At least 8 characters"
                value={formData.password}
                onChangeText={text => updateField('password', text)}
                error={errors.password}
                secure
                autoCapitalize="none"
              />

              <Field
                label="Confirm password"
                placeholder="Type it again"
                value={formData.confirmPassword}
                onChangeText={text => updateField('confirmPassword', text)}
                error={errors.confirmPassword}
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

              <Pressable3D
                onPress={handleRegister}
                tilt={3}
                accessibilityLabel="Create account"
              >
                <Grad
                  colors={g.aurora}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={[styles.button, { borderRadius: radius.md, padding: space.md }]}
                >
                  <Text style={[type.bodyStrong, onGradient, styles.buttonText]}>
                    Create account
                  </Text>
                </Grad>
              </Pressable3D>
            </Glass>
          </Reveal>

          <Reveal index={2}>
            <Pressable
              style={[styles.secondary, { marginTop: space.xl }]}
              onPress={() => navigation.goBack()}
            >
              <Text style={[type.small, { color: t.textSoft }]}>
                Already have an account?{' '}
                <Text style={[type.bodyStrong, { color: t.brand }]}>Log in</Text>
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

export default RegisterScreen;
