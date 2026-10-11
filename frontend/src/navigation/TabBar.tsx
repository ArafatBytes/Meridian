/**
 * The tab bar. A floating, blurred, iOS-style bar — built by hand.
 *
 * ## Why not configure the stock one
 *
 * `@react-navigation/bottom-tabs` draws a bar pinned to the bottom edge with an
 * opaque background and a hairline on top. You can colour it, and that is about
 * it. Four things this needs are not reachable through options:
 *
 * 1. **Detachment.** It floats with a margin on all three sides, so content
 *    scrolls *under* it and the blur has something to blur. A pinned bar has
 *    nothing behind it and glass is pointless.
 * 2. **A moving indicator.** The pill slides between tabs rather than appearing
 *    under the active one. The slide is the thing that reads as iOS: it tells
 *    you where you came from, not just where you are.
 * 3. **Icon motion.** The active icon lifts and scales; the label fades in
 *    beneath it. The stock bar renders icon and label as static children.
 * 4. **Blur that follows the theme.** Light and dark need different tints, and
 *    Android needs a nominated blur target — see `BlurTarget.tsx`.
 *
 * ## The pill is positioned, not laid out
 *
 * Tab width is measured once (`onLayout` on the row) and the pill is absolutely
 * positioned at `index * tabWidth`, animated with a spring. Letting flexbox
 * place it inside the active tab would make it jump, because there is no
 * layout transition between two different parents.
 *
 * ## It hides itself on a pushed screen
 *
 * Each tab holds a stack, and a pushed screen — a report, a form, Guardian — is
 * a detail view, not a destination. Keeping a floating bar over a form means its
 * submit button sits underneath the bar, and ten screens would each have to
 * reserve space for it.
 *
 * So the bar slides out whenever the focused tab's stack is deeper than its
 * first screen, which is what iOS does and what makes "back" rather than the tab
 * bar the way out of a detail view. One rule here instead of a `paddingBottom`
 * in every pushed screen, and the screens get the whole window.
 *
 * ## Labels only on the active tab
 *
 * Four icons with four labels is eight pieces of text competing at 11px. Only
 * the active tab is labelled; the rest are icons, which is what iOS 17+ does on
 * a floating bar and what makes it read as a control rather than a menu.
 */

import React, { useEffect, useState } from 'react';
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  StyleSheet,
  View,
  type LayoutChangeEvent,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import type { BottomTabBarProps } from '@react-navigation/bottom-tabs';

import { useTheme } from '../theme/ThemeProvider';
import { useAnimatedValue } from '../components/motion/useAnimatedValue';
import { useBlurProps, useHasBlur } from '../components/motion/BlurTarget';
import { TAB_BAR_HEIGHT as BAR_HEIGHT } from './metrics';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

const SIDE_MARGIN = 16;

export const TabBar: React.FC<BottomTabBarProps> = ({ state, descriptors, navigation }) => {
  const { t, g, type, radius } = useTheme();
  const blurProps = useBlurProps();
  const hasBlur = useHasBlur();
  const insets = useSafeAreaInsets();
  const [rowWidth, setRowWidth] = useState(0);

  const tabCount = state.routes.length;
  const tabWidth = rowWidth > 0 ? rowWidth / tabCount : 0;

  // A nested stack that has pushed past its first screen. `state` on a route is
  // undefined until that navigator has initialised, which reads correctly as
  // "not pushed".
  const nested = state.routes[state.index]?.state;
  const pushed = typeof nested?.index === 'number' && nested.index > 0;

  // One driver for the pill, in *tab index* units rather than pixels, so a
  // rotation or width change does not need the animation restarted.
  const slide = useAnimatedValue(state.index);

  useEffect(() => {
    Animated.spring(slide, {
      toValue: state.index,
      // Firm and barely bouncy. A visible bounce on the indicator draws the eye
      // to the bar instead of to the screen you just navigated to.
      tension: 230,
      friction: 22,
      useNativeDriver: true,
    }).start();
  }, [slide, state.index]);

  // Slides down and fades rather than unmounting: an unmount would drop the
  // measured width and the pill's position, so coming back from a detail screen
  // would show the bar rebuilding itself.
  const hide = useAnimatedValue(0);
  useEffect(() => {
    Animated.timing(hide, {
      toValue: pushed ? 1 : 0,
      duration: 220,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [hide, pushed]);

  const onLayout = (event: LayoutChangeEvent) => setRowWidth(event.nativeEvent.layout.width);

  return (
    <Animated.View
      // Untappable while hidden, or an invisible bar still takes touches meant
      // for the screen underneath it.
      pointerEvents={pushed ? 'none' : 'auto'}
      style={[
        styles.wrap,
        {
          opacity: hide.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
          transform: [
            {
              translateY: hide.interpolate({
                inputRange: [0, 1],
                outputRange: [0, BAR_HEIGHT + 24],
              }),
            },
          ],
          // Sits above the gesture area, not in it. On a phone with no home
          // button, `insets.bottom` is the swipe strip; a bar flush against it
          // gets its taps stolen by the system.
          bottom: Math.max(insets.bottom, 10),
          marginHorizontal: SIDE_MARGIN,
          borderRadius: radius.pill,
          borderColor: t.glassBorder,
          // Translucent only when something is actually blurring behind it.
          //
          // On iOS that is always; on Android it is true as long as
          // `MainNavigator` is wrapping each screen in a `ClaimBlurTarget`, so
          // the focused screen is in scope to be sampled. `barFill` stays as the
          // fallback and is opaque on purpose: without a blur, `glassFill` is
          // just a window onto the list scrolling underneath.
          backgroundColor: hasBlur ? t.glassFill : t.barFill,
          // `boxShadow` rather than `elevation`: see the note in `Glass.tsx`.
          // An elevation shadow under a translucent bar shows *through* it.
          boxShadow: [{ offsetX: 0, offsetY: 8, blurRadius: 20, color: t.shadow }],
        },
      ]}
    >
      {/* Only when a blur will actually happen. A method-less BlurView would
          just paint another translucent layer over `barFill` — lighter, no
          depth, one more view. */}
      {hasBlur ? (
        <BlurView
          intensity={Platform.OS === 'android' ? 44 : 34}
          tint={t.blurTint}
          {...blurProps}
          style={[StyleSheet.absoluteFill, { borderRadius: radius.pill }]}
        />
      ) : null}
      <Grad
        colors={g.sheen}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
        pointerEvents="none"
        style={[styles.sheen, { borderRadius: radius.pill }]}
      />

      <View style={styles.row} onLayout={onLayout}>
        {/* The sliding pill, behind the icons. */}
        {tabWidth > 0 ? (
          <Animated.View
            pointerEvents="none"
            style={[
              styles.pill,
              {
                width: tabWidth - 10,
                borderRadius: radius.pill,
                transform: [
                  {
                    translateX: slide.interpolate({
                      inputRange: [0, Math.max(1, tabCount - 1)],
                      outputRange: [5, (tabCount - 1) * tabWidth + 5],
                    }),
                  },
                ],
              },
            ]}
          >
            <Grad
              colors={g.aurora}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 1 }}
              style={[StyleSheet.absoluteFill, { borderRadius: radius.pill }]}
            />
          </Animated.View>
        ) : null}

        {state.routes.map((route, index) => {
          const { options } = descriptors[route.key];
          const focused = state.index === index;
          const label =
            typeof options.tabBarLabel === 'string' ? options.tabBarLabel : route.name;

          return (
            <Tab
              key={route.key}
              focused={focused}
              label={label}
              // The icon comes from the navigator's own `tabBarIcon`, so adding
              // a tab needs no change here. Colour is forced: on the gradient
              // pill the icon must be `onBrand`, which the screen cannot know.
              icon={options.tabBarIcon?.({
                focused,
                color: focused ? t.onBrand : t.textFaint,
                size: 22,
              })}
              labelStyle={[
                type.caption,
                { color: focused ? t.onBrand : t.textFaint },
              ]}
              onPress={() => {
                const event = navigation.emit({
                  type: 'tabPress',
                  target: route.key,
                  canPreventDefault: true,
                });
                if (focused || event.defaultPrevented) return;
                if (Platform.OS !== 'web') {
                  void Haptics.selectionAsync().catch(() => {});
                }
                navigation.navigate(route.name);
              }}
            />
          );
        })}
      </View>
    </Animated.View>
  );
};

/**
 * One tab. The icon lifts when it becomes active and the label fades in under it.
 *
 * The lift is 2px — enough to feel, not enough to see as movement. Combined with
 * the pill sliding in underneath, it reads as the pill picking the icon up.
 */
const Tab: React.FC<{
  focused: boolean;
  label: string;
  icon?: React.ReactNode;
  labelStyle: any;
  onPress: () => void;
}> = ({ focused, label, icon, labelStyle, onPress }) => {
  const active = useAnimatedValue(focused ? 1 : 0);

  useEffect(() => {
    Animated.spring(active, {
      toValue: focused ? 1 : 0,
      tension: 240,
      friction: 20,
      useNativeDriver: true,
    }).start();
  }, [active, focused]);

  return (
    <Pressable
      onPress={onPress}
      style={styles.tab}
      accessibilityRole="tab"
      accessibilityState={{ selected: focused }}
      accessibilityLabel={label}
      // A generous target: the bar is 64px tall but the icon is 22px, and a
      // floating bar is reached with a thumb at an angle.
      hitSlop={10}
    >
      <Animated.View
        style={{
          alignItems: 'center',
          transform: [
            { translateY: active.interpolate({ inputRange: [0, 1], outputRange: [0, -2] }) },
            { scale: active.interpolate({ inputRange: [0, 1], outputRange: [1, 1.06] }) },
          ],
        }}
      >
        {icon}
        {/* Mounted always, opacity-animated: mounting on focus would shift the
            icon as the text takes up space. */}
        <Animated.Text
          numberOfLines={1}
          style={[labelStyle, styles.label, { opacity: active }]}
        >
          {label}
        </Animated.Text>
      </Animated.View>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: BAR_HEIGHT,
    borderWidth: StyleSheet.hairlineWidth * 2,
    overflow: 'hidden',
  },
  sheen: { position: 'absolute', left: 0, right: 0, top: 0, height: '55%' },
  row: { flex: 1, flexDirection: 'row', alignItems: 'center' },
  pill: { position: 'absolute', top: 6, bottom: 6, left: 0, overflow: 'hidden' },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', height: '100%' },
  label: { marginTop: 2 },
});

export default TabBar;
