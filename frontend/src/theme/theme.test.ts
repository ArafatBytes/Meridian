/**
 * The theme is a single source of truth that screens index into by name, so a
 * missing key is a runtime `undefined` passed to a style prop — which React
 * Native silently ignores rather than erroring. That is how the dead
 * `theme/colors.ts` and `theme/darkTheme.ts` went unnoticed: two more colour
 * objects existed, neither was exported, and nothing complained.
 *
 * These assert the keys that screens actually reference, including the
 * compatibility aliases (`error`, `textPrimary`) that exist only because some
 * screens use a different name for the same value.
 */
import { colors, spacing, borderRadius, fontSize, shadows, typography } from './theme';

describe('colors', () => {
  // Referenced across the screens; `error` and `textPrimary` are aliases, and
  // the gray scale is used by empty states and placeholders.
  const required = [
    'primary', 'primaryLight', 'primaryDark',
    'secondary', 'background', 'surface', 'border',
    'text', 'textSecondary', 'textMuted', 'textPrimary',
    'success', 'warning', 'danger', 'error', 'info',
    'white', 'black', 'transparent',
    'gray400', 'gray500', 'shadowDark',
  ] as const;

  it.each(required)('defines %s', key => {
    expect(colors[key as keyof typeof colors]).toBeDefined();
  });

  it('keeps error and danger identical — they are aliases, not variants', () => {
    expect(colors.error).toBe(colors.danger);
  });

  it('keeps textPrimary and text identical', () => {
    expect(colors.textPrimary).toBe(colors.text);
  });
});

describe('scales', () => {
  it('spacing increases monotonically', () => {
    const order = [spacing.xs, spacing.sm, spacing.md, spacing.lg, spacing.xl, spacing.xxl];
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(new Set(order).size).toBe(order.length);
  });

  it('fontSize increases monotonically', () => {
    const order = [fontSize.xs, fontSize.sm, fontSize.md, fontSize.lg, fontSize.xl, fontSize.xxl];
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it('borderRadius.full is large enough to pill any realistic control', () => {
    expect(borderRadius.full).toBeGreaterThan(1000);
  });
});

describe('shadows', () => {
  // Both naming schemes are in use across screens; dropping either breaks
  // styles silently.
  it.each(['sm', 'md', 'lg', 'xl', 'small', 'medium', 'large'])(
    'defines %s with an elevation for Android',
    key => {
      const s = shadows[key as keyof typeof shadows];
      expect(s).toBeDefined();
      expect(s).toHaveProperty('elevation');
    },
  );
});

describe('typography', () => {
  it.each(['h1', 'h2', 'h3', 'h4', 'body', 'bodySmall', 'caption'])(
    '%s has a fontSize and a lineHeight',
    key => {
      const t = typography[key as keyof typeof typography];
      expect(t.fontSize).toBeGreaterThan(0);
      expect(t.lineHeight).toBeGreaterThanOrEqual(t.fontSize);
    },
  );
});
