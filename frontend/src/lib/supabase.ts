/**
 * Supabase client — the single instance used by the whole app.
 *
 * This file was missing from git until S01: the root `.gitignore` had a bare
 * `lib/` entry (meant for Python build artifacts) which also matched
 * `frontend/src/lib/`, so the client was never committed and a clean clone
 * could not build. Both the ignore rule and this file are now fixed. See
 * PROGRESS.md S01.
 */

// Must be the first import. Hermes' built-in URL is incomplete, and
// supabase-js builds request URLs with it — without this polyfill you get
// opaque "Network request failed" errors instead of real responses.
import 'react-native-url-polyfill/auto';

import { createClient } from '@supabase/supabase-js';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState, Platform } from 'react-native';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Fail at startup with an actionable message. The alternative is a client
  // that constructs fine and then fails every call with a 401.
  throw new Error(
    'Supabase is not configured.\n\n' +
      'Copy frontend/.env.example to frontend/.env, fill in:\n' +
      '  EXPO_PUBLIC_SUPABASE_URL\n' +
      '  EXPO_PUBLIC_SUPABASE_ANON_KEY\n\n' +
      'then restart Metro with `npx expo start --clear`.\n' +
      'EXPO_PUBLIC_* values are inlined at bundle time, so a running dev ' +
      'server will keep serving the old ones.\n\n' +
      'Setup guide: backend/migrations/supabase/README.md',
  );
}

const isWeb = Platform.OS === 'web';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    // AsyncStorage, deliberately — NOT expo-secure-store.
    //
    // SecureStore caps a single value at 2048 bytes. A Supabase session
    // (access token + refresh token + serialised user) regularly exceeds that,
    // and the write fails *silently*, so the user appears logged in until the
    // app restarts and the session is gone.
    //
    // The app separately mirrors the access token into SecureStore via
    // auth.service.ts for the backend API client; that value is small enough.
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    // Native apps have no URL fragment to parse. On web, the OAuth/magic-link
    // redirect does land in the URL, so let the client read it.
    detectSessionInUrl: isWeb,
  },
});

/**
 * React Native has no window-focus event, so supabase-js cannot tell on its
 * own when to run its refresh timer. Without this, a session can expire while
 * the app is backgrounded and the first call after resuming fails with a 401.
 */
if (!isWeb) {
  AppState.addEventListener('change', state => {
    if (state === 'active') {
      supabase.auth.startAutoRefresh();
    } else {
      supabase.auth.stopAutoRefresh();
    }
  });
}
