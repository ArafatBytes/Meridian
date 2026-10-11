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
   * no view, so it cannot be an ancestor of both. Only `BlurBackdrop` renders
   * the target. These assertions hold that shape.
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

  it('renders the target only inside BlurBackdrop', () => {
    const backdrop = source.slice(source.indexOf('export const BlurBackdrop'));
    expect(backdrop).toContain('<BlurTargetView');
    // One place in the whole app renders it.
    expect(source.split('<BlurTargetView').length - 1).toBe(1);
  });

  it('is not mounted around the app root', () => {
    // App.tsx wrapping the navigator is exactly how the first version shipped.
    const app = fs.readFileSync(path.join(SRC, '..', 'App.tsx'), 'utf8');
    expect(app).not.toContain('BlurTargetProvider');
  });
});
