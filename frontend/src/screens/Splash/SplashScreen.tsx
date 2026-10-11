import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useAuthStore } from '../../store';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { fontFamily, space } from '../../theme/type';

const SplashScreen: React.FC = () => {
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
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
        color={t.brand}
        style={styles.loader}
      />
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: t.brand,
    },
    title: {
      fontFamily: fontFamily.display,
      fontSize: 42,
      color: t.onBrand,
      marginBottom: space.sm,
    },
    subtitle: {
      fontFamily: fontFamily.body,
      fontSize: 18,
      color: t.onBrand,
      marginBottom: space.xxl,
    },
    loader: {
      marginTop: space.xl,
    },
  });

export default SplashScreen;
