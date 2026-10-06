import { create } from 'zustand';
import { LocationData } from '../types';
import { LocationService } from '../services';

interface LocationState {
  currentLocation: LocationData | null;
  isTracking: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  setCurrentLocation: (location: LocationData) => void;
  setTracking: (isTracking: boolean) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  getCurrentLocation: () => Promise<void>;
  startTracking: (onUpdate: (location: LocationData) => void) => Promise<void>;
  stopTracking: () => void;
  clearError: () => void;
}

export const useLocationStore = create<LocationState>(set => ({
  currentLocation: null,
  isTracking: false,
  isLoading: false,
  error: null,

  setCurrentLocation: location => set({ currentLocation: location }),

  setTracking: isTracking => set({ isTracking }),

  setLoading: isLoading => set({ isLoading }),

  setError: error => set({ error }),

  clearError: () => set({ error: null }),

  getCurrentLocation: async () => {
    try {
      set({ isLoading: true, error: null });
      const hasPermission = await LocationService.requestPermission();

      if (!hasPermission) {
        throw new Error('Location permission denied');
      }

      const location = await LocationService.getCurrentLocation();
      set({
        currentLocation: location,
        isLoading: false,
      });
    } catch (error: any) {
      set({
        error: error.message || 'Failed to get location',
        isLoading: false,
      });
      throw error;
    }
  },

  startTracking: async onUpdate => {
    try {
      const hasPermission = await LocationService.requestPermission();

      if (!hasPermission) {
        throw new Error('Location permission denied');
      }

      LocationService.watchPosition(
        location => {
          set({ currentLocation: location });
          onUpdate(location);
        },
        error => {
          set({ error: error.message });
        },
      );

      set({ isTracking: true });
    } catch (error: any) {
      set({
        error: error.message || 'Failed to start tracking',
        isTracking: false,
      });
      throw error;
    }
  },

  stopTracking: () => {
    LocationService.stopWatching();
    set({ isTracking: false });
  },
}));
