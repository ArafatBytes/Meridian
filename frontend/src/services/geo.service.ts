import apiService from './api.service';
import type { GeoResolution } from '../types/contracts/geo';

/**
 * Place resolution: text in, coordinates plus a method out.
 *
 * All the judgment lives on the server — the gazetteer, the fuzzy matching, the
 * LLM fallback and the decision to refuse. This file only carries the answer
 * across, for the same reason `risk.service.ts` does no decay arithmetic: one
 * implementation, and a phone is not the place for it.
 */

/** Wire shape — snake_case, as the endpoint sends it. */
interface GeoResolutionWire {
  lat: number;
  lon: number;
  radius_m: number;
  resolved_name: string;
  method: GeoResolution['method'];
  confidence: number;
  admin_area: string | null;
}

interface ResolveResponseWire {
  query: string;
  resolution: GeoResolutionWire;
}

/** One candidate from the Nominatim proxy. Carries no judgement — see `search()`. */
export interface NominatimPlace {
  display_name: string | null;
  lat: number;
  lon: number;
  type?: string | null;
}

interface GeoSearchWire {
  query: string;
  results: NominatimPlace[];
}

interface GeoReverseWire {
  lat: number;
  lon: number;
  display_name: string | null;
  address: Record<string, unknown>;
}

export interface ResolveResult {
  /**
   * The query this answer belongs to.
   *
   * Echoed by the server because resolution is asynchronous: a slow answer for
   * an earlier query must not overwrite a later one on screen. The caller
   * compares this against what is currently in the box before rendering.
   */
  query: string;
  resolution: GeoResolution;
}

function toResolution(wire: GeoResolutionWire): GeoResolution {
  return {
    lat: wire.lat,
    lon: wire.lon,
    radiusM: wire.radius_m,
    resolvedName: wire.resolved_name,
    method: wire.method,
    confidence: wire.confidence,
    adminArea: wire.admin_area ?? null,
  };
}

/** What we report when the request itself fails, as opposed to the place being unknown. */
function unresolved(query: string): ResolveResult {
  return {
    query,
    resolution: {
      lat: 0,
      lon: 0,
      radiusM: 1,
      resolvedName: query,
      method: 'unresolved',
      confidence: 0,
      adminArea: null,
    },
  };
}

class GeoService {
  /**
   * Resolve a place reference.
   *
   * Never throws. A network failure and an unknown place both surface as
   * `method: 'unresolved'`, because the distinction does not change what the map
   * does — it draws no pin either way — and a thrown error inside a search box
   * handler is how you get an unhandled rejection on a phone.
   */
  async resolve(text: string): Promise<ResolveResult> {
    const query = text.trim();
    if (!query) {
      return unresolved(query);
    }

    try {
      // `apiService.post` declares ApiResponse<T> but hands back the body
      // verbatim, and this endpoint returns an unwrapped object. Same double cast
      // as risk.service.ts, and said out loud for the same reason.
      const body = (await apiService.post<ResolveResponseWire>('/geo/resolve', {
        text: query,
      })) as unknown as ResolveResponseWire | { data?: ResolveResponseWire };

      const payload: ResolveResponseWire | undefined =
        body && 'resolution' in body ? body : body?.data;

      if (!payload?.resolution) {
        return unresolved(query);
      }

      return {
        query: payload.query ?? query,
        resolution: toResolution(payload.resolution),
      };
    } catch {
      return unresolved(query);
    }
  }

  /**
   * Forward geocode through **our** proxy, not Nominatim directly. Defect 10.
   *
   * Four screens used to call `nominatim.openstreetmap.org` straight from the device with
   * React Native's default `User-Agent` and no caching. That breaks Nominatim's usage
   * policy (it requires a genuine identifying agent and at most one request per second),
   * spends the per-IP rate limit separately on every phone, and is invisible to the
   * server. The proxy gives it one agent we own and one shared Redis cache.
   *
   * Returns `[]` rather than throwing when the geocoder is unreachable: the caller's job
   * is to offer suggestions, and no suggestions is a usable state while an exception is
   * not.
   *
   * ⚠️ **Not a replacement for `resolve()`.** That is the guarded path — the Dhaka
   * gazetteer, with the "discarded, never guessed" invariant. This answers *everything*,
   * which is why D03's lesson applies: a tier that always answers must not be able to
   * overturn a deliberate refusal. Use `resolve()` for the map's search box; use this for
   * address lookup and reverse geocoding.
   */
  async search(query: string): Promise<NominatimPlace[]> {
    if (!query.trim()) return [];
    try {
      const body = (await apiService.get<GeoSearchWire>(
        `/geo/search?q=${encodeURIComponent(query)}`,
      )) as unknown as GeoSearchWire | { data?: GeoSearchWire };
      const payload = body && 'results' in body ? body : body?.data;
      return payload?.results ?? [];
    } catch {
      return [];
    }
  }

  /**
   * Reverse geocode through the proxy. Returns null when there is no address for the point.
   *
   * A missing address is a state the reporting screen can render ("drop a pin here
   * anyway"), so it is not an error.
   */
  async reverse(lat: number, lon: number): Promise<string | null> {
    try {
      const body = (await apiService.get<GeoReverseWire>(
        `/geo/reverse?lat=${lat}&lon=${lon}`,
      )) as unknown as GeoReverseWire | { data?: GeoReverseWire };
      const payload = body && 'display_name' in body ? body : body?.data;
      return payload?.display_name ?? null;
    } catch {
      return null;
    }
  }
}

export const geoService = new GeoService();
