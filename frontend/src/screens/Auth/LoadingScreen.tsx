/**
 * The post-login screen. The app's signature animation, kept — and re-themed.
 *
 * ## Its motion grammar is deliberately unlike everything else
 *
 * **Concentric, centred, rigid**: a ring rotating at constant speed, a shield
 * pulsing on a fixed beat, four satellites at fixed angles. That reads as a
 * machine working, which is exactly right for "setting up your safety zone" and
 * exactly wrong anywhere else — on a content screen the same motion is a
 * spinner that never stops.
 *
 * So the rest of the app got different grammars rather than copies of this one:
 * `Aurora` drifts (ambient), `Reveal` arrives once (an event), `Pressable3D`
 * tilts under a finger (touch), and the SOS button emanates outward
 * (broadcasting). Four ideas, each meaning one thing. This file is the fifth and
 * it stays the only place that pulses in place.
 *
 * ## What changed
 *
 * * The gradient was `[primary, secondary, primary]` — indigo, pink, indigo. It
 *   is now `g.aurora` read from the theme, so it follows light/dark instead of
 *   being hard-coded, and it is three *different* stops rather than a palindrome
 *   (the old one put the same colour in both corners, which flattened it).
 * * Type is Sora, and the wordmark is tracked tight at display size.
 * * The three loading dots **used to share one driver**, so all three faded in
 *   and out together — a blinking bar rather than a loading indicator. They now
 *   run one driver with three phase offsets, which is the wave the original
 *   clearly intended.
 */

import React, { useEffect } from 'react';
import { View, Text, StyleSheet, Animated, Easing, Dimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';

import { useTheme } from '../../theme/ThemeProvider';
import { onGradient } from '../../theme/type';
import { useAnimatedValue } from '../../components/motion';

// @ts-ignore - LinearGradient type compatibility
const GradientView = LinearGradient as any;

const { width, height } = Dimensions.get('window');

/** The four satellites, at the four cardinal angles. */
const SATELLITES = [
  { key: 'location', style: 'satTop' as const, render: 'location' },
  { key: 'people', style: 'satRight' as const, render: 'people' },
  { key: 'warning', style: 'satBottom' as const, render: 'warning' },
  { key: 'flag', style: 'satLeft' as const, render: 'map-marker-alert' },
];

const LoadingScreen: React.FC = () => {
  const { g, type, space } = useTheme();

  const fade = useAnimatedValue(0);
  const scale = useAnimatedValue(0.3);
  const spinDrive = useAnimatedValue(0);
  const pulse = useAnimatedValue(1);
  const slide = useAnimatedValue(50);
  // One 0→1 driver for the dot wave; each dot reads it at a different offset.
  const wave = useAnimatedValue(0);

  useEffect(() => {
    const entrance = Animated.parallel([
      Animated.timing(fade, {
        toValue: 1,
        duration: 800,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }),
      Animated.spring(scale, {
        toValue: 1,
        friction: 4,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(slide, {
        toValue: 0,
        duration: 800,
        useNativeDriver: true,
        easing: Easing.out(Easing.ease),
      }),
    ]);

    const spin = Animated.loop(
      Animated.timing(spinDrive, {
        toValue: 1,
        duration: 2_000,
        useNativeDriver: true,
        easing: Easing.linear,
      }),
    );

    const breathe = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1.2,
          duration: 1_000,
          useNativeDriver: true,
          easing: Easing.inOut(Easing.ease),
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: 1_000,
          useNativeDriver: true,
          easing: Easing.inOut(Easing.ease),
        }),
      ]),
    );

    const dots = Animated.loop(
      Animated.timing(wave, {
        toValue: 1,
        duration: 1_200,
        useNativeDriver: true,
        easing: Easing.linear,
      }),
    );

    entrance.start();
    spin.start();
    breathe.start();
    dots.start();

    return () => {
      entrance.stop();
      spin.stop();
      breathe.stop();
      dots.stop();
    };
  }, [fade, scale, spinDrive, pulse, slide, wave]);

  const spin = spinDrive.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <GradientView
      colors={g.aurora}
      style={styles.container}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
    >
      <Animated.View style={[styles.content, { opacity: fade, transform: [{ scale }] }]}>
        {/* Rotating outer ring. */}
        <Animated.View style={[styles.outerRing, { transform: [{ rotate: spin }] }]}>
          <View style={styles.ring} />
        </Animated.View>

        {/* Pulsing shield. */}
        <Animated.View
          style={[
            styles.iconContainer,
            { marginBottom: space.xl, transform: [{ scale: pulse }] },
          ]}
        >
          <MaterialCommunityIcons name="shield-check" size={80} color="#FFFFFF" />
        </Animated.View>

        {/* The four satellites, at fixed angles — the rigid part of the grammar. */}
        <View style={styles.satellites} pointerEvents="none">
          {SATELLITES.map((satellite) => (
            <Animated.View
              key={satellite.key}
              style={[styles.satellite, styles[satellite.style], { opacity: fade }]}
            >
              {satellite.render === 'map-marker-alert' ? (
                <MaterialCommunityIcons name="map-marker-alert" size={24} color="#FFFFFF" />
              ) : (
                <Ionicons name={satellite.render as never} size={24} color="#FFFFFF" />
              )}
            </Animated.View>
          ))}
        </View>

        <Animated.View
          style={[
            styles.textContainer,
            { marginTop: space.xxl, opacity: fade, transform: [{ translateY: slide }] },
          ]}
        >
          <Text style={[type.hero, onGradient, styles.title]}>Meridian</Text>
          <Text style={[type.body, onGradient, styles.subtitle, { marginTop: space.sm }]}>
            Setting up your safety zone…
          </Text>

          {/* Three dots, one driver, three phases. */}
          <View style={[styles.dots, { marginTop: space.lg }]}>
            {[0, 1, 2].map((i) => (
              <Animated.View
                key={i}
                style={[
                  styles.dot,
                  {
                    // Each dot peaks a third of a cycle after the last. The
                    // ranges overlap at the wrap point so the wave is
                    // continuous rather than restarting from dark.
                    opacity: wave.interpolate({
                      inputRange: [0, 0.33, 0.66, 1],
                      outputRange: shiftedOpacity(i),
                    }),
                  },
                ]}
              />
            ))}
          </View>
        </Animated.View>
      </Animated.View>

      {/* Static decoration, faded in with everything else. */}
      <Animated.View style={[styles.floatingCircle, styles.circle1, { opacity: fade }]} />
      <Animated.View style={[styles.floatingCircle, styles.circle2, { opacity: fade }]} />
      <Animated.View style={[styles.floatingCircle, styles.circle3, { opacity: fade }]} />
    </GradientView>
  );
};

/**
 * Opacity keyframes for dot `i`, rotated by a third of the cycle.
 *
 * Each dot is bright at its own slot and dim at the other two, and the first and
 * last values match so the loop joins seamlessly.
 */
function shiftedOpacity(index: number): number[] {
  const bright = 1;
  const dim = 0.3;
  const frames = [dim, dim, dim, dim];
  frames[index] = bright;
  // The frame at t=1 must equal the frame at t=0, or the wave jumps on every
  // repeat. Dot 0's bright moment therefore lands on the cycle boundary and
  // appears at both ends.
  frames[3] = frames[0];
  return frames;
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  content: { alignItems: 'center', justifyContent: 'center' },
  outerRing: {
    position: 'absolute',
    width: 200,
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
  },
  ring: {
    width: 200,
    height: 200,
    borderRadius: 100,
    borderWidth: 3,
    borderColor: '#FFFFFF',
    borderStyle: 'dashed',
    opacity: 0.3,
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  satellites: { position: 'absolute', width: 280, height: 280 },
  satellite: {
    position: 'absolute',
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  satTop: { top: 0, left: '50%', marginLeft: -24 },
  satRight: { right: 0, top: '50%', marginTop: -24 },
  satBottom: { bottom: 0, left: '50%', marginLeft: -24 },
  satLeft: { left: 0, top: '50%', marginTop: -24 },
  textContainer: { alignItems: 'center' },
  title: { color: '#FFFFFF' },
  subtitle: { color: 'rgba(255, 255, 255, 0.92)', textAlign: 'center' },
  dots: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center' },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FFFFFF',
    marginHorizontal: 5,
  },
  floatingCircle: {
    position: 'absolute',
    borderRadius: 1000,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  circle1: { width: 100, height: 100, top: height * 0.1, left: width * 0.1 },
  circle2: { width: 150, height: 150, bottom: height * 0.15, right: width * 0.05 },
  circle3: { width: 80, height: 80, top: height * 0.7, left: width * 0.15 },
});

export default LoadingScreen;
