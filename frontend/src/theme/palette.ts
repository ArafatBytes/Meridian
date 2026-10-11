/**
 * Meridian's colour system. **The one file to edit to change how the app looks.**
 *
 * Two complete palettes — light and dark — behind one shape, so a component
 * reads `t.text` and never knows which mode it is in.
 *
 * ## Why it stopped being purple
 *
 * The inherited palette was indigo `#6366F1` → violet → pink `#EC4899`. Purple
 * reads as *consumer social app*, and three problems followed from it:
 *
 * 1. **It fought the data.** Risk severity is drawn in green → amber → red, and
 *    a violet-to-pink chrome puts pink next to red on the same screen. The two
 *    most important colours in a safety product were competing with decoration.
 * 2. **It had no cool anchor.** Everything was warm-ish, so there was no calm
 *    base for an interface whose job is to be trusted when something is wrong.
 * 3. **It was everywhere.** The gradient ran across headers, buttons, the tab
 *    bar and the loading screen identically, so nothing could be emphasised.
 *
 * ## What replaced it: Aurora
 *
 * A cool spectrum — **cyan → sky → azure** — with warm colours reserved
 * exclusively for state. Three things fall out of that:
 *
 * * Cool chrome, warm data. Amber and red mean *something is happening*
 *   wherever they appear, because nothing decorative is warm.
 * * It stays legible against a map. Dhaka's OSM tiles are beige and grey, and a
 *   cyan-to-azure overlay separates from them where violet muddied.
 * * It has depth without hue drift. The three stops differ in luminance as much
 *   as in hue, so a gradient reads as light falling on a surface rather than as
 *   two colours meeting.
 *
 * ## The accent is deliberately not in the gradient
 *
 * `accent` is coral. It appears on exactly one thing per screen — the action
 * that matters most — and because it is the only warm chrome colour, it cannot
 * be missed. A second accent would make it decoration.
 */

export type Mode = 'light' | 'dark';

/** The full token set. Both palettes implement this exactly. */
export interface Palette {
  mode: Mode;

  // ---- Brand ----------------------------------------------------------
  /** The three Aurora stops, cool → cooler. Use for gradients, not fills. */
  auroraStops: readonly [string, string, string];
  /** The single brand colour for a solid fill: the middle Aurora stop. */
  brand: string;
  brandSoft: string;
  brandStrong: string;
  /** Coral. One per screen, on the primary action. Never decorative. */
  accent: string;
  accentSoft: string;

  // ---- Surfaces -------------------------------------------------------
  /** The page. */
  bg: string;
  /** A raised panel that is NOT glass — lists, sheets. */
  surface: string;
  /** One step further forward. */
  surfaceRaised: string;
  /** Fill behind a `Glass` component, under the blur. */
  glassFill: string;
  glassBorder: string;
  /**
   * Fill for a glass surface that has **no backdrop to blur** — the floating
   * tab bar, which is a sibling of the navigator and so has no screen's
   * backdrop in scope (see `BlurTarget.tsx`).
   *
   * **Opaque**, and it has to be. Translucency only reads as material when
   * there is a blur behind it; without one it is simply a window, and the list
   * scrolling underneath reads straight through the tab labels. A translucent
   * panel with nothing blurring is a bug wearing a style's clothes.
   *
   * The bar still reads as glass, because the light edge and the top sheen are
   * what carry that — see the four conditions in `Glass`. This only replaces the
   * one of the four that cannot work here.
   */
  barFill: string;
  /** Scrims behind modals. */
  scrim: string;

  // ---- Text -----------------------------------------------------------
  text: string;
  textSoft: string;
  textFaint: string;
  /** Text that sits on the Aurora gradient or on `brand`. */
  onBrand: string;

  // ---- Lines ----------------------------------------------------------
  line: string;
  lineSoft: string;

  // ---- State ----------------------------------------------------------
  // The only warm colours in the system. Severity bands read against these.
  ok: string;
  warn: string;
  danger: string;
  info: string;
  okSoft: string;
  warnSoft: string;
  dangerSoft: string;

  // ---- Elevation ------------------------------------------------------
  shadow: string;
  /** Blur tint for `expo-blur`, which needs to know the mode. */
  blurTint: 'light' | 'dark';
}

/**
 * Light. Not white — `#F6F9FC` with a cool cast.
 *
 * Pure white next to a cyan gradient looks like a missing background; a
 * faintly cool ground makes the glass panels read as floating above something.
 */
export const light: Palette = {
  mode: 'light',

  auroraStops: ['#22D3EE', '#0EA5E9', '#2563EB'],
  brand: '#0EA5E9',
  brandSoft: '#E0F2FE',
  brandStrong: '#0369A1',
  accent: '#FB7185',
  accentSoft: '#FFE4E6',

  bg: '#F6F9FC',
  surface: '#FFFFFF',
  surfaceRaised: '#FFFFFF',
  glassFill: 'rgba(255, 255, 255, 0.62)',
  glassBorder: 'rgba(255, 255, 255, 0.85)',
  barFill: '#FBFCFE',
  scrim: 'rgba(15, 23, 42, 0.45)',

  text: '#0F172A',
  textSoft: '#475569',
  textFaint: '#94A3B8',
  onBrand: '#FFFFFF',

  line: 'rgba(15, 23, 42, 0.10)',
  lineSoft: 'rgba(15, 23, 42, 0.06)',

  ok: '#059669',
  warn: '#D97706',
  danger: '#DC2626',
  info: '#0284C7',
  okSoft: '#D1FAE5',
  warnSoft: '#FEF3C7',
  dangerSoft: '#FEE2E2',

  shadow: 'rgba(15, 23, 42, 0.14)',
  blurTint: 'light',
};

/**
 * Dark. Navy, not black.
 *
 * `#070B14` rather than `#000`: OLED black makes a glass panel's edge vanish,
 * and the whole look depends on being able to see the edge of the glass. A navy
 * ground also keeps the cyan gradient from glowing like neon.
 */
export const dark: Palette = {
  mode: 'dark',

  // Brightened a step: the same stops that read as confident on white look
  // muddy on navy.
  auroraStops: ['#67E8F9', '#38BDF8', '#3B82F6'],
  brand: '#38BDF8',
  brandSoft: 'rgba(56, 189, 248, 0.16)',
  brandStrong: '#7DD3FC',
  accent: '#FDA4AF',
  accentSoft: 'rgba(253, 164, 175, 0.16)',

  bg: '#070B14',
  surface: '#0F172A',
  surfaceRaised: '#172033',
  glassFill: 'rgba(23, 32, 51, 0.58)',
  glassBorder: 'rgba(148, 163, 184, 0.22)',
  barFill: '#111A2B',
  scrim: 'rgba(2, 6, 14, 0.66)',

  text: '#F1F5F9',
  textSoft: '#94A3B8',
  textFaint: '#64748B',
  onBrand: '#04121F',

  line: 'rgba(148, 163, 184, 0.18)',
  lineSoft: 'rgba(148, 163, 184, 0.10)',

  // Lightened for contrast against navy. The same hues, so a user switching
  // modes does not have to relearn what amber means.
  ok: '#34D399',
  warn: '#FBBF24',
  danger: '#FB7185',
  info: '#38BDF8',
  okSoft: 'rgba(52, 211, 153, 0.16)',
  warnSoft: 'rgba(251, 191, 36, 0.16)',
  dangerSoft: 'rgba(251, 113, 133, 0.16)',

  shadow: 'rgba(0, 0, 0, 0.55)',
  blurTint: 'dark',
};

export const palettes: Record<Mode, Palette> = { light, dark };

/**
 * Named gradients, derived from the palette so they switch with the mode.
 *
 * `aurora` is the brand. The rest exist so that a gradient never has to be
 * written inline — an inline array is how a fourth shade of blue gets invented
 * at one in the morning.
 */
export function gradientsFor(t: Palette) {
  return {
    /** The brand. Headers, the active tab pill, hero surfaces. */
    aurora: t.auroraStops,
    /** Two-stop, for small fills where three stops turn to mud. */
    auroraShort: [t.auroraStops[0], t.auroraStops[2]] as const,
    /** The one warm gradient: the SOS button and nothing else. */
    alarm: ['#FB7185', '#E11D48'] as const,
    /** Fades a photo or map into the page so text stays readable on top. */
    scrimDown:
      t.mode === 'light'
        ? (['rgba(246,249,252,0)', 'rgba(246,249,252,0.92)'] as const)
        : (['rgba(7,11,20,0)', 'rgba(7,11,20,0.94)'] as const),
    /** Barely-there sheen on a glass card. Sells the material. */
    sheen:
      t.mode === 'light'
        ? (['rgba(255,255,255,0.55)', 'rgba(255,255,255,0)'] as const)
        : (['rgba(255,255,255,0.10)', 'rgba(255,255,255,0)'] as const),
  };
}

export type Gradients = ReturnType<typeof gradientsFor>;
