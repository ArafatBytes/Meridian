import apiService from './api.service';

export interface Location {
    latitude: number;
    longitude: number;
}

export interface RouteRequest {
    source: Location;
    destination: Location;
    avoid_high_crime_zones?: boolean;
}

export interface RouteSegment {
    latitude: number;
    longitude: number;
    crime_score: number;
}

export interface RouteResponse {
    route_id: string;
    path: RouteSegment[];
    distance_km: number;
    duration_minutes: number;
    safety_score: number;
    composite_score: number;
    crime_hotspots: Location[];
}

class RouteService {
    async calculateRoutes(request: RouteRequest): Promise<RouteResponse[]> {
        try {
            const response = await apiService.post<any>('/routes/calculate', request);

            // Handle raw array response (FastAPI default)
            if (Array.isArray(response)) {
                return response;
            }
            // Handle wrapped response (if Schema changed)
            if (response && response.data && Array.isArray(response.data)) {
                return response.data;
            }

            return [];
        } catch (error) {
            console.error('Error calculating routes:', error);
            throw error;
        }
    }

    async getSafestRoute(source: Location, destination: Location): Promise<RouteResponse | null> {
        try {
            const response = await apiService.get<RouteResponse>(
                `/routes/safest?source_lat=${source.latitude}&source_lng=${source.longitude}&dest_lat=${destination.latitude}&dest_lng=${destination.longitude}`
            );
            if (response.success && response.data) {
                return response.data;
            }
            return null;
        } catch (error) {
            console.error('Error getting safest route:', error);
            throw error;
        }
    }
}

export const routeService = new RouteService();
