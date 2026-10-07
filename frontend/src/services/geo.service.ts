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
}

export const geoService = new GeoService();
