/**
 * The Android blur target: what `BlurView` samples, and where it may sit.
 *
 * ## Two bugs, one after the other
 *
 * **First**, every glass surface logged this on device:
 *
 * ```
 * WARN You have selected the "dimezisBlurView" blur method, but the `blurTarget`
 *      prop has not been configured. The blur view will fallback to "none".
 * ```
 *
 * Real. In expo-blur 57 the Android implementation no longer blurs "whatever is
 * behind me" — it blurs **one view you nominate**, by node handle. With no
 * target the native side silently falls back to `'none'`, so the panels were a
 * tinted fill with a border and no blur.
 *
 * **Second**, the obvious fix — one `BlurTargetView` wrapping the whole app so
 * any surface could find it — killed the app on launch:
 *
 * ```
 * tid: RenderThread  >>> com.Meridian.app <<<
 * signal 11 (SIGSEGV) — Cause: likely due to stack overflow
 * 512 total frames, every one: uirenderer::computeTransformImpl
 * ```
 *
 * Wrapping everything made each `BlurView` a **descendant of the view it
 * blurs**. Computing the blur walks the target's transform chain, that chain
 * runs back through the blur view, and the recursion never bottoms out: the
 * render thread overflows its stack and the process dies. Nothing reaches Metro,
 * because nothing is wrong with the JavaScript — which is exactly what makes it
 * worth writing down.
 *
 * ## The rule
 *
 * **A `BlurView` must be a sibling drawn *above* the target, never inside it.**
 *
 * Hence two pieces instead of one wrapper:
 *
 * ```jsx
 * <BlurTargetProvider>           // context only; renders no view at all
 *   <BlurBackdrop>               // the target: ONLY the backdrop goes in here
 *     …aurora blobs, or the map…
 *   </BlurBackdrop>
 *   …content, with Glass panels… // siblings, above — never children of it
 * </BlurTargetProvider>
 * ```
 *
 * The provider renders a fragment precisely so that it *cannot* become an
 * ancestor of both, which is what let the first attempt look reasonable.
 *
 * `Aurora` does this internally, so `<Aurora>…</Aurora>` gives its subtree real
 * blur for free. `MapScreen` does it around its `MapView`, which is a far better
 * thing to blur than any gradient.
 *
 * ## What gets no blur, and why that is fine
 *
 * A surface with no provider above it gets `{}` from `useBlurProps()` — no
 * method, no target, no warning, and the fill, edge and sheen carry it.
 *
 * ## The tab bar needed a second level of this
 *
 * The bar is rendered by `Tab.Navigator`'s `tabBar` prop, which puts it beside
 * the screen container rather than inside a screen — so no screen's `Aurora` is
 * in scope and the bar came out **opaque on Android**, which is defect #1 on the
 * UI list.
 *
 * It cannot simply be wrapped: anything that is an ancestor of both the bar and
 * the thing it blurs is the arrangement that overflowed the render thread above.
 * What works is two providers at two levels:
 *
 * ```
 * BlurTargetProvider                 (MainNavigator)  ← the bar reads THIS one
 *   Tab.Navigator
 *     ClaimBlurTarget                (per screen)     ← the bar blurs THIS view
 *       Screen
 *         Aurora → BlurTargetProvider + BlurBackdrop  ← Glass reads THIS one
 *           blobs
 *         Glass…
 *     TabBar → BlurView                               ← sibling, never inside
 * ```
 *
 * The inner provider shadows the outer one for everything inside a screen, so
 * `Glass` keeps blurring the blobs and needs no change. The bar sits outside
 * every screen, sees the outer provider, and blurs the focused screen whole.
 * Its `BlurView` is a sibling of that view, not a descendant, so the rule holds.
 *
 * `ClaimBlurTarget` only claims while its screen is **focused**. A tab navigator
 * keeps all four screens mounted, and without that the bar would blur whichever
 * one happened to mount last.
 *
 * ## Why `ready` exists
 *
 * React attaches refs bottom-up, so a `BlurView` runs `componentDidMount` —
 * where it resolves the node handle — **before** the target's ref is populated.
 * It finds `null`, and only looks again on an update; a `useRef` mutation does
 * not cause one. The blur would stay off forever.
 *
 * `onLayout` on the target fires after the commit that attached the ref, so
 * flipping `ready` there changes the context value, re-renders the consumers,
 * and `BlurView` resolves the target on that update.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Platform, StyleSheet, View, type ViewProps } from 'react-native';
import { BlurTargetView } from 'expo-blur';

import type { BlurMethod } from 'expo-blur';

interface BlurTargetValue {
  /** Stable ref object. `.current` is null until the tree has committed. */
  target: React.RefObject<View | null>;
  /** True once the node exists. Changing this is what re-renders consumers. */
  ready: boolean;
  markReady: () => void;
}

const BlurTargetContext = createContext<BlurTargetValue | null>(null);

/**
 * The blur method to ask for on Android.
 *
 * `dimezisBlurViewSdk31Plus` rather than `dimezisBlurView`: the plain variant
 * runs on every Android version but is slow on SDK 30 and below, where it
 * composites an offscreen buffer per frame. The Plus variant falls back to no
 * blur there instead, which is the right trade — an older phone gets the tinted
 * fill and keeps its frame rate, and everything from Android 12 up gets glass.
 */
export const BLUR_METHOD: BlurMethod = 'dimezisBlurViewSdk31Plus';

/**
 * Publishes a blur target to its subtree. **Renders no view.**
 *
 * That is deliberate and load-bearing: a provider that wrapped its children in a
 * view would be an ancestor of the target *and* of every blur view, which is the
 * arrangement that overflowed the render thread. A fragment cannot be.
 */
export const BlurTargetProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const target = useRef<View | null>(null);
  const [ready, setReady] = useState(false);

  const markReady = useCallback(() => {
    // Guarded: `onLayout` fires again on every resize and rotation.
    setReady(current => current || Boolean(target.current));
  }, []);

  const value = useMemo<BlurTargetValue>(
    () => ({ target, ready, markReady }),
    [ready, markReady],
  );

  return (
    <BlurTargetContext.Provider value={value}>{children}</BlurTargetContext.Provider>
  );
};

/**
 * The view that gets blurred. Put **only** the backdrop inside it.
 *
 * Anything in here is sampled by every `BlurView` in the subtree — and must not
 * itself contain one. Content belongs after it, as a sibling.
 */
export const BlurBackdrop: React.FC<ViewProps> = ({ children, style, ...rest }) => {
  const context = useContext(BlurTargetContext);

  if (!context) {
    throw new Error(
      'BlurBackdrop outside <BlurTargetProvider>. The provider publishes the ref ' +
        'that BlurViews resolve; see BlurTarget.tsx.',
    );
  }

  return (
    <BlurTargetView
      ref={context.target}
      onLayout={context.markReady}
      // React Native drops layout-only views on Android, and a collapsed target
      // has no native node to hand out a handle for.
      collapsable={false}
      style={style ?? StyleSheet.absoluteFill}
      {...rest}
    >
      {children}
    </BlurTargetView>
  );
};

/**
 * Publishes *this* view to the nearest **ancestor** provider while `active`.
 *
 * Unlike `BlurBackdrop`, which is the one backdrop its provider will ever have,
 * these compete: four of them sit under the provider in `MainNavigator` and the
 * focused one wins. That is the point — see the diagram at the top of the file.
 *
 * With no provider above, it renders a plain `View` rather than throwing.
 * `BlurBackdrop` throws because a backdrop with no provider is a mistake; this
 * one is used in the navigator, and nothing says a navigator must be wrapped.
 *
 * iOS also gets the plain `View`: the native effect view needs no target, so a
 * `BlurTargetView` there is a native view that does nothing.
 */
export const ClaimBlurTarget: React.FC<ViewProps & { active: boolean }> = ({
  active,
  children,
  style,
  ...rest
}) => {
  const context = useContext(BlurTargetContext);
  const node = useRef<View | null>(null);

  // A layout effect, not the ref callback. `BlurTargetView` takes a ref
  // *object*, not a callback, and in any case `active` flips long after mount —
  // when the user changes tab. Both the effect and `onLayout` end in
  // `markReady`, which is what re-renders the consumers so `BlurView` resolves
  // the handle on an update. See "Why `ready` exists" above.
  const claim = useCallback(() => {
    if (!context || !active || !node.current) return;
    context.target.current = node.current;
    context.markReady();
  }, [context, active]);

  useLayoutEffect(claim, [claim]);

  if (!context || Platform.OS === 'ios') {
    return (
      <View style={style} {...rest}>
        {children}
      </View>
    );
  }

  return (
    <BlurTargetView
      ref={node}
      onLayout={claim}
      // A layout-only view is dropped on Android and has no native node to hand
      // out a handle for. Same reason as `BlurBackdrop`.
      collapsable={false}
      style={style}
      {...rest}
    >
      {children}
    </BlurTargetView>
  );
};

/**
 * The blur target in scope, or `null` when there is none.
 *
 * A caller that gets `null` must not ask for a blur method — doing so is what
 * produced the fallback warning above.
 */
export function useBlurTarget(): React.RefObject<View | null> | null {
  const value = useContext(BlurTargetContext);
  // iOS blurs with a real UIVisualEffectView and needs no target at all.
  if (Platform.OS === 'ios') return null;
  if (!value || !value.ready) return null;
  return value.target;
}

/**
 * The props a `BlurView` needs on the current platform. One place, so a surface
 * cannot get half of the arrangement right.
 *
 * iOS: neither — the native effect view handles it.
 * Android with a target in scope: the method and the target together.
 * Android without one: nothing, so the component neither warns nor attempts a
 * blur it cannot perform.
 */
/**
 * Whether a real blur will happen here.
 *
 * A `BlurView` with no method still renders: on Android it paints a flat
 * translucent tint over whatever is beneath it. That is a *third* fill stacked
 * on the panel's own, it lightens the surface without adding any depth, and it
 * costs a native view. Surfaces use this to skip the component entirely when it
 * would do nothing, which also makes their own fill authoritative.
 */
export function useHasBlur(): boolean {
  const target = useBlurTarget();
  return Platform.OS === 'ios' || Boolean(target);
}

export function useBlurProps(): {
  blurMethod?: BlurMethod;
  blurTarget?: React.RefObject<View | null>;
} {
  const target = useBlurTarget();
  if (Platform.OS === 'ios') return {};
  if (!target) return {};
  return { blurMethod: BLUR_METHOD, blurTarget: target };
}

export default BlurTargetProvider;
