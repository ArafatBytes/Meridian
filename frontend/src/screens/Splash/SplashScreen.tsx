import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useAuthStore } from '../../store';
import { colors, spacing } from '../../theme';

const SplashScreen: React.FC = () => {
  const { initialize } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Meridian</Text>
      <Text style={styles.subtitle}>Your Safety Companion</Text>
      <ActivityIndicator
        size="large"
        color={colors.primary}
        style={styles.loader}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.primary,
  },
  title: {
    fontSize: 42,
    fontWeight: 'bold',
    color: colors.white,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 18,
    color: colors.white,
    marginBottom: spacing.xl,
  },
  loader: {
    marginTop: spacing.lg,
  },
});

export default SplashScreen;
