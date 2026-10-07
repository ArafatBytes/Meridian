import apiService from './api.service';
import type { RiskFlag, SourceRef, TimeProfile } from '../types/contracts/risk';

/**
 * Risk flags from the backend.
 *
 * The map's only source of risk data. Risk flags are deliberately **not** read
 * through Supabase the way crime reports are: `risk_flags` has row-level security
 * on with no policies, so the anon key cannot see it at all. Decay, time-of-day
 * modulation (D02) and the forward-looking view (D09) are arithmetic that must
 * have one implementation, and a phone is not the place for it.
 */

/** A map viewport, in the shape `react-native-maps` uses. */
export interface MapRegion {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
}

export interface RiskFlagsResult {
  /** The instant the server evaluated the surface at. */
  asOf: string;
  flags: RiskFlag[];
}

/**
 * The widest box the endpoint will accept, in degrees.
 *
 * Mirrors `MAX_BBOX_SPAN_DEGREES` in `backend/app/api/v1/endpoints/risk.py`. A
 * zoomed-right-out map would otherwise ask for a box the server rejects with a
 * 422, and an empty map is indistinguishable from "no flags here".
 */
const MAX_SPAN_DEGREES = 2.0;

/**
 * The smallest area a flag fetch covers, in degrees — about 39 km.
 *
 * `MapScreen` drives the map with a controlled `region` prop and has no
 * region-change handler, so flags are fetched once per recentre rather than on
 * every pan. Asking for the visible box alone would mean that zooming in near
 * Shahbagh silently drops the flag in Uttara, and the map would look correct while
 * being incomplete.
 *
 * Over-fetching a city's worth of flags costs one request of a few hundred rows,
 * which is the right trade until D04 adds pull-to-refresh and makes loading an
 * explicit, visible event.
 */
const RISK_FETCH_MIN_SPAN_DEGREES = 0.35;

/** What the wire actually carries. snake_case, and dates as ISO strings. */
interface RiskFlagWire {
  flag_id: string;
  event_key: string;
  kind: RiskFlag['kind'];
  status: RiskFlag['status'];
  lat: number;
  lon: number;
  radius_m: number;
  severity_0: number;
  severity_now: number;
  half_life_hours: number;
  observed_at: string;
  expires_at: string;
  source_count: number;
  sources: {
    source_id: string;
    url: string;
    published_at: string | null;
    title: string | null;
    snippet: string | null;
  }[];
  mobility_statement: string;
  time_profile: TimeProfile | null;
  valid_from: string | null;
  valid_to: string | null;
}

interface RiskFlagsResponseWire {
  as_of: string;
  count: number;
  flags: RiskFlagWire[];
}

function toSourceRef(wire: RiskFlagWire['sources'][number]): SourceRef {
  return {
    sourceId: wire.source_id,
    url: wire.url,
    publishedAt: wire.published_at,
    title: wire.title,
    snippet: wire.snippet,
  };
}

/**
 * Wire shape to contract shape.
 *
 * The conversion lives here, once, so that no screen ever handles a
 * `mobility_statement` with an underscore in it. Doing it per-component is how
 * two spellings of the same field end up in the codebase.
 */
function toRiskFlag(wire: RiskFlagWire): RiskFlag {
  return {
    flagId: wire.flag_id,
    eventKey: wire.event_key,
    kind: wire.kind,
    status: wire.status,
    lat: wire.lat,
    lon: wire.lon,
    radiusM: wire.radius_m,
    severity0: wire.severity_0,
    severityNow: wire.severity_now,
    halfLifeHours: wire.half_life_hours,
    observedAt: wire.observed_at,
    expiresAt: wire.expires_at,
    sourceCount: wire.source_count,
    sources: (wire.sources ?? []).map(toSourceRef),
    mobilityStatement: wire.mobility_statement,
    timeProfile: wire.time_profile,
    validFrom: wire.valid_from,
    validTo: wire.valid_to,
  };
}

/**
 * A map region as the `bbox` query parameter the endpoint expects.
 *
 * **Order is `west,south,east,north`** — longitude first. That is the OGC and
 * GeoJSON convention and what PostGIS uses, and it is the reverse of how
 * `MapRegion` reads. The swap happens here rather than at each call site.
 *
 * The span is clamped at both ends. Above, because at low zoom a region can cover
 * several degrees and the server refuses it. Below, by `minSpanDegrees`, because
 * fetching exactly the visible box means a flag two streets outside it does not
 * exist until the user happens to pan there — and this screen does not reload on
 * pan yet (see `RISK_FETCH_MIN_SPAN_DEGREES`).
 */
export function regionToBbox(
  region: MapRegion,
  minSpanDegrees = 0,
): string {
  const clamp = (delta: number) =>
    Math.min(Math.max(Math.abs(delta), minSpanDegrees), MAX_SPAN_DEGREES);
  const latSpan = clamp(region.latitudeDelta);
  const lonSpan = clamp(region.longitudeDelta);

  const south = region.latitude - latSpan / 2;
  const north = region.latitude + latSpan / 2;
  const west = region.longitude - lonSpan / 2;
  const east = region.longitude + lonSpan / 2;

  // Six decimal places is about 11 cm. More is noise that only lengthens the URL.
  const round = (n: number) => Number(n.toFixed(6));
  return [round(west), round(south), round(east), round(north)].join(',');
}

/**
 * The last Live Risk Agent run, from `GET /ingestion/status` (D04).
 *
 * `mode: 'replay'` means the backend is serving the captured offline replay
 * (`RISK_SURFACE_IMPL=seeded`) and there is no run to report.
 */
export interface IngestionStatus {
  mode: 'live' | 'replay';
  lastRun: {
    startedAt: string;
    finishedAt: string | null;
    status: 'running' | 'ok' | 'partial' | 'failed';
    documentsRead: number;
    flagsPublished: number;
  } | null;
}

interface IngestionStatusWire {
  mode: 'live' | 'replay';
  last_run: {
    started_at: string;
    finished_at: string | null;
    status: 'running' | 'ok' | 'partial' | 'failed';
    documents_read: number;
    flags_published: number;
  } | null;
}

class RiskService {
  async getIngestionStatus(): Promise<IngestionStatus> {
    // Same unwrapped-body situation as getFlagsInRegion below.
    const wire = (await apiService.get<IngestionStatusWire>(
      '/ingestion/status',
    )) as unknown as IngestionStatusWire;
    const run = wire.last_run;
    return {
      mode: wire.mode,
      lastRun: run && {
        startedAt: run.started_at,
        finishedAt: run.finished_at,
        status: run.status,
        documentsRead: run.documents_read,
        flagsPublished: run.flags_published,
      },
    };
  }

  /** Ask the backend to read the news now. Returns once the run is accepted, not done. */
  async runIngestion(): Promise<void> {
    await apiService.post('/ingestion/run');
  }

  /**
   * Live risk flags inside a map region.
   *
   * `asOf` is accepted from D01 even though the server treats every instant the
   * same until D02 — it is what D02's time control and D09's forward view both
   * drive, and threading it now means neither sprint has to touch this signature.
   */
  async getFlagsInRegion(
    region: MapRegion,
    asOf?: Date,
  ): Promise<RiskFlagsResult> {
    const params = new URLSearchParams({
      bbox: regionToBbox(region, RISK_FETCH_MIN_SPAN_DEGREES),
    });
    if (asOf) {
      params.set('as_of', asOf.toISOString());
    }

    // `apiService.get` declares ApiResponse<T> but returns the response body
    // verbatim, and these endpoints return an unwrapped object. The double cast
    // says so out loud instead of pretending the declared type is accurate.
    const body = (await apiService.get<RiskFlagsResponseWire>(
      `/risk/flags?${params.toString()}`,
    )) as unknown as RiskFlagsResponseWire | { data?: RiskFlagsResponseWire };

    const payload: RiskFlagsResponseWire | undefined =
      'flags' in body ? body : body.data;

    if (!payload || !Array.isArray(payload.flags)) {
      return { asOf: asOf?.toISOString() ?? new Date().toISOString(), flags: [] };
    }

    return {
      asOf: payload.as_of,
      flags: payload.flags.map(toRiskFlag),
    };
  }
}

export const riskService = new RiskService();
export default riskService;
