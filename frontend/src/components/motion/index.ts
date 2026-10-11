/**
 * The motion and material kit. Four primitives, one import.
 *
 * Everything new in the UI is built from these, which is the point: the look is
 * consistent because there is one place that knows what glass is and one place
 * that knows how things enter.
 */

export { Aurora, type AuroraProps } from './Aurora';
export { Glass, type GlassProps } from './Glass';
export { Reveal, Pressable3D, type RevealProps, type Pressable3DProps } from './Reveal';
export { ThemeToggle, ThemeChoice, type ThemeToggleProps } from './ThemeToggle';
export { useAnimatedValue } from './useAnimatedValue';
export {
  BlurTargetProvider,
  BlurBackdrop,
  useBlurProps,
  useBlurTarget,
  BLUR_METHOD,
} from './BlurTarget';
