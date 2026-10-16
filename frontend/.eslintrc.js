/**
 * ESLint configuration.
 *
 * Previously `extends: '@react-native'`, but `@react-native/eslint-config` was
 * never installed, so every lint run died with "couldn't find the config
 * @react-native to extend from" -- which is why this codebase had never been
 * linted. Its first successful run surfaced the malware in babel.config.js
 * (nine `no-undef` errors for Node APIs that have no business in a Babel
 * config). See docs/SECURITY-INCIDENT-2026-10-07.md.
 *
 * `eslint-config-expo` is what the SDK pins (expo/bundledNativeModules.json).
 */
module.exports = {
  root: true,
  extends: 'expo',
  ignorePatterns: [
    'node_modules/',
    'android/',
    'ios/',
    '.expo/',
    'dist/',
    'web-build/',
    'coverage/',
    'eslint-report.json',
  ],
  rules: {
    // --- React Compiler rules, downgraded to warnings -----------------------
    //
    // eslint-config-expo 57 pulls eslint-plugin-react-hooks v6, which adds the
    // React Compiler rule set. On this codebase that produced 69 NEW errors
    // against code that predates the upgrade and works:
    //
    //   react-hooks/refs               60  (55 in LoadingScreen.tsx alone)
    //   react-hooks/immutability        6
    //   react-hooks/set-state-in-effect 3
    //
    // Every one was inspected. They are three idiomatic patterns, not bugs:
    //
    //   * `useRef(new Animated.Value(1)).current` -- the documented React
    //     Native animation idiom. Technically a ref read during render;
    //     harmless for an Animated.Value. The compiler-friendly form is
    //     `useMemo(() => new Animated.Value(1), [])`.
    //   * `useEffect(() => { fetchX(); }, [])` -- mount-only data fetch calling
    //     a function from the component body.
    //   * Syncing `currentLocation` into `region` state inside an effect, which
    //     is guarded by a `hasInitialized` flag.
    //
    // They are real code smells and they are worth fixing -- but as part of
    // S07/S08, where these screens get decomposed into feature folders and
    // hooks anyway. That is the commit where this is cheap and safe; doing it
    // now would mean hours of churn in animation and data-fetching code to
    // satisfy a linter that was not running yesterday.
    //
    // They stay visible as warnings inside the ratchet, which only goes down.
    // Delete these three lines when S08 lands.
    'react-hooks/refs': 'warn',
    'react-hooks/immutability': 'warn',
    'react-hooks/set-state-in-effect': 'warn',
  },
  overrides: [
    {
      // Jest globals are only in scope in test files and the setup file.
      // Declaring them repo-wide would mask a stray `jest.*` call in app code.
      // `**/*.test.js` is here for app.config.test.js: the thing it tests is a
      // Node config file, so its test is .js too, and without this every
      // `it`/`expect` in it is a no-undef error.
      files: [
        '**/*.test.ts',
        '**/*.test.tsx',
        '**/*.test.js',
        'jest.setup.js',
        'jest.config.js',
      ],
      env: { jest: true, node: true },
    },
    {
      // Config files run in Node, not in the app bundle.
      files: ['*.config.js', '.eslintrc.js', '.prettierrc.js'],
      env: { node: true },
    },
  ],
};
