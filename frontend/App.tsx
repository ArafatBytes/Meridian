/**
 * Meridian - Smart Safety Navigation App
 * @format
 */

import React, { useEffect } from 'react';
import { StatusBar, LogBox, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { RootNavigator } from './src/navigation';
// Registers the background geofence handler. A STATIC import, at the app root,
// on purpose: `TaskManager.defineTask` must have run by the time the OS delivers
// a boundary crossing, and on a headless wake-up the only thing that has run is
// this bundle's module scope. Behind a lazy import or a hook, zone alerts would
// work while the app was open and nowhere else — the one state they are not for.
import './src/features/geofence/task';
import { GuardianProvider } from './src/features/guardian/GuardianProvider';
import { refreshZonesIfEnabled } from './src/features/geofence/service';
import { NotificationService, LocationService } from './src/services';
import { registerCheckInCategory } from './src/features/journey/checkIn';
import { answerFromNotification } from './src/features/journey/answerFromNotification';
import {
  registerForAlerts,
  watchForegroundRegistration,
} from './src/features/alerts/register';
import { useAuthStore } from './src/store';
import { ThemeProvider, useTheme } from './src/theme/ThemeProvider';
import { useAppFonts } from './src/theme/fonts';

// Ignore specific warnings
LogBox.ignoreLogs([
  'Non-serializable values were found in the navigation state',
]);

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

/**
 * The status bar, following the theme.
 *
 * It was `barStyle="dark-content"` with a hard-coded `#FFFAFA` background, which
 * in dark mode is black icons on navy — unreadable, and the one piece of chrome
 * a user cannot work around. It has to live under `ThemeProvider` to read the
 * mode, hence a component of its own rather than a line in `App`.
 *
 * `translucent` stays on: content draws behind the bar, which is what makes the
 * Aurora field reach the top of the screen.
 */
const ThemedStatusBar: React.FC = () => {
  const { isDark } = useTheme();
  return (
    <StatusBar
      barStyle={isDark ? 'light-content' : 'dark-content'}
      backgroundColor="transparent"
      translucent
    />
  );
};

/**
 * What shows for the few hundred ms before the fonts resolve.
 *
 * A flat fill in the theme's background colour, and nothing else. Rendering the
 * real tree and letting text reflow when the faces land produces a visible
 * swap — every label jumps as metrics change — and a spinner for 300 ms reads as
 * a slow app. A ground-coloured hold reads as the app opening.
 *
 * It is the theme's `bg`, not white, so a dark-mode user never sees a white
 * flash on launch.
 */
const BootBackdrop: React.FC = () => {
  const { t } = useTheme();
  return <View style={[styles.fill, { backgroundColor: t.bg }]} />;
};

function App(): React.JSX.Element {
  const { initialize } = useAuthStore();
  // Loads Sora and Inter. `ready` also goes true on failure or after a timeout
  // — a typeface is never allowed to keep this app off the screen. See fonts.ts.
  const fonts = useAppFonts();

  useEffect(() => {
    // Initialize app services
    const initializeApp = async () => {
      try {
        // Initialize auth state
        await initialize();

        // B6a. Channels, permission, token, listeners.
        //
        // This was commented out with the note "disabled in Expo Go", which was
        // accurate and meant the whole push path had never run once. It is on
        // now, and it never throws: a device that refuses notification
        // permission still gets an app, and every failure is reported through
        // `NotificationService.diagnose()` on the Alerts screen instead.
        //
        // Expo Go genuinely cannot receive remote push on Android (removed in
        // SDK 53). `diagnose()` says so in those words rather than letting it
        // look like a server problem.
        await NotificationService.initialize();

        // JG2. The lock-screen answer, in two halves.
        //
        // The category is the set of action buttons Android draws under a
        // check-in; the handler is what posts the answer when one is pressed.
        // Both have to exist before any notification arrives, and neither can
        // live in a screen -- the whole point is that no screen is mounted when
        // somebody answers from a lock screen.
        //
        // Registered unconditionally, including where push is unavailable. A
        // category nobody sends to costs nothing, and a handler that never fires
        // costs less than discovering at JG3 that it was never wired.
        await registerCheckInCategory();
        NotificationService.onAlertTap(tap => {
          void answerFromNotification(tap);
        });

        // Request location permission
        await LocationService.requestPermission();

        // Register this install for alerts, with a coarse position if we have
        // one. Deliberately last: it needs both the push token and the location
        // permission above, and it must not block startup if either is refused
        // — `registerDevice` returns false rather than throwing.
        //
        // ⚠️ This is the ONLY place the server learns where a device is, which is
        // why alerts are "near where the app last had your location" and not
        // "near you". Background location is S17 and is not built.
        await registerForAlerts();

        // Re-register the risk zones the OS is watching. Flags decay, expire and
        // appear, so a region set from yesterday watches roads that are now
        // clear and ignores the one that is blocked today. No-ops when the user
        // has zone alerts switched off.
        await refreshZonesIfEnabled();
      } catch (error) {
        console.error('App initialization error:', error);
      }
    };

    initializeApp();

    // Re-register on every foreground, at most once every 30 s. This is what
    // keeps the server's idea of where this phone is inside the six-hour window
    // the dispatcher will act on -- the app has no background location, so the
    // last foreground is the only position there is.
    return watchForegroundRegistration();
  }, [initialize]);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        {/* Above everything that draws. `useTheme()` throws outside it, which is
            deliberate — a screen that silently falls back to light would be a
            dark-mode bug nobody notices. */}
        <ThemeProvider>
          <ThemedStatusBar />
          <QueryClientProvider client={queryClient}>
            {/* One SOS controller, one shake listener, one voice guard, for the
                whole app. Inside the providers so it can use them, and outside
                the navigator so a trigger works on whatever screen is showing.
                Also deliberately OUTSIDE the font gate below: shake and voice
                SOS are armed from the first frame, not from the first frame
                that has typography. */}
            <GuardianProvider>
              {fonts.ready ? <RootNavigator /> : <BootBackdrop />}
            </GuardianProvider>
          </QueryClientProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});

export default App;
