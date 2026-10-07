/**
 * Jest setup — runs before the test framework is installed.
 *
 * `src/lib/supabase.ts` throws at import time when EXPO_PUBLIC_SUPABASE_URL or
 * EXPO_PUBLIC_SUPABASE_ANON_KEY is missing. That is deliberate: a misconfigured
 * app should fail loudly at startup rather than 401 on every request. But it
 * means any test importing a module that transitively reaches the Supabase
 * client needs these present.
 *
 * These are placeholders. No test should make a real network call — anything
 * that needs Supabase behaviour mocks the client.
 */
process.env.EXPO_PUBLIC_SUPABASE_URL ??= 'https://test-placeholder.supabase.co';
process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ??= 'test-placeholder-anon-key';
process.env.EXPO_PUBLIC_API_BASE_URL ??= 'http://127.0.0.1:8000/api/v1';

// AsyncStorage is a native module with no JS fallback, and the Supabase client
// uses it for session persistence. Anything importing src/lib/supabase.ts
// therefore reaches it. This is the mock the package ships for exactly this.
jest.mock(
  '@react-native-async-storage/async-storage',
  () => require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);
