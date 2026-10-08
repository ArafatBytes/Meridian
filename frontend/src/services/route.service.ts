import apiService from './api.service';

export interface Location {
    latitude: number;
    longitude: number;
}

export interface RouteRequest {
    source: Location;
    destination: Location;
    avoid_high_crime_zones?: boolean;
    /** Ceiling on `100 - safety_score`. Honoured since D06 — defect 6. */
    max_crime_score?: number;
    /** `driving` or `foot`. D06 added walking — see `RouteResponse.notes`. */
    profile?: 'driving' | 'foot';
}

export interface RouteSegment {
    latitude: number;
    longitude: number;
}

/**
 * A risk flag on this route, as the card and the map need it.
 *
 * `mobilityStatement` is server-framed prose. **Render it, never rebuild it** —
 * `app/policy/framing.py` is its only producer and an invariant test enforces that.
 */
export interface RouteFlag {
    flag_id: string;
    lat: number;
    lon: number;
    radius_m: number;
    mobility_statement: string;
    severity_now: number;
    status: 'confirmed' | 'unconfirmed' | string;
    source_count: number;
    /**
     * `chronic` is the historical police-statistics baseline, not an event: no headline,
     * still there next month, and scored at a reduced weight. Presenting it identically to
     * a fire reported an hour ago would be the permanent-area-label claim concept document
     * §9 rules out.
     */
    kind: string;
}

export interface RouteResponse {
    route_id: string;
    path: RouteSegment[];
    distance_km: number;
    /** OSRM's own duration. Was `distance / 30 km/h` before D06 — defect 7. */
    duration_minutes: number;
    /**
     * **0–100, higher is safer. The only scale.**
     *
     * D06 deleted the other two: `RouteSegment.crime_score` was 0–10 and this screen
     * rendered this field as `58.3% Safe`, so one quantity had three readings and none of
     * them agreed. That was defect 11. Render it as `NN/100`, never as a percentage.
     */
    safety_score: number;
    /** Ranking number: safety traded against duration, relative to the fastest option. */
    composite_score: number;
    /** The evidence behind the score, worst first. Drawn on the map, named in the card. */
    flags: RouteFlag[];
    /** One sentence of plain English, framed server-side. Beat 4. Render as-is. */
    explanation: string;
    /** `local` | `public-demo` | `straight-line`. Which engine answered. */
    engine: string;
    /** True when every route exceeded `max_crime_score` and the preference was dropped. */
    filter_relaxed: boolean;
    /** Caveats about how the answer was produced — walking estimates, degraded engine. */
    notes: string[];
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
