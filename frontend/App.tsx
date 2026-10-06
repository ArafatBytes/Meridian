/**
 * Meridian - Smart Safety Navigation App
 * @format
 */

import React, { useEffect } from 'react';
import { StatusBar, LogBox } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { RootNavigator } from './src/navigation';
import { NotificationService, LocationService } from './src/services';
import { useAuthStore } from './src/store';

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

function App(): React.JSX.Element {
  const { initialize } = useAuthStore();

  useEffect(() => {
    // Initialize app services
    const initializeApp = async () => {
      try {
        // Initialize auth state
        await initialize();

        // Initialize notification service (disabled in Expo Go)
        // await NotificationService.initialize();

        // Request location permission
        await LocationService.requestPermission();
      } catch (error) {
        console.error('App initialization error:', error);
      }
    };

    initializeApp();
  }, [initialize]);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar
            barStyle="dark-content"
            backgroundColor="#FFFAFA"
            translucent
          />
          <RootNavigator />
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

export default App;
