/**
 * Glass as a *style fragment*, for stylesheets that cannot use the `Glass`
 * component.
 *
 * ## Why both exist
 *
 * `components/motion/Glass` is the real thing: a blur layer, a tinted fill, a
 * light edge and a top sheen, composed from four stacked views. It is what a
 * hero surface should be.
 *
 * It is also four views and, on Android, a per-frame GPU cost. A screen like
 * Reports or Emergency Contacts is a list of twelve cards, and twelve blurs
 * scrolling at once drops frames on a budget handset — which is the note in
 * `Glass` about `blur={false}`, taken one step further. These screens also build
 * their cards inside a `StyleSheet.create`, where a component cannot go without
 * restructuring JSX that works.
 *
 * So the fill, the edge and the radius are available as a fragment to spread:
 *
 * ```ts
 * card: { ...glassSurface(t), padding: spacing.md },
 * ```
 *
 * What that loses is the blur and the sheen. What it keeps is most of what makes
 * the material read as material — a translucent fill over the Aurora field, and
 * a light edge that gives the panel thickness. **It only works over something.**
 * Spread over a flat `t.bg` it is a slightly lighter rectangle, so a screen using
 * it has to put `<Aurora>` behind its content. That is the one rule.
 *
 * ## Where each is used
 *
 * * `Glass` — the screen header, a single hero card, a modal, the tab bar, the
 *   route sheet. One or two per screen, where the blur is seen and worth it.
 * * `glassSurface` — list rows, form fields, grids. Many per screen.
 */

import { StyleSheet, type ViewStyle } from 'react-native';

import type { Palette } from './palette';
import { radius } from './type';

/**
 * How far off the page something sits. Four levels, and nothing in between.
 *
 * ## Why not `elevation`
 *
 * Android's `elevation` renders a view's shadow into the same region as the
 * view and then draws the view on top. With an opaque background you never see
 * it. With `glassFill` — 62% white in light mode, 58% navy in dark — you see
 * the remaining 38% or 42% of a shadow smeared across the *inside* of the
 * panel. That is the grey film that was on every glass card in the app, and
 * tuning the number does not fix it: it is 38% of whatever you pick.
 *
 * `boxShadow` is a Fabric style prop (RN 0.86, new architecture is on here)
 * that draws outside the border box on both platforms, like CSS. One
 * declaration, no `Platform.select`, and nothing behind the fill.
 *
 * ## Why levels rather than numbers
 *
 * There were 26 shadow declarations across ten files, each with its own
 * `shadowOpacity` between 0.1 and 0.3 — and on Android every one of them was
 * ignored, because `elevation` takes no opacity. So the two platforms did not
 * agree on a single card, and no two cards agreed with each other. Four named
 * levels is few enough to hold in your head and one place to tune.
 *
 * The colour is `t.shadow`, which carries its own alpha and flips with the mode
 * — `rgba(15,23,42,0.14)` on light, `rgba(0,0,0,0.55)` on navy, because a
 * shadow has to be much darker to read against a dark ground at all.
 */
const LIFTS = {
  /** A card at rest in a list. Just enough to separate it from the field. */
  1: { offsetY: 1, blur: 4 },
  /** A raised card, a button. The default. */
  2: { offsetY: 2, blur: 8 },
  /** A control floating over content — a search bar, a hint over a map. */
  3: { offsetY: 4, blur: 14 },
  /** A FAB, or a pane over a live map. The only level you should notice. */
  4: { offsetY: 8, blur: 24 },
} as const;

export type LiftLevel = keyof typeof LIFTS;

/**
 * A drop shadow at one of the four levels.
 *
 * `color` overrides `t.shadow`, for the one case that wants a coloured glow
 * rather than a shadow: a brand-filled primary button, where a neutral shadow
 * under a saturated fill reads as dirt.
 */
export function lift(t: Palette, level: LiftLevel = 2, color?: string): ViewStyle {
  const { offsetY, blur } = LIFTS[level];
  return {
    boxShadow: [{ offsetX: 0, offsetY, blurRadius: blur, color: color ?? t.shadow }],
  };
}

/**
 * A translucent panel: fill, hairline edge, card radius.
 *
 * The border is two hairlines rather than one. A single hairline on a 3x density
 * screen is a third of a pixel and effectively invisible against a translucent
 * fill, and the edge is what tells the eye the panel has thickness — drop it and
 * the whole thing reads as a lighter rectangle.
 */
export function glassSurface(t: Palette): ViewStyle {
  return {
    backgroundColor: t.glassFill,
    borderWidth: StyleSheet.hairlineWidth * 2,
    borderColor: t.glassBorder,
    borderRadius: radius.card,
  };
}

/**
 * A panel that is attached to an edge: same material, squarer corners.
 *
 * For a header or a footer that spans the screen. A 20pt radius on something
 * flush with the screen edge leaves two wedges of background in the corners,
 * which looks like a mistake rather than a choice.
 */
export function glassBar(t: Palette): ViewStyle {
  return {
    backgroundColor: t.glassFill,
    borderBottomWidth: StyleSheet.hairlineWidth * 2,
    borderBottomColor: t.glassBorder,
  };
}

/**
 * An inset well — a field, a read-only value, a code block.
 *
 * Deliberately *not* glass: it reads as recessed rather than raised, which is
 * what an input should do. Pairing a well inside a glass card is what gives a
 * form two legible levels.
 */
export function inset(t: Palette): ViewStyle {
  return {
    // `fillSoft`, not `lineSoft`. The latter is ink at 6%, so in light mode it
    // darkened the Aurora field behind the well instead of sitting on it as a
    // pale recess. See the note on `fillSoft` in `palette.ts`.
    backgroundColor: t.fillSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: t.line,
    borderRadius: radius.md,
  };
}
