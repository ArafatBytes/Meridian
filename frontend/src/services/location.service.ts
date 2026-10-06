import * as Location from 'expo-location';
import { LocationData, Coordinates } from '../types';
import {
  LOCATION_UPDATE_INTERVAL,
  LOCATION_DISTANCE_FILTER,
} from '../constants';

class LocationService {
  private watchSubscription: Location.LocationSubscription | null = null;

  async requestPermission(): Promise<boolean> {
    const { status: existingStatus } =
      await Location.getForegroundPermissionsAsync();

    if (existingStatus === 'granted') {
      return true;
    }

    const { status } = await Location.requestForegroundPermissionsAsync();
    return status === 'granted';
  }

  async requestBackgroundPermission(): Promise<boolean> {
    const { status: existingStatus } =
      await Location.getBackgroundPermissionsAsync();

    if (existingStatus === 'granted') {
      return true;
    }

    const { status } = await Location.requestBackgroundPermissionsAsync();
    return status === 'granted';
  }

  async getCurrentLocation(): Promise<LocationData> {
    try {
      // First try to get the last known location (fast, cached)
      const lastKnown = await Location.getLastKnownPositionAsync({
        maxAge: 60000, // Use cached location if less than 1 minute old
        requiredAccuracy: 100, // Accept accuracy within 100 meters
      });

      // If we have a recent cached location, use it immediately
      if (lastKnown) {
        const location: LocationData = {
          latitude: lastKnown.coords.latitude,
          longitude: lastKnown.coords.longitude,
          accuracy: lastKnown.coords.accuracy ?? undefined,
          altitude: lastKnown.coords.altitude ?? undefined,
          heading: lastKnown.coords.heading ?? undefined,
          speed: lastKnown.coords.speed ?? undefined,
          timestamp: lastKnown.timestamp,
        };
        return location;
      }

      // If no cached location, get fresh location with optimized settings
      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced, // Balanced is faster than High
      });

      const location: LocationData = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy ?? undefined,
        altitude: position.coords.altitude ?? undefined,
        heading: position.coords.heading ?? undefined,
        speed: position.coords.speed ?? undefined,
        timestamp: position.timestamp,
      };

      return location;
    } catch (error) {
      throw new Error(
        `Location error: ${error instanceof Error ? error.message : 'Unknown error'}`,
      );
    }
  }

  async watchPosition(
    onLocationUpdate: (location: LocationData) => void,
    onError?: (error: Error) => void,
  ): Promise<void> {
    try {
      this.watchSubscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.High,
          timeInterval: LOCATION_UPDATE_INTERVAL,
          distanceInterval: LOCATION_DISTANCE_FILTER,
        },
        (position: Location.LocationObject) => {
          const location: LocationData = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy ?? undefined,
            altitude: position.coords.altitude ?? undefined,
            heading: position.coords.heading ?? undefined,
            speed: position.coords.speed ?? undefined,
            timestamp: position.timestamp,
          };
          onLocationUpdate(location);
        },
      );
    } catch (error) {
      if (onError) {
        onError(
          new Error(
            `Location error: ${error instanceof Error ? error.message : 'Unknown error'}`,
          ),
        );
      }
    }
  }

  stopWatching(): void {
    if (this.watchSubscription) {
      this.watchSubscription.remove();
      this.watchSubscription = null;
    }
  }

  calculateDistance(from: Coordinates, to: Coordinates): number {
    // Haversine formula to calculate distance between two coordinates
    const R = 6371e3; // Earth's radius in meters
    const φ1 = (from.latitude * Math.PI) / 180;
    const φ2 = (to.latitude * Math.PI) / 180;
    const Δφ = ((to.latitude - from.latitude) * Math.PI) / 180;
    const Δλ = ((to.longitude - from.longitude) * Math.PI) / 180;

    const a =
      Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
      Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c; // Distance in meters
  }

  formatDistance(meters: number): string {
    if (meters < 1000) {
      return `${Math.round(meters)} m`;
    }
    return `${(meters / 1000).toFixed(1)} km`;
  }

  isLocationInRadius(
    center: Coordinates,
    point: Coordinates,
    radiusInMeters: number,
  ): boolean {
    const distance = this.calculateDistance(center, point);
    return distance <= radiusInMeters;
  }
}

export default new LocationService();
