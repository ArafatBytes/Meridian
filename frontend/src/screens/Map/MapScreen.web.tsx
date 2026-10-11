/**
 * The web stand-in for the map.
 *
 * `react-native-maps` has no web implementation, so Metro picks this file up
 * through the `.web.tsx` extension and the bundle never pulls in the native
 * module. The app is demoed on Android; this exists so a web build does not fail
 * on an import, and it is honest about what it is rather than rendering an empty
 * grey box.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';

const MapScreen = () => {
  const { type } = useTheme();
  const styles = useStyles(makeStyles);
  return (
    <View style={styles.container}>
      <Text style={[type.body, styles.text]}>
        The map is only available in the mobile app.
      </Text>
    </View>
  );
};

const makeStyles = (t: Palette) =>
  StyleSheet.create({
    container: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      padding: 24,
      backgroundColor: t.bg,
    },
    text: { color: t.textSoft, textAlign: 'center' },
  });

export default MapScreen;
