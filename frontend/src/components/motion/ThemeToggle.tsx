/**
 * The dark/light controls. Two of them, for two different jobs.
 *
 * * `ThemeToggle` — a round glass button for a screen header. One tap, flips.
 * * `ThemeChoice` — a three-state segment for Settings: Light / Dark / System.
 *
 * ## Why both, when one would compile
 *
 * The toggle is a two-state control over a three-state preference, so on its own
 * it can only ever express two of them: tap it once and `system` is gone, with
 * no way back. That is the standard bug in this feature — the user loses
 * "follow my phone" permanently and never knows they had it.
 *
 * So the quick control lives where you want it (in a header, one tap) and the
 * full one lives where a preference belongs (Settings), including the way back
 * to `system`. `ThemeToggle` also renders a small dot when the preference is
 * `system`, so the button says *which* of the three you are in rather than only
 * what is on screen.
 *
 * ## The icon crossfades and rotates rather than swapping
 *
 * Both icons are mounted; sun and moon counter-rotate and cross-fade. Swapping
 * one for the other on state change is instant and reads as a glitch — there is
 * no sense of a thing having changed, just a different picture. 180° of rotation
 * over 420 ms is long enough to see the transition and short enough that the
 * screen's own colour change (which is not animatable here) lands with it.
 */

import React, { useEffect, useState } from 'react';
import { Animated, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import * as Haptics from 'expo-haptics';

import { useTheme, type ThemePreference } from '../../theme/ThemeProvider';
import { useBlurProps, useHasBlur } from './BlurTarget';
import { useAnimatedValue } from './useAnimatedValue';

// ---------------------------------------------------------------------------
// ThemeToggle
// ---------------------------------------------------------------------------

export interface ThemeToggleProps {
  size?: number;
  /**
   * Force the icon colour. Pass `t.onBrand` when the button sits on the Aurora
   * gradient — it cannot know what is behind it.
   */
  color?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ size = 40, color }) => {
  const { t, isDark, toggle, preference, radius } = useTheme();
  const blurProps = useBlurProps();
  const hasBlur = useHasBlur();
  const tint = color ?? t.text;

  // 0 = light, 1 = dark. One driver for both icons.
  const phase = useAnimatedValue(isDark ? 1 : 0);

  useEffect(() => {
    Animated.timing(phase, {
      toValue: isDark ? 1 : 0,
      duration: 420,
      useNativeDriver: true,
    }).start();
  }, [isDark, phase]);

  const sun = {
    opacity: phase.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
    transform: [
      { rotate: phase.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '180deg'] }) },
      { scale: phase.interpolate({ inputRange: [0, 1], outputRange: [1, 0.4] }) },
    ],
  };
  const moon = {
    opacity: phase,
    transform: [
      { rotate: phase.interpolate({ inputRange: [0, 1], outputRange: ['-180deg', '0deg'] }) },
      { scale: phase.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] }) },
    ],
  };

  return (
    <Pressable
      onPress={() => {
        if (Platform.OS !== 'web') void Haptics.selectionAsync().catch(() => {});
        toggle();
      }}
      accessibilityRole="switch"
      accessibilityState={{ checked: isDark }}
      accessibilityLabel={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      hitSlop={8}
      style={[
        styles.round,
        {
          width: size,
          height: size,
          borderRadius: radius.pill,
          borderColor: t.glassBorder,
          backgroundColor: t.glassFill,
        },
      ]}
    >
      {hasBlur ? (
        <BlurView
          intensity={24}
          tint={t.blurTint}
          {...blurProps}
          style={[StyleSheet.absoluteFill, { borderRadius: radius.pill }]}
        />
      ) : null}
      {/* Both mounted, stacked, counter-rotating. */}
      <Animated.View style={[styles.icon, sun]}>
        <Ionicons name="sunny" size={size * 0.5} color={tint} />
      </Animated.View>
      <Animated.View style={[styles.icon, moon]}>
        <Ionicons name="moon" size={size * 0.46} color={tint} />
      </Animated.View>

      {/* "Following your phone". Without this the button cannot tell you that
          you are in `system` rather than in a mode you picked. */}
      {preference === 'system' ? (
        <View
          style={[styles.dot, { backgroundColor: t.brand, borderColor: t.bg }]}
          pointerEvents="none"
        />
      ) : null}
    </Pressable>
  );
};

// ---------------------------------------------------------------------------
// ThemeChoice
// ---------------------------------------------------------------------------

const OPTIONS: readonly { key: ThemePreference; label: string; icon: string }[] = [
  { key: 'light', label: 'Light', icon: 'sunny-outline' },
  { key: 'dark', label: 'Dark', icon: 'moon-outline' },
  { key: 'system', label: 'System', icon: 'phone-portrait-outline' },
];

/**
 * The full three-state preference, as a segmented control.
 *
 * The selected background slides between segments on a spring, for the same
 * reason the tab bar's pill does: a highlight that teleports tells you where you
 * are, one that travels tells you what you just did.
 *
 * Widths are computed from the container rather than measured per segment — the
 * three labels differ in width, and a sliding indicator that resizes as it moves
 * looks unstable. Equal thirds, which is also how iOS does it.
 */
export const ThemeChoice: React.FC = () => {
  const { t, type, space, radius, preference, setPreference } = useTheme();
  const [width, setWidth] = useState(0);
  const index = Math.max(
    0,
    OPTIONS.findIndex((option) => option.key === preference),
  );

  const slide = useAnimatedValue(index);
  useEffect(() => {
    Animated.spring(slide, {
      toValue: index,
      tension: 220,
      friction: 20,
      useNativeDriver: true,
    }).start();
  }, [index, slide]);

  const segment = width > 0 ? (width - 8) / OPTIONS.length : 0;

  return (
    <View
      onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
      style={[
        styles.segment,
        {
          borderRadius: radius.pill,
          backgroundColor: t.lineSoft,
          borderColor: t.line,
        },
      ]}
    >
      {segment > 0 ? (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.thumb,
            {
              width: segment,
              borderRadius: radius.pill,
              backgroundColor: t.surface,
              shadowColor: t.shadow,
              transform: [
                {
                  translateX: slide.interpolate({
                    inputRange: [0, OPTIONS.length - 1],
                    outputRange: [0, segment * (OPTIONS.length - 1)],
                  }),
                },
              ],
            },
          ]}
        />
      ) : null}

      {OPTIONS.map((option) => {
        const active = option.key === preference;
        return (
          <Pressable
            key={option.key}
            onPress={() => {
              if (Platform.OS !== 'web') void Haptics.selectionAsync().catch(() => {});
              setPreference(option.key);
            }}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            style={[styles.segmentItem, { paddingVertical: space.sm }]}
          >
            <Ionicons
              name={option.icon as never}
              size={14}
              color={active ? t.brand : t.textFaint}
            />
            <Text style={[type.label, styles.segmentLabel, { color: active ? t.text : t.textFaint }]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  round: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth * 2,
    overflow: 'hidden',
  },
  icon: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  dot: {
    position: 'absolute',
    right: 4,
    top: 4,
    width: 7,
    height: 7,
    borderRadius: 4,
    borderWidth: 1,
  },
  segment: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: StyleSheet.hairlineWidth * 2,
    padding: 4,
  },
  thumb: {
    position: 'absolute',
    left: 4,
    top: 4,
    bottom: 4,
    shadowOpacity: 1,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  segmentItem: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  segmentLabel: { marginLeft: 5 },
});

export default ThemeToggle;
