/**
 * Jest configuration.
 *
 * The preset was `react-native`, which is wrong for an Expo app: it does not
 * mock Expo's native modules, so any test that transitively imports one dies
 * on `requireNativeModule`. The first symptom was
 * `react-native-gesture-handler/src/init.ts` throwing inside App.tsx.
 *
 * `jest-expo` is versioned in lockstep with the SDK (~54 here) because it mocks
 * that SDK's native surface. Bump it with the SDK, not independently.
 */
const expoPreset = require('jest-expo/jest-preset');

module.exports = {
  ...expoPreset,

  // MERGED, not replaced. Jest gives config keys precedence over the preset, so
  // assigning `setupFiles` or `transformIgnorePatterns` outright silently drops
  // jest-expo's own — which is what transpiles expo-modules-core. Overriding
  // transformIgnorePatterns with a hand-written list produced
  // "SyntaxError: Cannot use import statement outside a module" from
  // expo-modules-core/src/polyfill/dangerous-internal.ts.
  setupFiles: [...expoPreset.setupFiles, '<rootDir>/jest.setup.js'],

  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/**/*.d.ts', '!src/types/**'],
  testPathIgnorePatterns: ['/node_modules/', '/android/', '/ios/'],
};
