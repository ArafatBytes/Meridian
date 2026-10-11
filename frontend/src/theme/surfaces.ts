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
