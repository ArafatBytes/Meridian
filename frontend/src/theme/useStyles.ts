/**
 * `useStyles` — the bridge from a module-level stylesheet to a themed one.
 *
 * ## The problem it solves
 *
 * Every inherited screen does this at module scope:
 *
 * ```ts
 * const styles = StyleSheet.create({ card: { backgroundColor: colors.white } });
 * ```
 *
 * which is evaluated once, when the module is imported, long before any React
 * tree exists. It therefore cannot see the theme, and that single fact is why
 * every un-migrated screen in this app is light-only — not a missing palette, a
 * stylesheet built at the wrong time.
 *
 * The fix is to make the sheet a function of the palette and call it from
 * inside the component:
 *
 * ```ts
 * const makeStyles = (t: Palette) => StyleSheet.create({
 *   card: { backgroundColor: t.surface },
 * });
 *
 * const Screen = () => {
 *   const styles = useStyles(makeStyles);
 *   // ...
 * };
 * ```
 *
 * ## Why a hook taking a factory, rather than a hook per file
 *
 * The first few migrated screens each grew their own four-line `useStyles`
 * wrapper. With twenty screens to convert that is twenty copies of the same
 * `useMemo`, and the copies are where the dependency array gets it wrong.
 *
 * Taking the factory as an argument also means a file's sub-components can each
 * call `useStyles(makeStyles)` directly instead of having `styles` threaded down
 * through their props — which matters, because the large screens in this app
 * have five or six small components sharing one sheet, and growing a `styles`
 * parameter on each is both noisy and the kind of change that quietly breaks
 * when one of them is forgotten.
 *
 * ## The memo is keyed on the factory as well as the mode
 *
 * `factory` must be a stable module-level function, which is how it is always
 * used — a factory defined inside a component would be a new identity every
 * render and `StyleSheet.create` would run on each one. It is in the dependency
 * array rather than omitted so that the memo is honest about what it depends on,
 * and so the lint rule does not have to be suppressed.
 */

import { useMemo } from 'react';

import { useTheme } from './ThemeProvider';
import type { Palette } from './palette';

export function useStyles<T>(factory: (t: Palette) => T): T {
  const { t } = useTheme();
  return useMemo(() => factory(t), [factory, t]);
}

export default useStyles;
