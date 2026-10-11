/**
 * Layout numbers that both the navigator and the screens need.
 *
 * ## Why this is its own file
 *
 * `TAB_BAR_CLEARANCE` started out exported from `MainNavigator`, which put four
 * require cycles in the bundle:
 *
 * ```
 * MainNavigator -> HomeScreen   -> MainNavigator
 * MainNavigator -> MapNavigator -> MapScreen -> MainNavigator
 * MainNavigator -> ReportsNavigator -> ReportsScreen -> MainNavigator
 * MainNavigator -> ProfileNavigator -> ProfileScreen -> MainNavigator
 * ```
 *
 * The navigator imports its screens, and a screen that imports a constant back
 * from the navigator closes the loop. Metro allows it and warns, and the warning
 * is worth heeding rather than silencing: whichever module in the cycle is
 * evaluated second sees the first one half-initialised. A `const` number
 * happened to be safe here, but the next thing added to that file might not be,
 * and the failure would be an `undefined` at import time with a stack trace
 * pointing somewhere unhelpful.
 *
 * A leaf module with no imports of its own cannot take part in a cycle.
 */

/**
 * Bottom padding a scrolling screen needs so its last item clears the tab bar.
 *
 * The bar is 64 tall and floats 10 above the safe-area inset, plus 18 of
 * breathing room. Add `insets.bottom` at the call site — this constant
 * deliberately does not, because it cannot read the inset.
 *
 * Only needed by a screen at the **root** of a tab. The bar slides out of the
 * way on a pushed screen (see `TabBar`), so adding this there is dead space.
 */
export const TAB_BAR_CLEARANCE = 92;

/** The bar's own height, which `TabBar` uses to animate itself off-screen. */
export const TAB_BAR_HEIGHT = 64;
