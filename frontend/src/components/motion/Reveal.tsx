/**
 * `Reveal` and `Pressable3D` — signature motions #2 and #3.
 *
 * Three distinct grammars across the app, and the point of keeping them
 * distinct is that motion should tell you *what kind of thing* is happening:
 *
 * | | grammar | means |
 * |---|---|---|
 * | `LoadingScreen` | concentric, centred, rigid | the system is working |
 * | `Aurora` | off-centre, drifting, non-repeating | ambient, ignore me |
 * | **`Reveal`** | **staggered, directional, one-shot** | **content has arrived** |
 * | **`Pressable3D`** | **tilt + depth, driven by touch** | **you are touching this** |
 *
 * Nothing here loops. That is the whole distinction from the first two: a loop
 * is a status, a one-shot is an event. Content arriving is an event.
 */

import React, { useEffect } from 'react';
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import * as Haptics from 'expo-haptics';

import { useAnimatedValue } from './useAnimatedValue';

// ---------------------------------------------------------------------------
// Reveal
// ---------------------------------------------------------------------------

export interface RevealProps {
  children: React.ReactNode;
  /**
   * Position in the stagger. Child 0 starts immediately, each subsequent one
   * `stagger` ms later.
   *
   * The stagger is what makes a screen feel assembled rather than switched on.
   * Everything appearing at once reads as a page load; a 60ms cascade reads as
   * the interface composing itself, and it costs nothing.
   */
  index?: number;
  /** Gap between children, ms. 60 is brisk; past ~90 it feels slow. */
  stagger?: number;
  /** Where it travels from. `up` (default) suits lists; `scale` suits hero cards. */
  from?: 'up' | 'down' | 'scale';
  /** Travel distance in px for `up`/`down`. */
  distance?: number;
  delay?: number;
  style?: StyleProp<ViewStyle>;
}

/**
 * One-shot entrance. Fades, travels, and settles.
 *
 * The curve is `Easing.bezier(0.16, 1, 0.3, 1)` — a strong ease-out that covers
 * most of the distance early and settles slowly. It is the difference between
 * "an element moved" and "an element arrived": a linear or `ease` curve makes
 * the end of the travel the most visible part, which draws the eye to the
 * motion instead of to the content.
 *
 * Deliberately **not** a spring. Springs overshoot, and twelve list rows each
 * overshooting by a few pixels at slightly different times looks like jelly.
 * Springs are for things you touch — see `Pressable3D`.
 */
export const Reveal: React.FC<RevealProps> = ({
  children,
  index = 0,
  stagger = 60,
  from = 'up',
  distance = 18,
  delay = 0,
  style,
}) => {
  const progress = useAnimatedValue(0);

  useEffect(() => {
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: 520,
      delay: delay + index * stagger,
      easing: Easing.bezier(0.16, 1, 0.3, 1),
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [delay, index, progress, stagger]);

  const transform =
    from === 'scale'
      ? [{ scale: progress.interpolate({ inputRange: [0, 1], outputRange: [0.94, 1] }) }]
      : [
          {
            translateY: progress.interpolate({
              inputRange: [0, 1],
              outputRange: [from === 'up' ? distance : -distance, 0],
            }),
          },
        ];

  return (
    <Animated.View style={[style, { opacity: progress, transform }]}>{children}</Animated.View>
  );
};

// ---------------------------------------------------------------------------
// Pressable3D
// ---------------------------------------------------------------------------

export interface Pressable3DProps {
  children: React.ReactNode;
  onPress?: () => void;
  onLongPress?: () => void;
  disabled?: boolean;
  /**
   * How far it tilts, in degrees. 0 gives press-depth only.
   *
   * The tilt is what makes this read as 3D rather than as a scale-down: the card
   * rotates very slightly on X as it sinks, so its top edge appears to move away
   * from you. 4–6° is the band where it is felt and not seen; past ~8° the text
   * visibly skews and it looks broken.
   */
  tilt?: number;
  /** Haptic on press-in. `false` for anything tapped repeatedly. */
  haptic?: boolean;
  style?: StyleProp<ViewStyle>;
  /** Accessibility label — this renders no text of its own. */
  accessibilityLabel?: string;
}

/**
 * A surface that responds to touch with depth.
 *
 * Springs here, where `Reveal` uses a curve, and the asymmetry is the design:
 * **a spring is the right model for something you are physically touching**,
 * because a slight overshoot on release is what a real object does. The same
 * overshoot applied to content arriving would be noise.
 *
 * `perspective` must come **first** in the transform array. React Native applies
 * transforms in order, and a `rotateX` before the perspective is a flat shear
 * with no depth at all — the most common way a tilt effect ends up looking wrong.
 */
export const Pressable3D: React.FC<Pressable3DProps> = ({
  children,
  onPress,
  onLongPress,
  disabled = false,
  tilt = 5,
  haptic = true,
  style,
  accessibilityLabel,
}) => {
  const press = useAnimatedValue(0);

  const animateTo = (value: number) =>
    Animated.spring(press, {
      toValue: value,
      // Low tension, high-ish friction: quick to depress, calm on the way back.
      // A bouncy return on a card the size of a screen looks cheap.
      tension: 220,
      friction: 18,
      useNativeDriver: true,
    }).start();

  return (
    <Pressable
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPressIn={() => {
        animateTo(1);
        if (haptic && Platform.OS !== 'web') {
          // Selection, not Impact: this fires on every press of every card, and
          // Impact at that frequency is fatiguing within a minute.
          void Haptics.selectionAsync().catch(() => {});
        }
      }}
      onPressOut={() => animateTo(0)}
      onPress={onPress}
      onLongPress={onLongPress}
    >
      <Animated.View
        style={[
          style,
          {
            opacity: disabled ? 0.5 : 1,
            transform: [
              // First. See the note above.
              { perspective: 800 },
              {
                scale: press.interpolate({ inputRange: [0, 1], outputRange: [1, 0.975] }),
              },
              {
                rotateX: press.interpolate({
                  inputRange: [0, 1],
                  outputRange: ['0deg', `${tilt}deg`],
                }),
              },
            ],
          },
        ]}
      >
        {children}
      </Animated.View>
    </Pressable>
  );
};

export default Reveal;
