/**
 * `useAnimatedValue` — one stable `Animated.Value` per component instance.
 *
 * ## Why this exists rather than `useRef(new Animated.Value(0)).current`
 *
 * That is the pattern in every React Native tutorial, and it has two problems
 * under React 19 and the React Compiler:
 *
 * 1. **It reads `.current` during render**, which `react-hooks/refs` flags. The
 *    rule is right in general — a value read during render that React does not
 *    track is how you get a component that will not update — and although it is
 *    harmless for an `Animated.Value` (the object identity never changes and the
 *    animation is driven natively), the warning is indistinguishable from the
 *    real bug, so it trains you to ignore the rule. There are already 55 of
 *    these in the inherited screens.
 * 2. **It allocates on every render.** `new Animated.Value(0)` is evaluated each
 *    time and then thrown away by `useRef`. Once per component it is nothing;
 *    in a list row that re-renders on scroll it is garbage for no reason.
 *
 * `useState` with a lazy initialiser fixes both: React calls the function once,
 * keeps the value, and nothing is read during render that React does not own.
 * The setter is discarded — the value is mutated by the animation driver, never
 * replaced, so there is no state update and no re-render. That is the whole
 * point: the animation runs on the native side and React is not involved after
 * the first frame.
 */

import { useState } from 'react';
import { Animated } from 'react-native';

/**
 * A stable animated value, created once.
 *
 * ```ts
 * const progress = useAnimatedValue(0);
 * useEffect(() => { Animated.timing(progress, { toValue: 1, ... }).start(); }, [progress]);
 * ```
 *
 * It is safe in a dependency array — the identity is stable for the life of the
 * component, so an effect listing it will not re-run.
 */
export function useAnimatedValue(initial: number): Animated.Value {
  // The initialiser is a function, so it runs on mount only.
  const [value] = useState(() => new Animated.Value(initial));
  return value;
}

export default useAnimatedValue;
