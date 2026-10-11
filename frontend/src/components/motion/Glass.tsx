/**
 * `Glass` — a pane of frosted material. The app's one container primitive.
 *
 * ## What makes glass read as glass, and what makes it read as a grey box
 *
 * Four things have to be true together. Drop any one and the effect collapses:
 *
 * 1. **Something has to be behind it.** A blur over a flat fill is a flat fill.
 *    This is why `Aurora` exists and why glass is only used over it, a map, or
 *    a photo — never over `t.bg`.
 * 2. **A tinted fill under the blur.** `expo-blur` alone is too transparent to
 *    carry text on Android. `t.glassFill` sits beneath it and does the
 *    legibility work; the blur does the depth.
 * 3. **A light edge.** The 1px `glassBorder` is what tells the eye there is a
 *    physical pane. Without it the panel has no thickness and the blur looks
 *    like a rendering artefact.
 * 4. **A sheen along the top.** A real pane catches light at its upper edge.
 *    `g.sheen` is a near-invisible vertical gradient over the top third — the
 *    single cheapest detail that moves this from "translucent rectangle" to
 *    "material", and the one most often left out.
 *
 * ## Android: the blur needs a nominated target
 *
 * In expo-blur 57 the Android implementation blurs **one view you name**, by
 * node handle, rather than whatever is behind it. Without a `blurTarget` it
 * falls back to no blur and warns — which is what every surface in this app was
 * doing until `BlurTarget.tsx` arrived. `useBlurProps()` supplies the method and
 * the target together, or neither, so a surface cannot get half of it right.
 *
 * The blur costs real GPU time per frame, which is why `Glass` takes
 * `blur={false}` for surfaces that are large, scrolling, or over a map — there,
 * the tinted fill plus the edge plus the sheen carries it, and the blur is the
 * part the user misses least.
 */

import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';

import { useTheme } from '../../theme/ThemeProvider';
import { useBlurProps, useHasBlur } from './BlurTarget';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

export interface GlassProps {
  children?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  /** Inner padding. Defaults to `space.lg`. Pass 0 for edge-to-edge content. */
  padding?: number;
  /**
   * Styles for the inner content box, which is where `padding` lives.
   *
   * This is the only way to reach the children's container: `style` lands on the
   * outer shell, which is `overflow: 'hidden'` and holds the blur and the sheen.
   * A `gap` or an `alignItems` set there would apply to the blur layer and not
   * to the content, which looks like the prop being ignored.
   */
  contentStyle?: StyleProp<ViewStyle>;
  /** Corner radius. Defaults to `radius.card` (20) — see the note in `type.ts`. */
  radius?: number;
  /**
   * Blur strength, 0–100. Defaults to 28.
   *
   * Above ~45 the backdrop turns to undifferentiated colour and the depth cue
   * is lost — it stops looking like glass and starts looking like fog.
   */
  intensity?: number;
  /**
   * Real blur, or fill-only.
   *
   * Set `false` for anything large, scrolling, or composited over a map. The
   * Android blur is a per-frame GPU cost and a list of twenty blurred rows will
   * drop frames on a budget device.
   */
  blur?: boolean;
  /** The top-edge sheen. On by default; off for very small chips. */
  sheen?: boolean;
  /** A drop shadow beneath the pane. Off for anything that moves. */
  elevated?: boolean;
}

export const Glass: React.FC<GlassProps> = ({
  children,
  style,
  padding,
  contentStyle,
  radius: radiusProp,
  intensity = 28,
  blur = true,
  sheen = true,
  elevated = false,
}) => {
  const { t, g, space, radius } = useTheme();
  const blurProps = useBlurProps();
  const hasBlur = useHasBlur();
  const r = radiusProp ?? radius.card;
  const pad = padding ?? space.lg;

  const shell: ViewStyle = {
    borderRadius: r,
    borderWidth: StyleSheet.hairlineWidth * 2,
    borderColor: t.glassBorder,
    // `hidden` so the blur and the sheen are clipped to the radius. Without it
    // the sheen paints a square corner over a rounded pane.
    overflow: 'hidden',
    backgroundColor: t.glassFill,
  };

  // `boxShadow`, not `elevation`, and that is the whole fix for the grey wash
  // that used to sit on every elevated pane in light mode.
  //
  // Android's `elevation` renders the shadow into the same region as the view
  // and then draws the view over it. With an opaque background you never see
  // it; with `glassFill` at 62% you see 38% of a shadow spread across the
  // *inside* of the card. That is what made the Guardian card on Home look
  // like it had a dark film over it, and no amount of tuning the number fixes
  // it -- 6 was already a compromise and it still showed.
  //
  // `boxShadow` is a Fabric style prop (RN 0.86, new architecture is on here)
  // that draws outside the border box on both platforms, like CSS. So one
  // declaration replaces the Platform.select, and the translucent fill has
  // nothing behind it but the backdrop.
  const shadow: ViewStyle = elevated
    ? {
        boxShadow: [
          { offsetX: 0, offsetY: 10, blurRadius: 22, color: t.shadow },
        ],
      }
    : {};

  return (
    <View style={[shell, shadow, style]}>
      {blur && hasBlur ? (
        <BlurView
          intensity={intensity}
          tint={t.blurTint}
          // Method + target, or neither. See `BlurTarget.tsx`.
          {...blurProps}
          style={StyleSheet.absoluteFill}
        />
      ) : null}

      {sheen ? (
        <Grad
          colors={g.sheen}
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
          pointerEvents="none"
          // The top third only. A sheen down the whole pane reads as a
          // gradient fill, not as light catching an edge.
          style={[styles.sheen, { borderTopLeftRadius: r, borderTopRightRadius: r }]}
        />
      ) : null}

      <View style={[{ padding: pad }, contentStyle]}>{children}</View>
    </View>
  );
};

const styles = StyleSheet.create({
  sheen: { position: 'absolute', left: 0, right: 0, top: 0, height: '34%' },
});

export default Glass;
