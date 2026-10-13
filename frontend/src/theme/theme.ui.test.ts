/**
 * Invariants for the design system. Three of these guard failures that are
 * invisible on screen until someone looks closely, which is why they are tests
 * and not review notes.
 *
 * The third one reads the source tree rather than importing anything, in the
 * same spirit as `features/alerts/channels.test.ts`: the property it checks is
 * about how the styles are *written*, so there is nothing to import.
 */

import fs from 'fs';
import path from 'path';

import { dark, gradientsFor, light, palettes } from './palette';
import { fontFamily, radius, space, type } from './type';

const SRC = path.join(__dirname, '..');

/** Every .ts/.tsx under src/, so a new screen is covered without being listed. */
function sourceFiles(dir: string = SRC): string[] {
  const found: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...sourceFiles(full));
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
      found.push(full);
    }
  }
  return found;
}

describe('the two palettes are interchangeable', () => {
  // A component reads `t.textFaint` without knowing the mode. A token present in
  // one palette and missing from the other is `undefined` passed to a style
  // prop, which React Native ignores silently — so the colour is simply absent
  // in one mode and nobody notices until a screenshot.
  it('define exactly the same tokens', () => {
    expect(Object.keys(light).sort()).toEqual(Object.keys(dark).sort());
  });

  it('give every token a value', () => {
    for (const [mode, palette] of Object.entries(palettes)) {
      for (const [token, value] of Object.entries(palette)) {
        expect(`${mode}.${token} = ${String(value)}`).not.toContain('undefined');
      }
    }
  });

  it('tell expo-blur which tint to use, per mode', () => {
    // `BlurView`'s tint cannot be derived from a hex colour, so it is a token.
    // Getting it wrong makes every glass surface in the app milky-white on navy.
    expect(light.blurTint).toBe('light');
    expect(dark.blurTint).toBe('dark');
  });

  it('keep the Aurora ramp three stops wide in both modes', () => {
    for (const palette of Object.values(palettes)) {
      expect(palette.auroraStops).toHaveLength(3);
      expect(new Set(palette.auroraStops).size).toBe(3);
    }
  });

  it('build every named gradient from at least two stops', () => {
    for (const palette of Object.values(palettes)) {
      for (const [name, stops] of Object.entries(gradientsFor(palette))) {
        expect(`${name}: ${stops.length} stops`).toBe(`${name}: ${stops.length} stops`);
        expect(stops.length).toBeGreaterThanOrEqual(2);
      }
    }
  });
});

describe('the type scale names fonts that are actually loaded', () => {
  // `fontFamily` is a string, and an unregistered one does not throw: Android
  // substitutes the default face without a warning. A typo here, or a weight
  // dropped from the loader, silently reverts the app to Roboto.
  const loader = fs.readFileSync(path.join(__dirname, 'fonts.ts'), 'utf8');

  it.each(Object.entries(fontFamily))('registers %s (%s)', (_role, family) => {
    expect(loader).toContain(family);
  });

  it('uses only those families across the whole scale', () => {
    const allowed = new Set<string>(Object.values(fontFamily));
    for (const [token, style] of Object.entries(type)) {
      expect(`${token}: ${style.fontFamily}`).toBe(`${token}: ${style.fontFamily}`);
      expect(allowed.has(style.fontFamily as string)).toBe(true);
    }
  });

  it('never pairs a family with a weight', () => {
    // See the test below for why. The scale is the one place this would be
    // easiest to reintroduce, because a display style "wants" to say bold.
    for (const style of Object.values(type)) {
      expect(style).not.toHaveProperty('fontWeight');
    }
  });

  it('gives every live number tabular figures', () => {
    // A meter or countdown set in proportional digits shifts sideways as the
    // digits change, which reads as a layout bug.
    for (const token of ['metric', 'metricSmall'] as const) {
      expect(type[token].fontVariant).toContain('tabular-nums');
    }
  });
});

describe('no style pairs fontFamily with fontWeight', () => {
  /**
   * The Android trap this exists for.
   *
   * React Native resolves a custom `fontFamily` on Android by asset name. Given
   * `fontFamily: 'Sora_700Bold'` *and* `fontWeight: 'bold'`, it goes looking for
   * a bold variant of that asset — `Sora_700Bold_bold` — which is not bundled.
   * What comes back is version-dependent: a synthetically emboldened face, or
   * the platform default.
   *
   * So the app would quietly render in Roboto on the one platform it is demoed
   * on, while every style still named the right font. The weight belongs in the
   * family name, which is why five font files are bundled rather than one.
   *
   * 105 of these pairings were removed when the fonts landed. This is what stops
   * the 106th.
   */
  const offenders: string[] = [];

  for (const file of sourceFiles()) {
    const source = fs.readFileSync(file, 'utf8');
    if (!source.includes('fontFamily')) continue;

    // Walk brace-delimited blocks and only judge the leaf ones — a style object.
    // An enclosing block holding several styles would otherwise look like a
    // single object that sets both.
    for (let i = 0; i < source.length; i += 1) {
      if (source[i] !== '{') continue;
      let depth = 0;
      let end = -1;
      for (let j = i; j < source.length; j += 1) {
        if (source[j] === '{') depth += 1;
        else if (source[j] === '}') {
          depth -= 1;
          if (depth === 0) {
            end = j;
            break;
          }
        }
      }
      if (end === -1) break;
      const body = source.slice(i + 1, end);
      if (body.includes('{')) continue; // not a leaf
      if (/\bfontFamily\s*:/.test(body) && /\bfontWeight\s*:/.test(body)) {
        const line = source.slice(0, i).split('\n').length;
        offenders.push(`${path.relative(SRC, file)}:${line}`);
      }
      i = end;
    }
  }

  it('anywhere under src/', () => {
    expect(offenders).toEqual([]);
  });
});

describe('there is one scale, not two', () => {
  /**
   * `theme.ts` says it at the top: **do not add keys here**. It is the floor
   * under the recolour — the legacy names, repointed at the Aurora palette so
   * that 26 un-migrated screens stopped being purple in a single edit.
   *
   * Twelve screens then went on using `spacing`, `borderRadius`, `fontSize` and
   * `typography` from it, which is why they sat oddly beside Home and Profile.
   * The numbers are genuinely different: `spacing.md` is 16 and `space.md` is
   * 12, `borderRadius.lg` is 16 and `radius.card` is 20, the old type scale ran
   * 12/14/16/18/20/24/32 and the real one runs 11/13/15/18/24/34. A screen
   * built from the first set cannot line up with one built from the second, and
   * no amount of recolouring hides it.
   *
   * `colors` is exempt and stays exported: `theme.test.ts` pins its keys,
   * because a missing one is a runtime `undefined` passed to a style prop,
   * which React Native ignores in silence.
   */
  const LEGACY = ['spacing', 'borderRadius', 'fontSize', 'fontWeight', 'typography', 'shadows'];
  const offenders: string[] = [];

  for (const file of sourceFiles()) {
    const rel = path.relative(SRC, file).split(path.sep).join('/');
    if (rel.startsWith('theme/')) continue;
    const source = fs.readFileSync(file, 'utf8');
    const imports = source.match(/import \{[^}]*\} from '(?:\.\.\/)+theme';/g) ?? [];
    for (const line of imports) {
      for (const name of LEGACY) {
        if (new RegExp(`\\b${name}\\b`).test(line)) offenders.push(`${rel}: ${name}`);
      }
    }
  }

  it('so nothing outside theme/ imports the legacy scale', () => {
    expect(offenders).toEqual([]);
  });
});

describe('the spacing and radius scales', () => {
  it('increase monotonically, with no duplicates', () => {
    const steps = [space.xs, space.sm, space.md, space.lg, space.xl, space.xxl, space.huge];
    expect(steps).toEqual([...steps].sort((a, b) => a - b));
    expect(new Set(steps).size).toBe(steps.length);
  });

  it('sit on a 4px grid', () => {
    for (const value of Object.values(space)) {
      expect(value % 4).toBe(0);
    }
  });

  it('give `pill` a radius large enough to fully round any control', () => {
    expect(radius.pill).toBeGreaterThan(radius.sheet * 10);
  });
});

describe('the Android blur contract', () => {
  /**
   * Two silent failures, both of which shipped once.
   *
   * In expo-blur 57 the Android implementation blurs **one nominated view**, by
   * node handle. A `BlurView` with a blur method but no `blurTarget` falls back
   * to no blur at all — it still renders, still tints, still looks like a panel,
   * and only a console warning says the material is not there. Every glass
   * surface in this app was in that state for a release.
   *
   * `experimentalBlurMethod` is the deprecated spelling of `blurMethod` and warns
   * separately. Both of these are caught by reading the source, because the
   * property is about how the component is *called*.
   *
   * The rule enforced here: anything rendering a `BlurView` gets its blur props
   * from `useBlurProps()`, which supplies the method and the target together or
   * neither.
   */
  const withBlurView: string[] = [];
  const deprecated: string[] = [];

  for (const file of sourceFiles()) {
    const source = fs.readFileSync(file, 'utf8');
    const rel = path.relative(SRC, file).split(path.sep).join('/');
    if (source.includes('experimentalBlurMethod') && !rel.includes('BlurTarget')) {
      deprecated.push(rel);
    }
    if (!source.includes('<BlurView')) continue;
    if (!source.includes('useBlurProps')) withBlurView.push(rel);
  }

  it('never uses the deprecated experimentalBlurMethod prop', () => {
    expect(deprecated).toEqual([]);
  });

  it('gets every BlurView its props from useBlurProps()', () => {
    expect(withBlurView).toEqual([]);
  });

  it('keeps the blur method one Android SDK 31+ chose deliberately', () => {
    // `dimezisBlurView` works on every version but composites an offscreen
    // buffer per frame on SDK 30 and below. The Plus variant degrades to no blur
    // there instead, which keeps an old handset's frame rate.
    const source = fs.readFileSync(
      path.join(SRC, 'components/motion/BlurTarget.tsx'),
      'utf8',
    );
    expect(source).toContain("'dimezisBlurViewSdk31Plus'");
  });
});

describe('every dialog is a Sheet', () => {
  /**
   * The defect this exists for.
   *
   * Eight modals, each a hand-rolled `<Modal transparent>` around a
   * `<View backgroundColor: t.surface>` with its own radius, its own padding and
   * its own scrim. None of them carried the glass material, so opening any
   * dialog dropped the user out of the new UI and into the old one — and the
   * SOS countdown, the single most important dialog in the product, was not
   * even themed: a white card with `#E53935` numerals, in a module-level
   * `StyleSheet` that could not see the mode.
   *
   * `components/motion/Sheet.tsx` is now the one modal container. Everything
   * else goes through it, so the material, the scrim and the two shapes are
   * decided in one place.
   *
   * ## The exceptions, and why each is one
   *
   * A full-screen *takeover* is not a dialog. Its backdrop is its own content —
   * a camera feed — and a translucent pane over that is a pane over the thing
   * the user is looking at.
   */
  const ALLOWED = [
    // The one place `Modal` is supposed to appear.
    'components/motion/Sheet.tsx',
    // The viewfinder. Full-screen over a live camera feed; see the note there.
    'components/SOSCameraModal.tsx',
  ];

  const offenders: string[] = [];

  for (const file of sourceFiles()) {
    const rel = path.relative(SRC, file).split(path.sep).join('/');
    if (ALLOWED.includes(rel)) continue;
    if (fs.readFileSync(file, 'utf8').includes('<Modal')) offenders.push(rel);
  }

  it('so no screen rolls its own', () => {
    expect(offenders).toEqual([]);
  });

  it('and the viewfinder is the only full-screen exception left', () => {
    // Narrower than the allow-list: SOSCameraModal may keep ONE `Modal`, the
    // camera. Its permission card is a dialog and went through `Sheet`.
    const camera = fs.readFileSync(
      path.join(SRC, 'components/SOSCameraModal.tsx'),
      'utf8',
    );
    expect(camera.split('<Modal').length - 1).toBe(1);
    expect(camera).toContain('<Sheet');
  });

  it('keeps the scrim in one place', () => {
    // Every dialog's backdrop used to be its own literal, which is how four of
    // them ended up at three different opacities. `Sheet` reads `t.scrim`, and
    // because nothing else renders a `Modal` (above), nothing else needs one.
    //
    // Scoped to styles *named* like a backdrop on purpose. A literal black at
    // 50% is also the right answer for dimming a photo — the avatar picker and
    // the "analysing" overlay both do it, over an image, inside the page — and
    // those are not scrims.
    const sheet = fs.readFileSync(path.join(SRC, 'components/motion/Sheet.tsx'), 'utf8');
    expect(sheet).toContain('t.scrim');

    const hardcoded: string[] = [];
    for (const file of sourceFiles()) {
      const rel = path.relative(SRC, file).split(path.sep).join('/');
      if (rel === 'components/motion/Sheet.tsx') continue;
      const source = fs.readFileSync(file, 'utf8');
      if (/(modalOverlay|backdrop|scrim)\s*:\s*\{[^}]*rgba\(0/i.test(source)) {
        hardcoded.push(rel);
      }
    }
    expect(hardcoded).toEqual([]);
  });
});

describe('a blur target is never transparent', () => {
  /**
   * The defect that made every blurred panel a grey smear.
   *
   * Dimezis blurs the nominated view by drawing **that view's own canvas** into
   * a bitmap. `Aurora` put the page colour on the wrapper and the blobs inside
   * the target, so the target drew three translucent blobs over nothing — and
   * the blur of nothing is not transparent, it is black.
   *
   * On screen: a charcoal gradient across the Guardian card, the Theme card and
   * the Log out card, heavy enough to swallow the text under it, while the four
   * quick actions on Home looked perfect. The only difference between them is
   * that the quick actions pass `blur={false}`, which skips the `BlurView`
   * entirely — so the one panel kind that never blurred was the one that looked
   * right, which is the opposite of what you would guess.
   *
   * The rule: whatever is handed out as a blur target paints an opaque
   * background. It is one line and it is invisible in review, because a
   * transparent view is a perfectly ordinary thing for everything else.
   */
  it('Aurora paints the page colour on the backdrop, not only above it', () => {
    const source = fs.readFileSync(
      path.join(SRC, 'components/motion/Aurora.tsx'),
      'utf8',
    );
    const open = source.indexOf('<BlurBackdrop');
    expect(open).toBeGreaterThan(-1);
    const tag = source.slice(open, source.indexOf('>', open));
    expect(tag).toContain('backgroundColor: t.bg');
  });

  it('and the screen wrapper the tab bar samples is opaque through its screen', () => {
    // `ClaimBlurTarget` wraps a whole screen, and a screen's first child is its
    // `Aurora` — which is opaque. So the target has something to draw without
    // a background of its own, and giving it one would paint over the screen.
    const navigator = fs.readFileSync(
      path.join(SRC, 'navigation/MainNavigator.tsx'),
      'utf8',
    );
    expect(navigator).toContain('<ClaimBlurTarget');
    expect(navigator).not.toContain('backgroundColor');
  });
});

describe('glassSurface is only used over something', () => {
  /**
   * `glassSurface` is a translucent fill. Over the Aurora field it reads as
   * material; over a flat `t.bg` it is a slightly lighter rectangle and the
   * screen just looks washed out. That is the one rule in `theme/surfaces.ts`
   * and it is invisible in review — the style compiles either way.
   *
   * A screen that spreads the fragment must therefore also render `<Aurora`.
   * MapScreen is the deliberate exception: its backdrop is the map itself, which
   * is a far better thing to be translucent over than any gradient.
   */
  const EXEMPT = ['screens/Map/MapScreen.tsx'];
  const offenders: string[] = [];

  for (const file of sourceFiles()) {
    const rel = path.relative(SRC, file).split(path.sep).join('/');
    if (EXEMPT.includes(rel)) continue;
    const source = fs.readFileSync(file, 'utf8');
    if (!source.includes('glassSurface(t)')) continue;
    if (!source.includes('<Aurora')) offenders.push(rel);
  }

  it('so every screen using it also renders an Aurora backdrop', () => {
    expect(offenders).toEqual([]);
  });
});

describe('the blur target is never an ancestor of a blur view', () => {
  /**
   * The arrangement that killed the app on launch.
   *
   * One `BlurTargetView` was wrapped around the whole app so any surface could
   * find a target. That made every `BlurView` a descendant of the view it
   * blurs; computing the blur walks the target's transform chain, the chain
   * runs back through the blur view, and the recursion never bottoms out:
   *
   *     tid: RenderThread  >>> com.Meridian.app <<<
   *     signal 11 (SIGSEGV) — Cause: likely due to stack overflow
   *     512 total frames, every one: uirenderer::computeTransformImpl
   *
   * The process dies before the first frame, and **nothing reaches Metro** —
   * the JavaScript is fine. There is no red screen and no stack trace in the
   * terminal, which is what makes it worth a test rather than a comment.
   *
   * The fix is structural: `BlurTargetProvider` publishes context and renders
   * no view, so it cannot be an ancestor of both. Only `BlurBackdrop` and
   * `ClaimBlurTarget` render the target, and `ClaimBlurTarget` is only ever
   * wrapped around a screen. These assertions hold that shape.
   */
  const source = fs.readFileSync(
    path.join(SRC, 'components/motion/BlurTarget.tsx'),
    'utf8',
  );

  const provider = source.slice(
    source.indexOf('export const BlurTargetProvider'),
    source.indexOf('export const BlurBackdrop'),
  );

  it('keeps BlurTargetView out of the provider, which must render no view', () => {
    expect(provider).not.toContain('<BlurTargetView');
  });

  it('renders only the context provider around its children', () => {
    expect(provider).toContain('<BlurTargetContext.Provider value={value}>{children}');
  });

  it('renders the target from BlurBackdrop and ClaimBlurTarget, and nowhere else', () => {
    const backdrop = source.slice(
      source.indexOf('export const BlurBackdrop'),
      source.indexOf('export const ClaimBlurTarget'),
    );
    const claim = source.slice(source.indexOf('export const ClaimBlurTarget'));
    expect(backdrop).toContain('<BlurTargetView');
    expect(claim).toContain('<BlurTargetView');
    // Those two, and only those two.
    expect(source.split('<BlurTargetView').length - 1).toBe(2);
  });

  it('is the only file in the app that mounts a target view', () => {
    // Stronger than counting inside one file: the crash came from a target
    // mounted somewhere convenient, and the two components here are the only
    // arrangements that have been reasoned about.
    const elsewhere = sourceFiles().filter(
      file =>
        !file.endsWith(`motion${path.sep}BlurTarget.tsx`) &&
        fs.readFileSync(file, 'utf8').includes('<BlurTargetView'),
    );
    expect(elsewhere.map(f => path.relative(SRC, f))).toEqual([]);
  });

  it('is not mounted around the app root', () => {
    // App.tsx wrapping the navigator is exactly how the first version shipped.
    const app = fs.readFileSync(path.join(SRC, '..', 'App.tsx'), 'utf8');
    expect(app).not.toContain('BlurTargetProvider');
  });

  /**
   * The tab bar's own arrangement, which is the second way to rebuild the crash.
   *
   * The bar is rendered by `Tab.Navigator`'s `tabBar` prop, so it lives *inside*
   * the navigator. Wrapping the navigator in a `ClaimBlurTarget` to give the bar
   * something to sample would therefore make the bar a descendant of the view it
   * blurs — the original bug with a new spelling. The wrapper has to go around
   * each screen instead, which leaves the bar a sibling.
   */
  it('claims each screen, never the navigator that holds the bar', () => {
    const navigator = fs.readFileSync(
      path.join(SRC, 'navigation/MainNavigator.tsx'),
      'utf8',
    );
    expect(navigator).toContain('<BlurTargetProvider>');
    expect(navigator).toContain('<ClaimBlurTarget');

    // The provider is allowed to be an ancestor of the bar: it renders no view.
    // The claim is not, so no `<Tab.Navigator` may appear inside one.
    const claimStart = navigator.indexOf('<ClaimBlurTarget');
    const claimEnd = navigator.indexOf('</ClaimBlurTarget>');
    expect(claimEnd).toBeGreaterThan(claimStart);
    expect(navigator.slice(claimStart, claimEnd)).not.toContain('Tab.Navigator');
  });
});

describe('the map follows the app theme, not the phone', () => {
  /**
   * `MapView` defaults its colour scheme to the device setting, so a map in a
   * light-themed app goes charcoal on a phone that is in dark mode. The prop
   * fixes it; the `key` is what makes a later theme change take, because
   * Android reads the scheme once at map creation and ignores every update.
   *
   * Both are invisible in review and invisible on a phone whose own setting
   * agrees with the app's, which is why they are a test.
   */
  const offenders: string[] = [];

  for (const file of sourceFiles()) {
    const rel = path.relative(SRC, file).split(path.sep).join('/');
    // The component that documents the rule, and the web stub that renders a
    // placeholder rather than a map.
    if (rel.startsWith('components/MapComponent')) continue;

    const source = fs.readFileSync(file, 'utf8');

    // The opening JSX tag. The leading `\s` is what separates it from
    // `useRef<MapView>(null)`, where the `>` follows the name immediately -- a
    // type argument, not an element, and the reason the first spelling of this
    // test failed on the very screen it was written for.
    for (const match of source.matchAll(/<MapView\s[^>]*>/g)) {
      const props = match[0];
      if (!props.includes('userInterfaceStyle={mode}')) offenders.push(`${rel}: no scheme`);
      if (!props.includes('key={mode}')) offenders.push(`${rel}: no remount`);
    }
  }

  it('so every MapView is passed the resolved mode, and remounts with it', () => {
    expect(offenders).toEqual([]);
  });
});

describe('text is never painted in its own background colour', () => {
  /**
   * The bug this catches shipped twice, in two components, from the same
   * mechanical edit: a selected chip was given `backgroundColor: t.brandStrong`
   * and its label `color: t.brandStrong`. The control still worked, still
   * animated, still passed every other test — and the selected option was simply
   * invisible. Both cases were found from a screenshot, which is the expensive
   * way to find them.
   *
   * It reads the style objects as written rather than rendering anything: the
   * pattern is a pair of adjacent keys in one `StyleSheet.create`, and that is
   * exactly what a source scan is good at.
   *
   * It is deliberately narrow — the `*Active`/`*Selected` convention this codebase
   * already follows — because a general contrast checker over every style would
   * need to resolve composition and inheritance, and would be mostly false
   * positives. This catches the specific mistake that has actually been made.
   */
  const FILL = /^(\s*)([A-Za-z0-9_]+(?:Active|Selected))\s*:\s*\{[^}]*backgroundColor:\s*t\.([A-Za-z0-9_]+)/gm;
  const TEXT_COLOUR = /color:\s*t\.([A-Za-z0-9_]+)/;

  it('does not give an active style the same token for fill and text', () => {
    const offenders: string[] = [];

    for (const file of sourceFiles()) {
      const source = fs.readFileSync(file, 'utf8');
      const rel = path.relative(SRC, file).split(path.sep).join('/');

      for (const match of source.matchAll(FILL)) {
        const [, , styleName, fillToken] = match;
        // The matching text style, by this codebase's own naming: `tabActive`
        // pairs with `tabTextActive`, `profileChipActive` with
        // `profileChipTextActive`.
        const base = styleName.replace(/(Active|Selected)$/, '');
        const suffix = styleName.endsWith('Active') ? 'Active' : 'Selected';
        const textName = `${base}Text${suffix}`;

        // Located by string search and matched with a regex LITERAL, never with a
        // pattern built from a template string. The first version of this used
        // `new RegExp(\`${textName}\\s*:...\`)` and silently matched nothing: the
        // backslashes did not survive into the file, so `\s` became a literal `s`
        // and the pattern read `tabTextActives*:s*...`. The test passed, found
        // nothing, and would have passed forever.
        const at = source.indexOf(`${textName}:`);
        if (at === -1) continue;
        const close = source.indexOf('}', at);
        if (close === -1) continue;
        const textToken = TEXT_COLOUR.exec(source.slice(at, close))?.[1];

        if (textToken === fillToken) {
          offenders.push(`${rel}: ${textName} is t.${textToken} on t.${fillToken}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it('uses onBrand for text sitting on a brand fill', () => {
    // The positive half: the two that were wrong are now right, so a revert shows
    // up here as well as in the rule above.
    const map = fs.readFileSync(path.join(SRC, 'screens', 'Map', 'MapScreen.tsx'), 'utf8');
    expect(map).toContain('profileChipTextActive: { color: t.onBrand }');

    const card = fs.readFileSync(
      path.join(SRC, 'components', 'RouteComparisonCard.tsx'),
      'utf8',
    );
    expect(card).toContain('tabTextActive: { color: t.onBrand }');
    // And the score beside it, which was `safetyColour` on the brand fill —
    // green-on-blue at 100/100.
    expect(card).toContain('active ? t.onBrand : safetyColour(candidate.safety_score, t)');
  });
});

describe('a floating card never covers the whole map', () => {
  /**
   * This is the second time the expanded route card has had to be made smaller,
   * which is why it is pinned rather than left to the next screenshot.
   *
   * The first fix stopped it overlapping the "Plan a route" card by measuring the
   * space below it — and the card then grew to fill exactly that space, which is
   * still a screen with no map on it. Clearing the control above you is not the
   * same as leaving the map visible, and a route card that hides the route is the
   * one thing this card must never do: the point of opening the details is to read
   * them against the line drawn on the map.
   *
   * Source-scanned because it is layout arithmetic in a screen component, with no
   * renderer here to measure. It checks the shape of the calculation, not the
   * pixels — the pixels are what a screenshot is for.
   */
  const map = fs.readFileSync(path.join(SRC, 'screens', 'Map', 'MapScreen.tsx'), 'utf8');

  it('subtracts a guaranteed band of map from the card’s cap', () => {
    expect(map).toContain('MIN_MAP_BAND');
    expect(map).toMatch(/routeCardSpace\s*-\s*MIN_MAP_BAND/);
  });

  it('measures the space below the search card rather than guessing a percentage', () => {
    // `searchHeight` is measured by the search card's own onLayout. A percentage
    // cannot know how tall it is, and it grows with the destination name.
    expect(map).toContain('searchTop + searchHeight');
    expect(map).toContain('maxHeight={routeCardMaxHeight}');
  });

  it('keeps a floor so the card can still show its own controls', () => {
    // Below roughly this the Start button and the tab row stop fitting, and a card
    // you cannot press Start on is worse than a thin strip of map.
    expect(map).toMatch(/Math\.max\(\s*\n?\s*(\/\/[^\n]*\n\s*)*260,/);
  });
});

describe('Glass is padded once, not twice', () => {
  /**
   * `Glass` puts `style` on the SHELL and its `padding` prop on the inner content
   * box. So a `padding` in the style is applied *in addition* to the prop, and the
   * children end up inset by the sum.
   *
   * On the map's route planner that was 32pt on every side instead of 16 — 64pt of
   * vertical whitespace, about a quarter of the card's height, spent on nothing.
   * It survived because nothing looks broken: the card is simply airier than
   * intended, and you only notice when you measure it against the map it is
   * covering.
   *
   * The glassmorphic migration introduced it, with a note reading "what stays is
   * the padding and the elevation" — true of the elevation, and already supplied
   * by the prop for the padding.
   */

  /** The body of `name: { ... }` inside a StyleSheet, brace-matched. */
  function styleBody(source: string, name: string): string | null {
    const start = source.indexOf(`    ${name}: {`);
    if (start === -1) return null;
    let depth = 0;
    for (let i = source.indexOf('{', start); i < source.length; i++) {
      if (source[i] === '{') depth++;
      else if (source[i] === '}') {
        depth--;
        if (depth === 0) return source.slice(start, i);
      }
    }
    return null;
  }

  it('never sets padding in a style handed to Glass', () => {
    const offenders: string[] = [];

    for (const file of sourceFiles()) {
      const source = fs.readFileSync(file, 'utf8');
      if (!source.includes('<Glass')) continue;
      const rel = path.relative(SRC, file).split(path.sep).join('/');

      for (const match of source.matchAll(/<Glass[^>]*style=\{\[?styles\.(\w+)/g)) {
        const body = styleBody(source, match[1]);
        // Brace-matched rather than regex-sliced to the next `},` — a one-line
        // style like `card: { marginHorizontal: space.lg },` would otherwise
        // swallow everything up to the next multi-line style and report its
        // padding. That false positive is why this helper exists.
        if (body && /\n\s*padding(Top|Bottom|Vertical)?\s*:/.test(body)) {
          offenders.push(`${rel}: styles.${match[1]} pads a Glass shell`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });
});
