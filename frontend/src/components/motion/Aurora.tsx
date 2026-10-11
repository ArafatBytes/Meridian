/**
 * `Aurora` — the app's ambient background. Signature motion #1.
 *
 * ## How it differs from the loading screen, deliberately
 *
 * `LoadingScreen` is built on **concentric, centred, rigid** motion: a ring
 * rotating at constant speed, a core pulsing on a fixed beat, four satellites
 * at fixed angles. It is a machine working, and it reads as one — which is right
 * for "setting up your safety zone", and wrong for every other screen, where it
 * would be a spinner that never stops.
 *
 * This is the opposite on every axis: **off-centre, drifting, and
 * non-repeating**. Three large blurred blobs move on long, mismatched timings
 * along different paths, so the composition never returns to the same frame.
 * There is no centre to look at and no beat to notice. It reads as weather
 * rather than machinery, which is what a background should do — present when you
 * look for it, invisible when you are reading.
 *
 * Same palette, same family. Different grammar.
 *
 * ## Why blobs and not a static gradient
 *
 * A `LinearGradient` behind content is flat: it establishes colour and then
 * nothing. Three overlapping radial blobs at low opacity produce *areas* of
 * colour that pass behind glass panels — which is the whole point, because the
 * blur has something to blur. Glass over a flat fill looks like a translucent
 * rectangle; glass over moving colour looks like glass.
 *
 * ## Performance, which is the real constraint for an always-on background
 *
 * Every animated value drives only `transform` and `opacity`, so all of it runs
 * on the native driver and none of it crosses the bridge per frame. The blobs
 * are plain `View`s with a huge `borderRadius` and a static `LinearGradient`
 * fill — no SVG, no filters, no `shadow` (Android shadow on a moving view is
 * the single most expensive thing you can ask for).
 *
 * `durations` are prime-ish and mutually indivisible (23s, 31s, 41s) so the
 * three loops do not share a period. With round numbers the composition visibly
 * resets, and once you have seen it reset you cannot stop seeing it.
 */

import React, { useEffect, useMemo } from 'react';
import { Animated, Dimensions, Easing, StyleSheet, View, type ViewStyle } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

import { useTheme } from '../../theme/ThemeProvider';
import { useAnimatedValue } from './useAnimatedValue';
import { BlurBackdrop, BlurTargetProvider } from './BlurTarget';

// @ts-ignore - LinearGradient's generated types fight `style` in this RN version
const Grad = LinearGradient as any;

const { width: W, height: H } = Dimensions.get('window');

/** One drifting blob. Drawn as concentric rings — see `FALLOFF`. */
interface BlobSpec {
  size: number;
  from: { x: number; y: number };
  to: { x: number; y: number };
  colors: readonly [string, string];
  opacity: number;
  durationMs: number;
}

export interface AuroraProps {
  /**
   * How present the field is.
   *
   * `ambient` sits under content and must never compete with it. `vivid` is for
   * a screen whose subject *is* the background — the loading and auth screens,
   * where there is almost nothing else on screen.
   */
  intensity?: 'ambient' | 'vivid';
  /** Stop the motion. Respect this for reduced-motion, or to save battery. */
  animated?: boolean;
  style?: ViewStyle;
  children?: React.ReactNode;
}

export const Aurora: React.FC<AuroraProps> = ({
  intensity = 'ambient',
  animated = true,
  style,
  children,
}) => {
  const { t, mode } = useTheme();

  const blobs = useMemo<BlobSpec[]>(() => {
    const [cyan, sky, azure] = t.auroraStops;
    // Dark mode needs more opacity to be visible against navy at all; light
    // mode needs less or the text contrast drops below readable.
    const base =
      intensity === 'vivid'
        ? mode === 'dark'
          ? 0.5
          : 0.38
        : mode === 'dark'
          ? 0.28
          : 0.2;

    return [
      {
        // Top-left, drifting right and down. The largest, so it anchors.
        size: W * 1.15,
        from: { x: -W * 0.3, y: -H * 0.12 },
        to: { x: W * 0.12, y: H * 0.08 },
        colors: [cyan, sky],
        opacity: base,
        durationMs: 23_000,
      },
      {
        // Bottom-right, travelling up and left — the opposite diagonal, so the
        // two never move in parallel.
        size: W * 1.0,
        from: { x: W * 0.45, y: H * 0.62 },
        to: { x: W * 0.1, y: H * 0.34 },
        colors: [azure, sky],
        opacity: base * 0.95,
        durationMs: 31_000,
      },
      {
        // Mid-right, mostly vertical and smallest. Breaks the symmetry the
        // other two would otherwise settle into.
        size: W * 0.72,
        from: { x: W * 0.52, y: -H * 0.04 },
        to: { x: W * 0.3, y: H * 0.26 },
        colors: [sky, cyan],
        opacity: base * 0.8,
        durationMs: 41_000,
      },
    ];
  }, [t.auroraStops, mode, intensity]);

  return (
    // The provider renders no view of its own, so it cannot become an ancestor
    // of both the target and the glass panels — that arrangement overflows
    // Android's render thread. See `BlurTarget.tsx`.
    <BlurTargetProvider>
      <View style={[styles.fill, { backgroundColor: t.bg }, style]} pointerEvents="box-none">
        {/* ONLY the blobs go in the target. This is what every `Glass` in
            `children` samples, and it must not contain a blur view itself. */}
        <BlurBackdrop pointerEvents="none">
          {blobs.map((blob, index) => (
            <Blob key={index} spec={blob} animated={animated} />
          ))}
        </BlurBackdrop>
        {/* Siblings, drawn above the target — never inside it. */}
        {children}
      </View>
    </BlurTargetProvider>
  );
};

const Blob: React.FC<{ spec: BlobSpec; animated: boolean }> = ({ spec, animated }) => {
  // One driver per blob, 0 → 1 → 0. Interpolated into x and y separately so the
  // path is a straight line the eye cannot trace, rather than an orbit it can.
  const drive = useAnimatedValue(0);

  useEffect(() => {
    if (!animated) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(drive, {
          toValue: 1,
          duration: spec.durationMs,
          // `inOut(sin)` rather than `linear`: a blob that reverses direction at
          // constant speed has a visible corner at each end of its path.
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(drive, {
          toValue: 0,
          duration: spec.durationMs,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [animated, drive, spec.durationMs]);

  const translateX = drive.interpolate({
    inputRange: [0, 1],
    outputRange: [spec.from.x, spec.to.x],
  });
  const translateY = drive.interpolate({
    inputRange: [0, 1],
    outputRange: [spec.from.y, spec.to.y],
  });
  // A slight breath in scale, out of phase with the travel, so size and
  // position do not peak together.
  const scale = drive.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [1, 1.14, 1],
  });

  return (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.blob,
        {
          width: spec.size,
          height: spec.size,
          opacity: spec.opacity,
          transform: [{ translateX }, { translateY }, { scale }],
        },
      ]}
    >
      {/* A radial falloff, faked with concentric rings.
          A single filled circle has a hard edge, and at these sizes that edge
          is plainly visible as an arc across the screen — which is the one
          thing an "aurora" must not look like. React Native has no radial
          gradient, and the usual substitutes are worse than the problem: a
          `shadow` on a view this large makes Android allocate an offscreen
          buffer every frame, and an SVG gradient pulls in a renderer for a
          decoration.

          Four nested circles at decreasing size and low alpha approximate the
          falloff: the centre accumulates all four and the rim carries only the
          faintest, so there is no single edge to see. Cheap, static, and it
          composites on the GPU like any other view. */}
      {FALLOFF.map(({ scale: ringScale, alpha }) => {
        const size = spec.size * ringScale;
        return (
          <View
            key={ringScale}
            style={[
              styles.ring,
              {
                width: size,
                height: size,
                borderRadius: size / 2,
                opacity: alpha,
                // Centred on the parent, which is what makes them concentric.
                marginLeft: -size / 2,
                marginTop: -size / 2,
              },
            ]}
          >
            <Grad
              colors={spec.colors}
              start={{ x: 0.1, y: 0 }}
              end={{ x: 0.9, y: 1 }}
              style={[styles.fill, { borderRadius: size / 2 }]}
            />
          </View>
        );
      })}
    </Animated.View>
  );
};

/**
 * The rings, outermost first. Sizes and alphas chosen so the accumulated
 * opacity rises smoothly toward the centre rather than in visible steps — the
 * outer ring is nearly transparent, which is what removes the edge.
 */
const FALLOFF = [
  { scale: 1.0, alpha: 0.22 },
  { scale: 0.78, alpha: 0.26 },
  { scale: 0.55, alpha: 0.3 },
  { scale: 0.32, alpha: 0.34 },
] as const;

const styles = StyleSheet.create({
  fill: { ...StyleSheet.absoluteFill },
  blob: {
    position: 'absolute',
    top: 0,
    left: 0,
    // The rings are positioned from this centre.
    alignItems: 'center',
    justifyContent: 'center',
    // No shadow and no overflow clipping. Both force Android to allocate an
    // offscreen buffer every frame for a view this large, and the frame budget
    // on a Unisoc device does not survive it.
  },
  ring: { position: 'absolute', left: '50%', top: '50%' },
});

export default Aurora;
