import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  View,
  StyleSheet,
  Pressable,
  TouchableOpacity,
  Text,
  Alert,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Keyboard,
  Platform,
  useWindowDimensions,
} from 'react-native';

import MapView, {
  Marker,
  MAP_PROVIDER,
  Polyline,
  Circle,
} from '../../components/MapComponent';
import { Ionicons } from '@expo/vector-icons';
import { CompositeNavigationProp } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { NavigationProp } from '@react-navigation/native';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface, lift } from '../../theme/surfaces';
import { Glass, Sheet } from '../../components/motion';
import { fontFamily, radius, space, type } from '../../theme/type';
import { useLocationStore } from '../../store';
import { DEFAULT_MAP_REGION } from '../../constants';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { CrimeCategory, MainTabParamList } from '../../types';
import { crimeCategoryLabel } from '../../types/contracts/crime';
import type { RiskFlag } from '../../types/contracts/risk';
import { routeService, RouteResponse, Location } from '../../services/route.service';
import { riskService, type IngestionStatus } from '../../services/risk.service';
import { geoService } from '../../services/geo.service';
import RiskFlagSheet, { riskBand } from '../../components/RiskFlagSheet';
import { RiskFlagMarker, isConfirmedFlag } from '../../components/RiskFlagMarker';
import RouteComparisonCard, { safetyColour } from '../../components/RouteComparisonCard';
import Dialog from '../../components/Dialog';
import { TAB_BAR_CLEARANCE } from '../../navigation/metrics';
import PlaceSearch from '../../components/PlaceSearch';
import { AS_OF_PRESETS, asOfSummary } from '../../features/risk/scheduled';
import type { GeoResolution } from '../../types/contracts/geo';
import type { CommunityCluster } from '../../types/contracts/community';
import { CommunityClusterMarker } from '../../components/CommunityClusterMarker';
import { useNavigation as useRouteFollow } from '../../features/navigation/useNavigation';
import { NavigationBanner } from '../../features/navigation/NavigationBanner';
import { FollowMarker } from '../../features/navigation/FollowMarker';
import { useJourney } from '../../features/journey/useJourney';
import { goesTo, startedAtLabel } from '../../features/journey/resume';

/**
 * A report as this screen draws it -- and every one of these belongs to the signed-in
 * user. B13 made reports private to their author: RLS on `crime_reports` is
 * `auth.uid() = user_id`, so there is no longer a query that returns anyone else's.
 *
 * `verified` is gone with the column. There was no honest way for this product to set
 * it -- the app cannot establish that an incident happened -- so the badge it fed was
 * unreachable UI. What a stranger sees instead is a `CommunityCluster`: several
 * independent people reporting in one small area, published as a count.
 */
interface CrimeReportData {
  id: string;
  category: CrimeCategory;
  title: string;
  description: string;
  incident_date_time: string;
  latitude: string;
  longitude: string;
  location_name: string | null;
  status: string;
}

// Defect 3. These keys were capitalised ('Theft') while the database enum and
// everything the app sends are lowercase ('theft'), so every lookup returned
// undefined and NO crime marker had a colour. Typed as Record<CrimeCategory, ...>
// against the single list in types/contracts/crime.ts, so a missing category is
// now a compile error rather than a grey pin.
const CRIME_COLORS: Record<CrimeCategory, string> = {
  theft: '#FF9800', // Orange
  robbery: '#F44336', // Red
  assault: '#E91E63', // Pink
  harassment: '#9C27B0', // Purple
  vandalism: '#607D8B', // Blue Grey
  burglary: '#FF5722', // Deep Orange
  fraud: '#2196F3', // Blue
  other: '#9E9E9E', // Grey
};

const CRIME_FALLBACK_COLOR = '#9E9E9E';

/**
 * Colour for a category that may not be one we know.
 *
 * Reports come straight out of Supabase with no validation step, so a row written
 * before an enum change can carry anything. Returning grey beats returning
 * undefined, which is how this bug looked for the whole of S01.
 */
const crimeColor = (category: string): string =>
  CRIME_COLORS[category as CrimeCategory] ?? CRIME_FALLBACK_COLOR;

// ---------------------------------------------------------------------------
// Risk flags
// ---------------------------------------------------------------------------

/**
 * Severity bands live in `components/RiskFlagSheet.tsx` and are imported, not
 * redeclared. The sheet and the pins must agree: a sheet saying "High" next to a pin
 * the map coloured "Severe" reads as a bug in the data rather than in the palette.
 *
 * They are keyed off `severityNow` from D02 onward — the decayed value — which is what
 * makes a fading flag visibly change colour as the time control moves.
 */

/**
 * The largest radius worth drawing as a circle, in metres.
 *
 * The chronic baseline layer comes from police *unit* statistics, so its flags have a
 * 20 km radius — DMP covers the whole of Dhaka. Drawing that is not information, it is
 * a tint over the entire viewport that makes every other flag harder to read while
 * implying a precision the data does not have. Above this, the pin is drawn alone and
 * the detail sheet states the radius in words.
 *
 * Kind-agnostic on purpose: the rule is "a circle bigger than the screen says nothing",
 * which is true whatever produced it.
 */
const MAX_DRAWN_RADIUS_M = 5000;

/*
 * Overlay geometry.
 *
 * The SOS button referred to below has since been removed from this screen — see
 * the comment at its old site in the JSX. The arrangement it forced is kept,
 * because the search card and the FAB column still have to stack correctly.
 *
 * Everything on top of the map is absolutely positioned, and three of those things
 * used to be placed by independent guesses that happened to collide:
 *
 *   - the time control sat at `insets.bottom + space.huge * 2` (96) while the SOS
 *     button occupies `insets.bottom + space.xxl` upwards (32 to 112), so a
 *     full-width bar lay across the top of an 80pt emergency button;
 *   - the report and route buttons started at `insets.top + space.xxl` (32) while
 *     the search card starts at `insets.top + space.xs` (4) and is ~42 tall, so
 *     the card — which has the higher zIndex — covered the top of both;
 *   - the risk badge is content-sized with no right bound, so a long label
 *     ("31 risk flags · news 4 min ago") ran underneath the SOS button.
 *
 * The fix is to name the sizes and derive the positions from them, so a button that
 * changes size moves the things around it instead of silently overlapping them.
 */
/**
 * How far back the user's own report history goes on the map, in days.
 *
 * 90 days. Long enough to be a record worth looking at, short enough that it is not a
 * permanent set of marks on the city -- the same instinct as `half_life_hours` on
 * everything else this map draws, applied to the one layer that cannot decay because
 * it is a list of things that happened rather than a claim about now.
 *
 * It bounds the query, not just the drawing: a report outside the window is never
 * fetched.
 */
const REPORT_HISTORY_DAYS = 90;

const FAB_SIZE = 56;
/** Vertical gap between the two stacked right-hand buttons. Was a bare `+ 70`. */
const FAB_GAP = 14;
/**
 * Height assumed for the search card until `onLayout` reports the real one — the
 * collapsed `PlaceSearch`, which is padding plus a single input row. Used for the
 * first frame only, and close enough that nothing visibly jumps.
 */
const SEARCH_CARD_FALLBACK = 46;


/**
 * An "hours from now" offset as the instant to ask the surface about.
 *
 * `undefined` for 0, so a live read sends no `as_of` at all rather than an instant that
 * is already a few hundred milliseconds stale by the time it arrives.
 *
 * Module scope, not a function inside the component, and that is not a style choice:
 * `react-hooks/purity` flags reading the clock anywhere in a component body, because a
 * render that depends on `Date.now()` is not a pure function of its props. Keeping it
 * out here makes the rule true rather than suppressed.
 */
const asOfFromOffset = (offsetHours: number): Date | undefined =>
  offsetHours === 0 ? undefined : new Date(Date.now() + offsetHours * 3600 * 1000);

/**
 * The news half of the status badge: "news 4 min ago", "reading news…", "offline replay".
 *
 * Module scope for the same `react-hooks/purity` reason as `asOfFromOffset`. D04's
 * point is that ingestion is visible as an event, not inferred from pins changing.
 */
function newsLabel(status: IngestionStatus | null, fetching: boolean): string | null {
  if (status?.mode === 'replay') return 'offline replay';
  if (fetching || status?.lastRun?.status === 'running') return 'reading news…';
  const finished = status?.lastRun?.finishedAt;
  if (!finished) return status ? 'no news run yet' : null;
  const minutes = Math.round((Date.now() - new Date(finished).getTime()) / 60000);
  if (minutes < 1) return 'news just now';
  if (minutes < 60) return `news ${minutes} min ago`;
  return `news ${Math.round(minutes / 60)} h ago`;
}

/** How long "fetch news now" waits for the run to finish: 36 polls, 5 s apart. */
const NEWS_POLL_MS = 5000;
const NEWS_POLL_LIMIT = 36;

/**
 * Hex colour plus an alpha channel, for the radius circles.
 *
 * `react-native-maps` takes rgba strings for fill and stroke. Eight-digit hex is
 * accepted on both platforms and keeps the band table in one notation.
 */
const withAlpha = (hex: string, alpha: string) => `${hex}${alpha}`;

// `getRouteColor` lived here until D06. It is now `safetyColour`, exported from
// components/RouteComparisonCard.tsx, so the polyline and the card cannot disagree about
// what a safety score looks like -- they read one table. Thresholds moved 80 -> 75 with it.

type MapScreenNavigationProp = CompositeNavigationProp<
  BottomTabNavigationProp<MainTabParamList, 'Map'>,
  NavigationProp<any>
>;

interface Props {
  navigation: MapScreenNavigationProp;
}

const MapScreen: React.FC<Props> = ({ navigation }) => {
  const { t, mode } = useTheme();
  const styles = useStyles(makeStyles);
  const { currentLocation, getCurrentLocation } = useLocationStore();
  const [region, setRegion] = useState(DEFAULT_MAP_REGION);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [crimeReports, setCrimeReports] = useState<CrimeReportData[]>([]);
  /**
   * Whether the user's own report history is drawn. **Off by default.**
   *
   * Their reports are historical records, not live hazards, and the map's job on open
   * is to show what is happening now. Defect 54's complaint was that reports and flags
   * were drawn as interchangeable pins; having to ask for the history is part of
   * separating them -- the layer that is on by default is the one that decays.
   */
  const [showMyReports, setShowMyReports] = useState(false);
  const [clusters, setClusters] = useState<CommunityCluster[]>([]);
  const [riskFlags, setRiskFlags] = useState<RiskFlag[]>([]);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [ingestion, setIngestion] = useState<IngestionStatus | null>(null);
  const [isFetchingNews, setIsFetchingNews] = useState(false);
  const [selectedFlag, setSelectedFlag] = useState<RiskFlag | null>(null);
  // Where a place search landed, so the map can show it. Null until a search
  // resolves; an unresolved search deliberately leaves this alone (no pin).
  const [resolvedPlace, setResolvedPlace] = useState<GeoResolution | null>(null);
  // The instant the server evaluated the surface at, echoed back in the response. The
  // sheet needs it to say how long a flag has left *from the moment being shown*, not
  // from now -- otherwise dragging the time control forward would show a flag with
  // negative time remaining.
  const [riskAsOf, setRiskAsOf] = useState<string | null>(null);
  // Hours ahead of now that the map is being shown at. 0 is live.
  const [asOfOffsetHours, setAsOfOffsetHours] = useState(0);

  /**
   * Which risk request is the current one.
   *
   * Opening the map fires two fetches in the first second, by design: the
   * screen mounts on `DEFAULT_MAP_REGION` and asks, then the device location
   * arrives, `region` moves, and the effect below asks again. Both call
   * `setRiskFlags`, so without this the array is whichever **answered last** --
   * and on a slow connection that is routinely the first one, for a box
   * centred somewhere the user is not looking.
   *
   * A counter rather than an AbortController: the responses are small and
   * already in flight, and this has to work the same for the `as of` taps,
   * which fire from a button rather than from an effect with a cleanup.
   */
  const riskRequestId = useRef(0);

  /** The map itself, for the one thing `region` cannot express: bearing. */
  const mapRef = useRef<MapView>(null);

  // Measured rather than guessed, like the search card above it. The time
  // control's height depends on the font and on how the six presets wrap, and
  // the map controls have to sit just clear of it.
  const [asOfHeight, setAsOfHeight] = useState(0);

  // Defect 14. One SOS implementation, shared with Home.
  // The one shared SOS controller, mounted at the app root by
  // `GuardianProvider`. Creating one per screen is what gave this app two shake
  // listeners and two camera modals per shake.

  /*
   * The search card's real height, measured rather than assumed.
   *
   * `PlaceSearch` grows when it has a result to show, so a constant would either
   * leave a gap most of the time or overlap once someone searched. Measuring means
   * the buttons below it follow it down and are never covered.
   */
  const [searchHeight, setSearchHeight] = useState(SEARCH_CARD_FALLBACK);
  const [selectedCrime, setSelectedCrime] = useState<CrimeReportData | null>(
    null,
  );
  const [isModalVisible, setIsModalVisible] = useState(false);

  // Routing State
  const [routeMode, setRouteMode] = useState(false);
  const [destination, setDestination] = useState<Location | null>(null);
  const [calculatedRoutes, setCalculatedRoutes] = useState<RouteResponse[]>([]);
  /**
   * Driving or walking. D06 shipped the backend profile and no control for it, so the
   * walkthrough's own step 12 read "switch the profile to walking, **if the UI exposes
   * it**" — which it did not. That is the §3 failure mode the plan names: ship the crude
   * screen, cut the backend depth, never the other way round.
   *
   * Walking is not a cosmetic option here. In a city where the safest way home is often on
   * foot, offering only car directions answers a question the user did not ask.
   */
  const [routeProfile, setRouteProfile] = useState<'driving' | 'foot'>('driving');
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [isRouting, setIsRouting] = useState(false);
  /**
   * Keep the camera on the user while following. On by default, and turned off the
   * moment the user taps the map -- a camera that fights a pan is worse than one
   * that does not follow at all.
   */
  const [followCamera, setFollowCamera] = useState(true);

  const selectedRoute = calculatedRoutes[selectedRouteIndex];

  /**
   * Live route following. The path identity is what resets progress, so it is
   * memoised on the selected route rather than rebuilt on every render -- a new array
   * every render would re-run the hook's cumulative-distance computation and
   * restart progress on every fix.
   */
  const followPath = useMemo(
    () =>
      selectedRoute
        ? selectedRoute.path.map(p => ({ latitude: p.latitude, longitude: p.longitude }))
        : null,
    [selectedRoute],
  );

  /**
   * The selected route's manoeuvres, memoised on the route so the hook does not see
   * a new array identity every render.
   *
   * `?? []` because `steps` is optional on the wire -- a backend from before
   * turn-by-turn landed, and the straight-line fallback, both send nothing. Empty
   * means the banner narrates from the polyline's geometry instead, which is a
   * true sentence without a road name rather than no sentence.
   */
  const followSteps = useMemo(() => selectedRoute?.steps ?? [], [selectedRoute]);

  /**
   * Route again from a given position. The one path by which a followed route is
   * replaced, reached two ways: automatically by the hook after a sustained period
   * off-route, and by the banner's button at any time.
   *
   * It takes `from` rather than reading the live position, which is what lets it be
   * declared above the hook that would otherwise have to supply it -- see
   * `onReroute` in `useNavigation.ts`. It also means an automatic re-route uses the
   * fix that triggered it rather than whatever had reached React state by then.
   *
   * `calculateRouteTo` and `getCurrentLocation` are declared further down and
   * referenced from inside this body, which is fine: the reference is resolved when
   * this runs, long after both are assigned.
   */
  const recalculateFrom = async (from?: Location | null) => {
    if (!destination) return;
    const here = from ?? currentLocation ?? (await getCurrentLocation());
    if (!here) {
      Alert.alert('Location unavailable', 'Could not work out where you are.');
      return;
    }
    setSourceLocation(here);
    setSourceQuery('My Location');
    await calculateRouteTo(here, destination);
    // The hook resets progress when the path identity changes, so the next fix
    // re-locates on the new route. Nothing to restart here.
  };

  const follow = useRouteFollow({
    path: followPath,
    totalSeconds: (selectedRoute?.duration_minutes ?? 0) * 60,
    steps: followSteps,
    // Automatic re-routing. The hook decides *when* -- sustained off-route, past a
    // cooldown -- and this decides *what*, which is the same call the banner's
    // button makes. One path, two triggers.
    onReroute: recalculateFrom,
  });

  /**
   * The journey the server is holding. JG1.
   *
   * It is read on mount, so a force-stop mid-walk is recoverable: the row
   * outlived the process, and the card below offers it back. Nothing watches it
   * -- there is no deadline and no check-in until JG2.
   */
  const journey = useJourney();

  /**
   * Measured height of the resume card, so the FAB column below it moves down
   * instead of being covered. Zero when the card is not showing, which is the
   * usual case. Same idiom and same reason as `searchHeight`.
   */
  const [resumeHeight, setResumeHeight] = useState(0);

  // Search State
  const [sourceLocation, setSourceLocation] = useState<Location | null>(null);
  const [sourceQuery, setSourceQuery] = useState('My Location');
  const [destQuery, setDestQuery] = useState('');

  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [activeSearch, setActiveSearch] = useState<'source' | 'destination' | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const insets = useSafeAreaInsets();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();

  const requestLocation = async () => {
    try {
      await getCurrentLocation();
    } catch (error) {
      Alert.alert('Location Error', 'Failed to get your current location');
    }
  };

  // Search Functions
  const fetchSuggestions = async (query: string) => {
    if (query.length < 3) {
      setSuggestions([]);
      return;
    }
    setIsSearching(true);
    try {
      // D06, defect 10: through our own proxy, not nominatim.openstreetmap.org direct.
      // One identifying User-Agent, one shared Redis cache, and traffic the server can
      // see — rather than every phone spending the per-IP rate limit separately with
      // React Native's default agent.
      setSuggestions(await geoService.search(query));
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    const query = activeSearch === 'source' ? sourceQuery : destQuery;
    const timeoutId = setTimeout(() => {
      // Don't search if it's "My Location" or empty
      if (activeSearch && query.trim().length >= 3 && query !== 'My Location') {
        fetchSuggestions(query);
      } else {
        setSuggestions([]);
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [sourceQuery, destQuery, activeSearch]);

  const handleSuggestionSelect = (suggestion: any) => {
    const loc = {
      latitude: parseFloat(suggestion.lat),
      longitude: parseFloat(suggestion.lon),
    };
    const name = suggestion.display_name.split(',')[0];

    // Zoom to selected location
    setRegion({
      latitude: loc.latitude,
      longitude: loc.longitude,
      latitudeDelta: 0.015,
      longitudeDelta: 0.015,
    });

    if (activeSearch === 'source') {
      setSourceLocation(loc);
      setSourceQuery(name);
      if (destination) {
        calculateRouteTo(loc, destination);
      }
    } else {
      setDestination(loc);
      setDestQuery(name);
      // Trigger route calc if source is ready
      if (sourceLocation || currentLocation) {
        calculateRouteTo(sourceLocation || currentLocation, loc);
      }
    }

    setSuggestions([]);
    setActiveSearch(null);
    Keyboard.dismiss();
  };

  const calculateRouteTo = async (
    start: Location | null,
    end: Location,
    profileOverride?: 'driving' | 'foot',
  ) => {
    const fromLoc = start || currentLocation;
    if (!fromLoc) {
      Alert.alert("Location Missing", "Please select a source location.");
      return;
    }

    setIsRouting(true);
    try {
      const routes = await routeService.calculateRoutes({
        source: fromLoc,
        destination: end,
        avoid_high_crime_zones: true,
        profile: profileOverride ?? routeProfile,
      });

      setCalculatedRoutes(routes);
      if (routes.length > 0) {
        setSelectedRouteIndex(0);
      } else {
        Alert.alert("No Routes", "Could not calculate a safe route.");
      }
    } catch (error) {
      Alert.alert("Error", "Failed to calculate routes.");
    } finally {
      setIsRouting(false);
    }
  };


  /**
   * The signed-in user's **own** reports, recent ones only.
   *
   * This used to be `select(...).order(...)` with no filter at all: every report ever
   * filed by anyone, unbounded in time and in space, drawn as a pin beside the risk
   * flags. Three things were wrong with that and only one of them was a bug.
   *
   * 1. **It was somebody else's claim.** One stranger's uncorroborated account naming
   *    a street is the permanent area label the concept document (section 9) commits
   *    to never producing.
   * 2. **It was a privacy surface.** A pin at a corner, plus a timestamp, plus a
   *    narrative, can identify a victim. That is section 9 and the B14 retention
   *    registry, not something to wave through because the row was readable.
   * 3. **It never ended.** No time bound, so a report from a year ago sat on a live
   *    map looking exactly like one from last night.
   *
   * So: `user_id` is filtered here *and* enforced by RLS, which is what makes it more
   * than a convention -- a client bug cannot leak what the database will not return.
   * `REPORT_HISTORY_DAYS` bounds it, and `status = 'filed'` leaves out what the author
   * has withdrawn.
   *
   * What other people reported reaches this screen through `fetchClusters`, as counts.
   */
  const fetchCrimeReports = async () => {
    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) {
        setCrimeReports([]);
        return;
      }

      const since = new Date(
        Date.now() - REPORT_HISTORY_DAYS * 24 * 60 * 60 * 1000,
      ).toISOString();

      const { data, error } = await supabase
        .from('crime_reports')
        .select(
          'id, category, title, description, incident_date_time, latitude, longitude, location_name, status',
        )
        .eq('user_id', user.id)
        // Excludes the two retired states rather than requiring 'filed', and that
        // is not a style choice. Rows written before the B13 migration still hold
        // `status = 'pending'`; `.eq('status', 'filed')` would silently return
        // nothing against a database whose migrations have not been applied yet, and
        // "my own reports vanished from the map" is a very confusing way to discover
        // a pending migration. Written this way, the filter is correct on both sides
        // of it, and still drops what the author has withdrawn.
        .not('status', 'in', '("withdrawn","removed")')
        .gte('incident_date_time', since)
        .order('created_at', { ascending: false });

      if (error) throw error;
      setCrimeReports(data || []);
    } catch (error: any) {
      console.error('Error fetching your reports:', error);
    }
  };

  /**
   * Corroborated community clusters for the area around the map centre.
   *
   * Through the backend, like the flags and for the same reason: decay and the
   * hour-of-day curve are server arithmetic, and `community_clusters` is RLS-locked
   * with no policies so the anon key cannot read it at all.
   *
   * Shares `riskRequestId` with the flag fetch deliberately. The two always move
   * together -- same region, same `as of` -- so one counter answers "is this still the
   * request the user is waiting for" for both, and a cluster layer from a stale
   * viewport can never outlive the flags it was fetched beside.
   *
   * A failure is silent beyond a warning. An empty cluster layer is the *normal*
   * state for most of Dhaka, so it must not read as an error: publishing one needs at
   * least two independent people to have filed within 200 m of each other.
   */
  const fetchClusters = async (offsetHours = asOfOffsetHours) => {
    const asOf = asOfFromOffset(offsetHours);
    const id = riskRequestId.current;
    try {
      const result = await riskService.getClustersInRegion(region, asOf);
      if (id !== riskRequestId.current) return;
      setClusters(result.clusters);
    } catch (error: any) {
      if (id !== riskRequestId.current) return;
      console.warn('Community clusters unavailable:', error?.message ?? error);
      setClusters([]);
    }
  };

  /**
   * Load risk flags for the area around the current map centre.
   *
   * Through the backend, not Supabase: `risk_flags` is RLS-locked with no policies
   * and the anon key cannot read it. Decay and the time-of-day arithmetic live on
   * the server, which is the point of the endpoint.
   *
   * A failure is recorded in state rather than shown as an Alert. An alert on
   * every failed poll is unusable, and the honest signal — "the risk layer is not
   * loading" — belongs on the screen where it can be read during a demo.
   */
  const fetchRiskFlags = async (offsetHours = asOfOffsetHours) => {
    const asOf = asOfFromOffset(offsetHours);
    const id = (riskRequestId.current += 1);
    try {
      const result = await riskService.getFlagsInRegion(region, asOf);
      // A later request has been made since this one left. Its answer is the
      // one the user is waiting for; dropping this reply is the whole point.
      if (id !== riskRequestId.current) return;
      setRiskFlags(result.flags);
      setRiskAsOf(result.asOf);
      setRiskError(null);
    } catch (error: any) {
      if (id !== riskRequestId.current) return;
      // Not fatal: the crime layer and routing still work without it.
      console.warn('Risk flags unavailable:', error?.message ?? error);
      setRiskError('Risk layer unavailable');
    }
  };

  /** The last news run. A failure just hides the news label; flags still render. */
  const refreshNewsStatus = async () => {
    try {
      setIngestion(await riskService.getIngestionStatus());
    } catch (error: any) {
      console.warn('Ingestion status unavailable:', error?.message ?? error);
      setIngestion(null);
    }
  };

  /** D04's refresh: the flags for this instant, and when the news was last read. */
  const refreshRiskLayer = () => {
    fetchRiskFlags();
    // After `fetchRiskFlags`, which is what bumps `riskRequestId` -- the cluster
    // fetch reads that counter rather than incrementing it, so the two share one
    // notion of "still current".
    fetchClusters();
    refreshNewsStatus();
  };

  /**
   * "Fetch news now" — start a Live Risk Agent run and wait for it, then reload.
   *
   * The run takes a minute or two (polite fetching plus a model call per relevant
   * article), so this polls the status rather than holding a request open. A run
   * that started within the last minute counts as ours: if the schedule happened to
   * start one just before the tap, the backend skips the duplicate and that run is
   * the one worth waiting for.
   */
  const fetchNewsNow = async () => {
    if (isFetchingNews) return;
    setIsFetchingNews(true);
    const requestedAt = Date.now();
    try {
      await riskService.runIngestion();
      for (let attempt = 0; attempt < NEWS_POLL_LIMIT; attempt++) {
        await new Promise(resolve => setTimeout(resolve, NEWS_POLL_MS));
        const status = await riskService.getIngestionStatus();
        setIngestion(status);
        const run = status.lastRun;
        if (
          run &&
          run.status !== 'running' &&
          new Date(run.startedAt).getTime() >= requestedAt - 60_000
        ) {
          break;
        }
      }
    } catch (error: any) {
      console.warn('News fetch failed:', error?.message ?? error);
    } finally {
      setIsFetchingNews(false);
      refreshRiskLayer();
    }
  };

  /**
   * Move the map's clock. Dev builds only -- see the control at the bottom of render.
   *
   * Refetches rather than filtering what is already loaded, because decay is computed
   * on the server and `severityNow` for a different instant is a different number. The
   * device deliberately holds no decay arithmetic (see `types/contracts/risk.ts`).
   */
  const setAsOfOffset = (offsetHours: number) => {
    setAsOfOffsetHours(offsetHours);
    setSelectedFlag(null); // its severity and time-remaining belong to the old instant
    fetchRiskFlags(offsetHours);
    // Clusters decay too, on a 72-hour half-life, and drop out past `expiresAt`.
    // Leaving them static while the flags moved would make the time control look
    // like it only applies to news -- and a cluster that never faded on screen is
    // the permanent street label this whole design is built to avoid.
    fetchClusters(offsetHours);
  };

  /**
   * Put the map back on the user.
   *
   * Both halves are needed, and `setRegion` alone is not enough — which is what
   * the first version did, and it did nothing at all.
   *
   * Dragging the map does **not** update `region`: there is no
   * `onRegionChangeComplete` here, deliberately, because feeding the user's own
   * pan back into a controlled prop is how a map starts fighting the finger. So
   * after a pan the state still holds wherever the map was last *told* to be —
   * usually the user's location — and `setRegion` to that same value changes
   * nothing, react-native-maps sees an unchanged prop, and the map stays where
   * the finger left it.
   *
   * `animateToRegion` moves it regardless, because it talks to the native map
   * rather than to the prop. The `setRegion` is still worth doing for the other
   * case: when the state really is somewhere else (a place search flew the map
   * across town), it both moves the map and re-runs the risk fetch for the area
   * the user is actually returning to.
   */
  const recentreOnMe = async () => {
    const here = currentLocation ?? (await getCurrentLocation());
    if (!here) return;
    const next = {
      ...region,
      latitude: here.latitude,
      longitude: here.longitude,
    };
    setRegion(next);
    mapRef.current?.animateToRegion(next, 400);
  };

  /**
   * Point the map north again.
   *
   * This one *does* go through the ref, because bearing and pitch are not in
   * `region` at all -- it carries a centre and a span and nothing about which
   * way is up. So there is no controlled value to fight with here.
   */
  const faceNorth = () => {
    // Releases camera following as well. While following, the camera is turned
    // toward the direction of travel on every fix, so without this the map would
    // swing back within two seconds and the button would look broken.
    if (follow.active) setFollowCamera(false);
    mapRef.current?.animateCamera({ heading: 0, pitch: 0 }, { duration: 300 });
  };

  const handleMarkerPress = (crime: CrimeReportData) => {
    if (routeMode) return; // Don't select markers in route mode
    setSelectedCrime(crime);
    setIsModalVisible(true);
  };

  const closeModal = () => {
    setIsModalVisible(false);
    setSelectedCrime(null);
  };

  const formatDateTime = (dateTime: string) => {
    const date = new Date(dateTime);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  // Routing Functions
  const toggleRouteMode = () => {
    if (routeMode) {
      // Exit route mode
      follow.stop();
      // Leaving route mode ends the journey, because it throws away the route and
      // the destination that the journey is about. A no-op when there is no open
      // journey, which is the usual case. `cancelled` rather than `arrived` is the
      // truth about it: the one thing JG2 and JG3 must be able to tell apart is
      // "got there" from "stopped telling us", so the two states never merge.
      void journey.cancel();
      setFollowCamera(true);
      setRouteMode(false);
      setDestination(null);
      setCalculatedRoutes([]);
      setDestQuery('');
      setSourceQuery('My Location');
      setSourceLocation(null);
    } else {
      setRouteMode(true);
    }
  };

  /**
   * Put a journey the server was holding back on the screen. JG1.
   *
   * It restores route mode, the destination and the profile, then routes again
   * **from where the person is now**. The route is not stored and deliberately
   * so: a polyline from twenty minutes ago starts at an origin they have left, so
   * following it would snap them to a point far behind and narrate a turn they
   * already took. The journey is the destination and the clock, not the line.
   *
   * It stops at the route card rather than starting to follow by itself. Two
   * reasons, and the second is the honest one. A fresh route is a fresh set of
   * candidates, and which one to take is a question the user should see the
   * answer to. And `follow.start` closes over the path in the current render, so
   * calling it in the same tick as the route arriving would be following the path
   * from *before* -- a stale-closure bug that would look like Resume silently
   * doing nothing. Pressing `Start` on the card is one tap and no such hazard,
   * and it does not create a second journey: `goesTo` recognises this one.
   */
  const resumeJourney = async () => {
    const open = journey.journey;
    if (!open) return;

    const dest = {
      latitude: open.destination_latitude,
      longitude: open.destination_longitude,
    };
    const profile: 'driving' | 'foot' = open.route_profile === 'foot' ? 'foot' : 'driving';

    setRouteMode(true);
    setRouteProfile(profile);
    setDestination(dest);
    setDestQuery(open.destination_label);

    const here = currentLocation ?? (await getCurrentLocation());
    if (!here) {
      Alert.alert('Location unavailable', 'Could not work out where you are.');
      return;
    }
    setSourceLocation(here);
    setSourceQuery('My Location');
    // The override is passed explicitly: `setRouteProfile` above has not reached
    // state yet, and routing a walk as a drive would quietly treble the ETA.
    await calculateRouteTo(here, dest, profile);
  };

  /**
   * Route to a point the user tapped on the map.
   *
   * Reached from two events, not one. See `handlePoiPress`.
   */
  const selectDestination = (coord: Location, label: string) => {
    if (!routeMode || !currentLocation) return;

    // While following, a tap on the map means "let me look around" and nothing
    // else. It must NOT set a new destination: this handler re-routes, so an
    // accidental touch mid-walk would silently replace the route being followed
    // with one to whatever patch of Dhaka the thumb landed on.
    if (follow.active) {
      setFollowCamera(false);
      return;
    }

    const dest = { latitude: coord.latitude, longitude: coord.longitude };
    setDestination(dest);
    setDestQuery(label);
    calculateRouteTo(sourceLocation || currentLocation, dest);
  };

  /** A tap on open ground. The coordinate is all there is to say about it. */
  const handleMapPress = (e: any) =>
    selectDestination(e.nativeEvent.coordinate, 'Selected Location');

  /**
   * A tap on one of Google's own labelled places -- a restaurant, a mosque, a
   * school.
   *
   * This is a **separate event**, and that is the whole bug it fixes: the Maps
   * SDK dispatches `onPoiClick` for a labelled place and `onPress` only for
   * empty ground, so with `onPress` alone every named place on the map was
   * untappable while the blank pavement beside it worked. Reported as "it only
   * selects if I miss the label", which is exactly what was happening.
   *
   * The event carries the place's `name`, so this is also better than what it
   * fixes: the destination field reads "Star Kabab" rather than "Selected
   * Location". `name` is still defended against, because the payload is the
   * SDK's and an unnamed POI is possible.
   */
  const handlePoiPress = (e: any) =>
    selectDestination(
      e.nativeEvent.coordinate,
      e.nativeEvent.name || 'Selected Location',
    );

  useEffect(() => {
    requestLocation();
    fetchCrimeReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reload flags whenever the map recentres. The fetch asks for a generous box
  // around the centre (see RISK_FETCH_MIN_SPAN_DEGREES), so this does not need to
  // fire on every pan — and deliberately does not, because the map is driven by a
  // controlled `region` prop and adding a region-change handler to it risks the
  // map fighting the user. D04 adds the explicit refresh in the status badge; a map
  // view has no scroll to pull, so "pull to refresh" is a button here.
  useEffect(() => {
    refreshRiskLayer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region.latitude, region.longitude]);

  /**
   * Keep the camera on the user while following.
   *
   * Through `mapRef.animateCamera`, and **never** through `setRegion`. That is not
   * a style preference: the effect above refetches the risk layer whenever
   * `region` changes, so following by state would fire a flags-and-clusters
   * request every two seconds for the whole walk. The ref talks to the native map
   * directly, exactly as `faceNorth` does, and leaves `region` alone.
   *
   * The camera is also turned toward the direction of travel. A north-up map while
   * walking means mentally rotating every instruction; "bear left" is only
   * unambiguous when the map agrees with which way you are facing. The bearing
   * comes from the route geometry ahead of you rather than from the phone's
   * compass, which on this hardware is noisy enough to make the map spin.
   */
  useEffect(() => {
    if (!follow.active || !followCamera || !follow.progress) return;
    const heading = follow.turn?.bearing;
    mapRef.current?.animateCamera(
      {
        center: follow.progress.snapped,
        ...(heading !== undefined ? { heading } : {}),
      },
      { duration: 600 },
    );
  }, [follow.active, followCamera, follow.progress, follow.turn?.bearing]);

  /**
   * Surface a failure to start following.
   *
   * Needed because the banner only renders while `follow.active`, and a refused
   * permission leaves `active` false -- so without this, tapping Start on a phone
   * that has denied location does nothing at all and says nothing about why. A
   * silent no-op is the worst of the three possible behaviours here.
   */
  useEffect(() => {
    if (!follow.error) return;
    Alert.alert('Cannot follow this route', follow.error);
  }, [follow.error]);

  /**
   * You arrived, so the journey is closed. JG1.
   *
   * The navigator decides this -- `hasArrived`, within 40 m of the final point --
   * and it is the only thing in JG1 that ends a journey without the user pressing
   * anything. From JG2 onward it is also what stops the clock, which is why it
   * goes through `arrive` and not `cancel`: a journey that ended by arriving and
   * one that ended by being abandoned are the two cases the whole feature exists
   * to tell apart.
   *
   * Safe to fire more than once. `useJourney` clears its own state first, so a
   * second call has no journey to close.
   */
  useEffect(() => {
    if (follow.phase !== 'arrived') return;
    void journey.arrive();
    // `journey.arrive` is stable (`useCallback`), and listing `journey` itself
    // would re-run this on every journey state change -- including the one this
    // effect causes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [follow.phase]);

  /**
   * The journey could not be recorded, and the person is about to walk off.
   *
   * Said out loud rather than swallowed, because the consequence is specific and
   * invisible: the directions work, and nothing will remember this trip if the
   * app restarts. A silent failure here is the feature pretending to be on.
   *
   * Filled in by the Start handler from what `journey.start` returned, not by an
   * effect watching the hook -- see `JourneyWrite`. Cleared when the dialog is
   * dismissed, so it is a record of what has not been read yet rather than of
   * what is wrong.
   */
  const [journeyNotice, setJourneyNotice] = useState<string | null>(null);

  // Leaving route mode stops the GPS. Without this, backing out of routing would
  // leave a high-accuracy subscription running behind the browse map.
  useEffect(() => {
    if (!routeMode && follow.active) follow.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeMode, follow.active]);

  useEffect(() => {
    if (currentLocation && !hasInitialized) {
      setRegion({
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
        latitudeDelta: 0.0922,
        longitudeDelta: 0.0421,
      });
      setHasInitialized(true);
    }
  }, [currentLocation, hasInitialized]);


  // A place search resolved: move the map to it and drop a pin.
  //
  // The zoom follows the entry's own radius, so a junction fills the screen and a
  // suburb does not pretend to be a point. Only called for resolved answers —
  // PlaceSearch does not report an unresolved one, which is what keeps the "never
  // guess" invariant visible on the map rather than only in the API.
  const flyToResolved = (resolution: GeoResolution) => {
    const span = Math.max(0.01, (resolution.radiusM / 111_000) * 8);
    setResolvedPlace(resolution);
    setRegion({
      latitude: resolution.lat,
      longitude: resolution.lon,
      latitudeDelta: span,
      longitudeDelta: span,
    });
  };

  // Laid out as a stack rather than as independent guesses — see the geometry note
  // at the top of this file.
  const searchTop = insets.top + space.xs;
  // The resume card sits between the search card and the buttons, so the buttons
  // move down by its height when it is there.
  //
  // `showResume` and not `resumeHeight > 0` alone: `onLayout` does not fire on
  // unmount, so the measured height survives the card disappearing, and the
  // buttons would stay pushed down over a gap. Deriving the offset from whether
  // the card is rendered makes it correct in both directions.
  const resumeTop = searchTop + searchHeight + space.sm;
  const showResume = !routeMode && !journey.loading && !!journey.journey;
  const fabColumnTop =
    resumeTop + (showResume && resumeHeight > 0 ? resumeHeight + space.sm : 0);
  // Every bottom overlay measures from here rather than from `insets.bottom`.
  // The tab bar now floats *over* this screen instead of sitting below it, so
  // the safe floor moved up by its height — and because the geometry note above
  // derives the SOS button, the risk badge and the time control from one base,
  // changing the base keeps all three in the same relationship.
  const bottomFloor = insets.bottom + TAB_BAR_CLEARANCE;
  // What the time control has to clear. It was the top of the SOS button; with
  // that gone it is just the floor plus the badge's own row, so the control sits
  // lower and gives the map back the strip it was using.
  const overlayFloor = bottomFloor + space.xxl + 28;
  // `maxWidth` rather than a `right` bound: setting both `left` and `right` on an
  // absolute element stretches it, so a badge reading "0 risk flags" would sit in a
  // pill the width of the screen. This hugs the label.
  //
  // It used to subtract `SOS_SIZE` to stop short of the SOS button. That button
  // is gone, so the badge gets two thirds of the width — enough for the longest
  // real label ("31 risk flags · news 4 min ago") without ellipsis.
  /**
   * The tallest the expanded route card may be.
   *
   * Two constraints, and the second one is the point.
   *
   * **It must not reach the search card.** `76%` of the screen was fine until the
   * "Plan a route" card grew -- two location fields, a profile row, and a taller
   * label once a destination is named -- at which point the expanded details
   * covered the very fields that produced them. `searchHeight` is already measured
   * by that card's own `onLayout` for the FAB column, so this costs nothing new.
   *
   * **And it must leave a band of map visible.** Clearing the search card was not
   * enough on its own: the card then grew to fill *exactly* the gap, which is
   * still a screen with no map on it. A route card that hides the route is the
   * one thing this card must never do -- the whole reason to open the details is
   * to understand the line drawn on the map, and you cannot read the two against
   * each other if only one is on screen.
   *
   * Nothing is lost to the smaller cap, because the expanded body is a scroll
   * view. The cost is scrolling; the alternative was an invisible map.
   */
  const MIN_MAP_BAND = Math.max(120, windowHeight * 0.16);
  const routeCardSpace =
    windowHeight - (searchTop + searchHeight + space.md) - (bottomFloor + space.lg);
  const routeCardMaxHeight = Math.max(
    // The floor wins on a cramped screen. Below about this the card stops being
    // able to show its own controls, and a card you cannot press Start on is
    // worse than a thin strip of map.
    260,
    routeCardSpace - MIN_MAP_BAND,
  );

  const riskBadgeMaxWidth = (windowWidth - space.xl * 2) * 0.66;

  return (
    <View style={styles.container}>
      <MapView
        // The map's own light/dark, pinned to the app's theme instead of the
        // phone's, and remounted when it changes because Android reads the
        // scheme only at creation. Both lines are load-bearing -- the long
        // version of why is in `MapComponent.tsx`.
        key={mode}
        userInterfaceStyle={mode}
        ref={mapRef}
        provider={MAP_PROVIDER}
        style={styles.map}
        region={region}
        showsUserLocation
        // Google's own controls are off, and replaced below.
        //
        // They are positioned by the Maps SDK against the top edge of the map,
        // which here is the top edge of the *screen* -- the map is full-bleed so
        // that content can float over it. So the locate button sat under the
        // status bar, among the clock and the charging icon, and the compass sat
        // under the search card. `mapPadding` is the usual answer and cannot
        // help: it moves them down from the top, and the room is at the bottom.
        showsMyLocationButton={false}
        showsCompass={false}
        onPress={handleMapPress}
        // Labelled places come through here instead of `onPress`, never both.
        onPoiClick={handlePoiPress}
      >
        {/* Source Marker */}
        {sourceLocation && (
          <Marker
            coordinate={sourceLocation}
            title="Start Location"
            pinColor="#4CAF50"
            anchor={{ x: 0.5, y: 1 }}
          />
        )}

        {/* Destination Marker */}
        {destination && (
          <Marker
            coordinate={destination}
            title="Destination"
            pinColor="#F44336"
            anchor={{ x: 0.5, y: 1 }}
          />
        )}

{/* Routes.
            D06: the line is coloured by `safety_score`, through the same `safetyColour`
            the card uses. It used to be coloured by rank — blue, amber, grey by index —
            which encoded *position in the list* and told you nothing about the route. Two
            routes could look identically "second" while one was safe and one was not. */}
        {calculatedRoutes.map((route, index) => {
          const isSelected = index === selectedRouteIndex;
          // While following, the selected route is drawn in two parts: the stretch
          // already behind, faint, and the stretch ahead, full strength. That is
          // what makes the line visibly shrink from the start point as you move,
          // which is the whole feature.
          //
          // The unselected candidates are left whole. They are alternatives being
          // compared, not routes being followed, and trimming them would imply
          // progress along a path nobody is on.
          // `behind`, not `ahead`, is the test. At the very end of a route `ahead`
          // collapses to the single snapped point, and keying off it would make the
          // whole untrimmed line reappear at the moment of arrival -- undoing, in
          // one frame, all the shrinking the user just watched. `behind` only
          // reaches one point before the first fix, which is exactly when the
          // untrimmed line IS the right thing to draw.
          const following = isSelected && follow.active && follow.behind.length > 1;

          if (following) {
            return (
              <React.Fragment key={route.route_id}>
                <Polyline
                  coordinates={follow.behind}
                  strokeColor={withAlpha(safetyColour(route.safety_score, t), '4D')}
                  strokeWidth={5}
                  zIndex={8}
                />
                {/* A Polyline with fewer than two points draws nothing, so this is
                    simply absent once the route is finished rather than being a
                    degenerate line. */}
                {follow.ahead.length > 1 && (
                  <Polyline
                    coordinates={follow.ahead}
                    strokeColor={safetyColour(route.safety_score, t)}
                    strokeWidth={7}
                    zIndex={10}
                  />
                )}
              </React.Fragment>
            );
          }

          return (
            <Polyline
              key={route.route_id}
              coordinates={route.path.map(p => ({ latitude: p.latitude, longitude: p.longitude }))}
              strokeColor={safetyColour(route.safety_score, t)}
              strokeWidth={isSelected ? 6 : 3}
              onPress={() => setSelectedRouteIndex(index)}
              tappable={true}
              lineDashPattern={isSelected ? undefined : [10, 5]}
              zIndex={isSelected ? 10 : 1}
            />
          );
        })}

        {/* Where you are on the route, as against where the phone thinks you are.
            Its own component because it needs the `tracksViewChanges` settle that
            `RiskFlagMarker` documents: written inline with tracking off from the
            first render, the native side can snapshot the child before it has
            drawn and freeze a blank circle -- and unlike a flag marker there is no
            key change to recover it, so the dot would be missing for the whole
            walk while the route trimmed correctly around it. */}
        {follow.active && follow.progress && (
          <FollowMarker coordinate={follow.progress.snapped} />
        )}

        {/* Flagged corridors along each candidate. D06: *"flagged corridors visibly
            highlighted along the rejected route, so the comparison reads without
            narration."*

            Two styles, and the distinction is the whole point. A flag on the route you are
            looking at is drawn solid — this is what you would pass. A flag that only
            appears on a route you are NOT looking at is drawn dashed and faint — this is
            what the recommended option is avoiding. Seeing both at once is what makes
            "4 minutes longer, avoids two flagged corridors" legible on the map rather
            than only in a sentence. */}
        {routeMode &&
          (() => {
            const selectedIds = new Set(
              (calculatedRoutes[selectedRouteIndex]?.flags ?? []).map(f => f.flag_id),
            );
            // Deduplicate across routes: a flag on three candidates is one circle.
            const byId = new Map<string, (typeof calculatedRoutes)[number]['flags'][number]>();
            calculatedRoutes.forEach(route =>
              route.flags.forEach(flag => byId.set(flag.flag_id, flag)),
            );
            return Array.from(byId.values()).map(flag => {
              const onSelected = selectedIds.has(flag.flag_id);
              return (
                <Circle
                  key={`route-flag-${flag.flag_id}-${onSelected ? 'on' : 'off'}`}
                  center={{ latitude: flag.lat, longitude: flag.lon }}
                  radius={flag.radius_m}
                  strokeWidth={onSelected ? 2 : 1}
                  strokeColor={withAlpha(t.danger, onSelected ? 'CC' : '55')}
                  fillColor={withAlpha(t.danger, onSelected ? '26' : '0D')}
                  lineDashPattern={onSelected ? undefined : [8, 6]}
                  zIndex={onSelected ? 5 : 2}
                />
              );
            });
          })()}

        {/* Risk flag radius circles.
            Drawn before the markers so the pins sit on top of them. A flag is a
            claim about an AREA — a bare pin would overstate how precisely the
            location is known. */}
        {!routeMode &&
          riskFlags
            .filter(flag => flag.radiusM <= MAX_DRAWN_RADIUS_M)
            .map(flag => {
              const band = riskBand(flag.severityNow);
              // D05. The verification tier, on the area as well as on the pin: a
              // corroborated claim is drawn solid, a single-source one dashed and
              // fainter. Two channels for one distinction, because colour is already
              // carrying severity and a dashed outline survives a bad projector.
              const confirmed = isConfirmedFlag(flag);
              return (
                <Circle
                  key={`risk-circle-${flag.flagId}-${flag.status}`}
                  center={{ latitude: flag.lat, longitude: flag.lon }}
                  radius={flag.radiusM}
                  strokeWidth={confirmed ? 2 : 1}
                  strokeColor={withAlpha(band.color, confirmed ? 'CC' : '77')}
                  fillColor={withAlpha(band.color, confirmed ? '2E' : '12')}
                  // Android ignores a dash pattern below ~2px stroke width; the fill
                  // and stroke alpha carry the distinction where this does not land.
                  lineDashPattern={confirmed ? undefined : [8, 6]}
                />
              );
            })}

        {/* Risk flag pins.
            The callout text is `mobilityStatement` and nothing else. It is the
            only user-facing string the server produced through
            app/policy/framing.py, and building a label from `kind` here would put
            the word "clash" on a map that has committed not to say it.

            Colour is `severityNow`, not `severity0`: a pin that fades as the time
            control moves is demo beat 5, and it only works if the colour tracks the
            decayed value. */}
        {!routeMode &&
          riskFlags.map(flag => (
            // D05 replaced the native teardrop here. `pinColor` can carry exactly one
            // variable and D04 had already spent it on severity, leaving nowhere for
            // the verification tier or the source count. See RiskFlagMarker for the
            // `tracksViewChanges` and `key` reasoning -- both matter at ~60 markers.
            <RiskFlagMarker
              // `tracksViewChanges={false}` means the marker bitmap is taken once, so
              // every field that changes the drawing has to be in this key. `validFrom`
              // joined it in D09: it decides round versus square.
              key={`risk-${flag.flagId}-${flag.status}-${flag.sourceCount}-${flag.validFrom ?? 'live'}`}
              flag={flag}
              onPress={setSelectedFlag}
            />
          ))}

        {/* Crime Report Markers */}
        {!routeMode && resolvedPlace && (
          <Marker
            coordinate={{ latitude: resolvedPlace.lat, longitude: resolvedPlace.lon }}
            title={resolvedPlace.resolvedName}
            description={
              resolvedPlace.method === 'gazetteer'
                ? 'From our Dhaka gazetteer'
                : 'Inferred by AI'
            }
            pinColor={resolvedPlace.method === 'gazetteer' ? '#2E7D32' : '#1565C0'}
          />
        )}

        {/* What other people reported, as counts. B13.
            Drawn before the user's own pins so an own-report teardrop sits above a
            cluster pill it overlaps -- the user's own record is the thing they are
            most entitled to be able to tap.

            Hidden in route mode like every other browse-layer marker: the route card
            carries its own cluster list, and a corridor cluttered with pills is the
            problem the route view exists to avoid. */}
        {!routeMode &&
          clusters.map(cluster => (
            <CommunityClusterMarker
              key={cluster.clusterId}
              cluster={cluster}
              onPress={() => {}}
            />
          ))}

        {/* The user's own report history, behind an explicit toggle.
            `showMyReports` defaults to false -- see the state declaration. Every pin
            here is the signed-in user's own: there is no query that returns anyone
            else's any more. */}
        {!routeMode && showMyReports && crimeReports.map(crime => (
          <Marker
            key={crime.id}
            coordinate={{
              latitude: parseFloat(crime.latitude),
              longitude: parseFloat(crime.longitude),
            }}
            title={crime.title}
            description={`Your report · ${crimeCategoryLabel(crime.category)}`}
            // Defect 3, the other half. CRIME_COLORS was already defined and was
            // never passed to a marker, so even with correct keys every pin would
            // still have rendered in the default red.
            pinColor={crimeColor(crime.category)}
            onPress={() => handleMarkerPress(crime)}
          />
        ))}
      </MapView>

      {/* Place search - demo beat 3. Hidden in route mode, which has its own inputs. */}
      {!routeMode && (
        <View
          style={[styles.searchContainer, { top: searchTop }]}
          onLayout={event => setSearchHeight(event.nativeEvent.layout.height)}
        >
          <PlaceSearch onResolved={flyToResolved} />
        </View>
      )}

      {/* A journey the server was still holding. JG1, and the whole visible
          output of that phase.

          Shown only outside route mode, which is exactly the state a cold start
          lands in -- so force-stopping the app mid-walk and reopening it finds
          this instead of an empty map. `loading` keeps it off the screen until
          the launch read has answered, so it does not flash in and out.

          `opaque` for the reason the search card above gives: with the blur off,
          the fill is all that separates this card's text from the map's. */}
      {showResume && journey.journey && (
        <View
          style={[styles.searchContainer, { top: resumeTop }]}
          onLayout={event => setResumeHeight(event.nativeEvent.layout.height)}
        >
          <Glass
            style={styles.searchBox}
            padding={space.md}
            radius={radius.card}
            blur={false}
            opaque
            elevated
          >
            <View style={styles.resumeRow}>
              <Ionicons
                name={journey.journey.route_profile === 'foot' ? 'walk' : 'navigate'}
                size={18}
                color={t.brand}
              />
              <View style={styles.resumeText}>
                <Text style={styles.resumeTitle} numberOfLines={1}>
                  Journey in progress
                </Text>
                {/* The route's own estimate and the time it was taken, not a
                    countdown. There is no clock in JG1 -- a "7 min left" here
                    would be a number nothing is maintaining, and the phase that
                    builds the clock is JG2. */}
                <Text style={styles.resumeDetail} numberOfLines={1}>
                  {`${Math.round(journey.journey.duration_minutes)} min to ${journey.journey.destination_label}`}
                  {startedAtLabel(journey.journey.started_at)
                    ? ` · started ${startedAtLabel(journey.journey.started_at)}`
                    : ''}
                </Text>
              </View>
            </View>
            <View style={styles.resumeActions}>
              <TouchableOpacity
                onPress={() => void journey.cancel()}
                style={styles.resumeEnd}
                accessibilityRole="button"
                accessibilityLabel="End this journey"
              >
                <Text style={styles.resumeEndText}>End</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => void resumeJourney()}
                style={styles.resumeGo}
                accessibilityRole="button"
                accessibilityLabel="Resume this journey"
              >
                <Text style={styles.resumeGoText}>Resume</Text>
              </TouchableOpacity>
            </View>
          </Glass>
        </View>
      )}

      {/* Route Search Interface (Google Maps Style).

          Hidden once following starts. The route comparison card below already
          had `!follow.active`; this one did not, so pressing Start left the
          planner sitting over the map with the navigation banner underneath it
          -- two cards, and the source and destination fields are not something
          anyone edits mid-walk.

          It also removes the only way to reach the close button below while
          walking, which is the second half of the same report: that button exits
          route mode completely. The exit while following is the banner's own,
          which stops following and brings this back. */}
      {routeMode && !follow.active && (
        <View style={[styles.searchContainer, { top: searchTop }]}>
          {/* `padding` on the prop, never in `searchBox` -- see that style.

              `blur={false}` is NOT a performance trade here -- it is the fix for a
              crash that killed the process. This screen has no `Aurora`, so its
              `Glass` panels resolved the only blur target in scope: the
              `ClaimBlurTarget` that `MainNavigator` wraps around the whole screen.
              That makes the `BlurView` a descendant of the view it blurs, the
              transform chain never bottoms out, and the render thread overflows its
              stack -- `SIGSEGV`, no redbox, nothing in Metro. `BlurTarget.tsx` has
              the full account; `Sheet.tsx` turns it off for the same reason.

              Nothing is lost visually either way: Dimezis blurs the target's own
              canvas, a Google map draws on a surface that canvas never sees, so the
              blur of a map is the blur of nothing -- which comes out black, not
              transparent. See the note in `Aurora.tsx`.

              `opaque` because with the blur gone the fill is all that separates
              this card's text from the map's. See `Glass.tsx`. */}
          <Glass
            style={styles.searchBox}
            padding={space.md}
            radius={radius.card}
            blur={false}
            opaque
            elevated
          >
            {/* Source input, with the way out of route mode on the same row.
                A "Plan a route" title used to sit above this in a header of its
                own, which spent a whole row saying what two labelled fields and a
                Driving/Walking pair already say. The close control stays -- it is
                how you leave route mode, and a reload was once the only escape --
                it just no longer needs a row to itself.

                It leaves route mode outright, which is why this whole card is
                hidden while following: there, "close" has to mean stop walking,
                and that button is on the navigation banner. */}
            <View style={styles.inputRow}>
              <View style={[styles.inputDot, styles.sourceDot]} />
              <TextInput
                style={styles.input}
                value={sourceQuery}
                onChangeText={(text) => {
                  setSourceQuery(text);
                  setActiveSearch('source');
                }}
                onFocus={() => setActiveSearch('source')}
                placeholder="Start location"
                placeholderTextColor={t.textSoft}
                selectTextOnFocus
              />
              {activeSearch === 'source' && isSearching && <ActivityIndicator size="small" color={t.brand} />}
              <TouchableOpacity
                onPress={toggleRouteMode}
                hitSlop={12}
                style={styles.routeClose}
                accessibilityRole="button"
                accessibilityLabel="Close route planning"
              >
                <Ionicons name="close" size={20} color={t.textSoft} />
              </TouchableOpacity>
            </View>

            <View style={styles.connectorLine} />

            {/* Destination Input */}
            <View style={styles.inputRow}>
              <View style={[styles.inputDot, styles.destDot]} />
              <TextInput
                style={styles.input}
                placeholder="Where to?"
                value={destQuery}
                onChangeText={(text) => {
                  setDestQuery(text);
                  setActiveSearch('destination');
                }}
                onFocus={() => setActiveSearch('destination')}
                placeholderTextColor={t.textSoft}
                autoFocus={true}
              />
              {activeSearch === 'destination' && isSearching && <ActivityIndicator size="small" color={t.brand} />}
            </View>

            {/* Driving / walking. Re-requests immediately when a route is already shown,
                because a mode switch that needs a second tap to take effect reads as
                broken — and the two profiles give genuinely different answers. */}
            <View style={styles.profileRow}>
              {(['driving', 'foot'] as const).map(mode => {
                const active = routeProfile === mode;
                return (
                  <TouchableOpacity
                    key={mode}
                    style={[styles.profileChip, active && styles.profileChipActive]}
                    onPress={() => {
                      if (active) return;
                      setRouteProfile(mode);
                      if (destination) {
                        // `calculateRouteTo` reads `routeProfile` from the closure, so pass
                        // the new value explicitly rather than relying on a state update
                        // that has not landed yet.
                        calculateRouteTo(sourceLocation, destination, mode);
                      }
                    }}
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                    accessibilityLabel={mode === 'driving' ? 'Driving directions' : 'Walking directions'}
                  >
                    <Ionicons
                      name={mode === 'driving' ? 'car-outline' : 'walk-outline'}
                      size={15}
                      // Same reason as `profileChipTextActive`: this sits ON the
                      // brandStrong fill, so it has to be the on-brand colour.
                      color={active ? t.onBrand : t.textSoft}
                    />
                    <Text style={[styles.profileChipText, active && styles.profileChipTextActive]}>
                      {mode === 'driving' ? 'Driving' : 'Walking'}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </Glass>

          {/* Suggestions List.

              `blur={false}` for the reason on the card above: over a map, on a
              screen with no backdrop of its own, the blur is a crash -- and
              `opaque` for the other half of it, because a list of place names
              over a map full of place names is unreadable at 62%. */}
          {suggestions.length > 0 && (
            <Glass
              style={styles.suggestionsContainer}
              padding={0}
              radius={radius.md}
              blur={false}
              opaque
              elevated
            >
              <ScrollView keyboardShouldPersistTaps="always">
                {suggestions.map((item, index) => (
                  <TouchableOpacity
                    key={index}
                    style={styles.suggestionItem}
                    onPress={() => handleSuggestionSelect(item)}
                  >
                    <Ionicons name="location-outline" size={20} color={t.textSoft} />
                    <Text style={styles.suggestionText}>{item.display_name}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </Glass>
          )}
        </View>
      )}

      {/* The 80pt red SOS button that used to sit here has been removed.
          Removed rather than moved: it was the third way to reach the same
          `useSosController`, after the Home screen's button and the two
          automatic triggers in Guardian (shout and shake), and on this screen
          it cost more than it gave. It occupied the bottom-right corner, which
          is where the route sheet and the risk badge now live, and the whole
          overlay geometry below was arranged around avoiding an 80pt circle.

          Nothing about the SOS path changed — `GuardianProvider` still holds one
          controller for the app, still armed from the first frame, and the
          shouted phrase and the hard shake still work on this screen. */}
      {/* SOSFlow is rendered once by GuardianProvider at the app root. */}

      {/* Report Button (Hide in route mode) */}
      {!routeMode && (
        <TouchableOpacity
          style={[styles.reportButton, { top: fabColumnTop }]}
          onPress={() => {
            navigation.navigate('Reports');
            setTimeout(() => {
              navigation.navigate('AddReport');
            }, 100);
          }}
        >
          <Ionicons name="warning" size={24} color={t.onBrand} />
        </TouchableOpacity>
      )}

      {/* Enter route mode. Leaving it is the card's own close control, not this
          button: in route mode this sat inside the route card and under it, so it
          could not be tapped at all. It is hidden there now rather than restyled,
          because a 56px floating circle on top of a text field was reachable but
          still wrong. */}
      {!routeMode && (
        <TouchableOpacity
          style={[
            styles.actionButton,
            {
              top: fabColumnTop + FAB_SIZE + FAB_GAP,
              right: space.xl,
              backgroundColor: t.brand
            }
          ]}
          onPress={toggleRouteMode}
          accessibilityRole="button"
          accessibilityLabel="Plan a route"
        >
          <Ionicons name="navigate" size={24} color={t.onBrand} />
        </TouchableOpacity>
      )}

      {/* Route comparison card — D06, beat 4.
          Replaced ~45 lines of inline JSX that rendered `safety_score` as `58.3% Safe`
          (defect 11's third scale) and whose "description" was a three-way ternary on the
          index, not a reason. The card now shows the server's framed explanation, the
          trade-off sentence, the flags behind the score, and any caveat about how the
          answer was produced. */}
      {/* The comparison card and the navigation banner are mutually exclusive, and
          that is the design rather than a layout convenience. The card answers
          "which of these routes should I take" -- three candidates, safety scores,
          flag lists, a trade-off sentence. Once following has started that question
          is settled, and the screen's job becomes "am I going the right way".
          Leaving both up would bury the instruction in a sheet you have to expand
          one-handed while walking. */}
      {routeMode && calculatedRoutes.length > 0 && !follow.active && (
        <RouteComparisonCard
          routes={calculatedRoutes}
          selectedIndex={selectedRouteIndex}
          onSelect={setSelectedRouteIndex}
          bottomInset={bottomFloor}
          maxHeight={routeCardMaxHeight}
          // Following is opt-in rather than automatic on route calculation: this
          // screen is a map first and a navigator second, and acquiring
          // high-accuracy fixes every two seconds because a route happens to be
          // drawn would flatten a battery for someone who was only comparing
          // options.
          // JG1. The journey is written *before* following starts, because that
          // ordering is what makes it survive -- the row has to exist before the
          // thing that could be killed begins.
          //
          // It does not block following. A phone with no signal at the moment
          // someone presses Start is a phone whose owner still needs directions,
          // and refusing to navigate because we could not record the journey
          // would be the safety feature making the person less safe. `start`
          // resolves to null instead of throwing, and the effect above says so.
          onStart={() => {
            setFollowCamera(true);
            const open = journey.journey;
            const route = calculatedRoutes[selectedRouteIndex];
            const from = sourceLocation ?? follow.position ?? currentLocation;

            // Already recorded: this is the journey being resumed, reached
            // through the same button. Recording a second one would move
            // `started_at` to now, and from JG2 onward that is the instant the
            // deadline is measured from.
            const alreadyOpen = !!open && !!destination && goesTo(open, destination);

            void (async () => {
              if (!alreadyOpen && destination && from && route) {
                const written = await journey.start({
                  origin_latitude: from.latitude,
                  origin_longitude: from.longitude,
                  destination_latitude: destination.latitude,
                  destination_longitude: destination.longitude,
                  // Falls back rather than sending an empty string, which the
                  // server rejects: a map tap on open ground leaves `destQuery`
                  // as 'Selected Location', but a cleared field leaves it blank.
                  destination_label: destQuery.trim() || 'Selected Location',
                  route_id: route.route_id ?? null,
                  route_profile: routeProfile,
                  distance_km: route.distance_km,
                  duration_minutes: route.duration_minutes,
                  safety_score: route.safety_score ?? null,
                });
                // Here, and not in an effect watching the hook: a failure message
                // held in state is the same string every time, so the second
                // failed Start would change nothing for an effect to notice and
                // the screen would sit silent through it. See `JourneyWrite`.
                if (written.error) setJourneyNotice(written.error);
              }
              void follow.start();
            })();
          }}
        />
      )}

      {routeMode && follow.active && (
        <NavigationBanner
          phase={follow.phase}
          turn={follow.turn}
          step={follow.step}
          rerouting={follow.rerouting}
          remainingM={follow.remainingM}
          remainingSeconds={follow.remainingSeconds}
          accuracyM={follow.accuracyM}
          bottomInset={bottomFloor}
          recalculating={isRouting}
          onRecalculate={() => recalculateFrom(follow.position)}
          onStop={() => {
            follow.stop();
            // Stopping the navigator ends the journey. The banner's cross is the
            // user saying they are done walking this route, which is the same
            // statement as closing the journey -- and leaving an active row
            // behind would make the next launch offer to resume a journey that
            // was deliberately abandoned.
            void journey.cancel();
            setFollowCamera(true);
          }}
        />
      )}

      {/* Following, but the user has panned away. One tap back, and nothing happens
          automatically -- a camera that re-centres on its own while someone is
          looking at a side street is the behaviour that makes people put the phone
          away. */}
      {follow.active && !followCamera && (
        // The wrapper is what centres the chip. `alignSelf` on an absolutely
        // positioned element with left:0 and right:0 does nothing -- the element
        // simply spans the width, and a full-width transparent touch target over a
        // map swallows the taps meant for it. `box-none` lets touches through
        // everywhere except on the chip itself.
        <View
          pointerEvents="box-none"
          style={[styles.recentreRow, { bottom: bottomFloor + space.lg + 92 }]}
        >
          <Pressable
            onPress={() => setFollowCamera(true)}
            style={styles.recentreChip}
            accessibilityRole="button"
            accessibilityLabel="Re-centre on me"
          >
            <Ionicons name="locate" size={14} color={t.brand} />
            <Text style={styles.recentreText}>Re-centre</Text>
          </Pressable>
        </View>
      )}

      {/* Risk layer status, refresh, and "fetch news now" (D04).
          Small, but it is what turns "the map looks the same as yesterday" into a
          readable answer: a flag count and when the news was last read, or the reason
          there is none. Bottom-left since D04: at the top it sat under the search card
          (zIndex 10) and could not be seen at all. */}
      {!routeMode && (
        <View
          style={[
            styles.riskBadge,
            {
              bottom: bottomFloor + space.xxl,
              // A content-sized badge with no bound slid under the SOS button once
              // the label grew. Bounded here; the label ellipsizes instead.
              maxWidth: riskBadgeMaxWidth,
            },
          ]}
        >
          <View
            style={[
              styles.riskDot,
              {
                backgroundColor: riskError
                  ? t.danger
                  : asOfOffsetHours > 0
                    ? t.info
                    : t.ok,
              },
            ]}
          />
          {/* The badge text is the way into the news page, rather than a third
              icon in a row of two. It already reads "… · news 4 min ago", so it is
              the thing on screen that most looks like it should open the news, and
              it is a far bigger tap target than another 16pt glyph. */}
          <TouchableOpacity
            onPress={() => navigation.navigate('News')}
            hitSlop={8}
            style={styles.riskBadgeLabel}
            accessibilityLabel="See the articles behind these flags"
          >
            <Text style={styles.riskBadgeText} numberOfLines={1}>
              {riskError ??
                [
                  `${riskFlags.length} risk flags`,
                  // Counted separately, never added to the flag count. They are
                  // different claims, and "14 things on the map" would be the number
                  // that hides exactly the distinction this layer exists to make.
                  clusters.length > 0 ? `${clusters.length} report areas` : '',
                  newsLabel(ingestion, isFetchingNews),
                ]
                  .filter(Boolean)
                  .join(' · ')}
            </Text>
          </TouchableOpacity>
          {/* Your own report history on and off. In the badge rather than as a third
              FAB: it is a layer control, and the badge is already the row that says
              what the map is showing. The icon is filled when the layer is on, so the
              control states its own position without a label. */}
          <TouchableOpacity
            onPress={() => setShowMyReports(current => !current)}
            style={styles.riskBadgeButton}
            hitSlop={8}
            accessibilityRole="switch"
            accessibilityState={{ checked: showMyReports }}
            accessibilityLabel={
              showMyReports ? 'Hide my past reports' : 'Show my past reports'
            }
          >
            <Ionicons
              name={showMyReports ? 'bookmark' : 'bookmark-outline'}
              size={16}
              color={showMyReports ? t.brand : t.textSoft}
            />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={refreshRiskLayer}
            style={styles.riskBadgeButton}
            hitSlop={8}
            accessibilityLabel="Refresh risk flags"
          >
            <Ionicons name="refresh" size={16} color={t.textSoft} />
          </TouchableOpacity>
          {ingestion?.mode !== 'replay' && (
            <TouchableOpacity
              onPress={fetchNewsNow}
              disabled={isFetchingNews}
              style={styles.riskBadgeButton}
              hitSlop={8}
              accessibilityLabel="Fetch today's news now"
            >
              {isFetchingNews ? (
                <ActivityIndicator size="small" color={t.brand} />
              ) : (
                <Ionicons name="newspaper-outline" size={16} color={t.brand} />
              )}
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Locate, and face north. Google's two, in a place a thumb can reach.
          Above the time control rather than below it: the bottom strip belongs
          to the thing that changes what the map is showing, and these only
          change where you are looking. Right-hand side, stacked, so they line up
          under the report and route buttons rather than starting a third column. */}
      {!routeMode && asOfHeight > 0 && (
        <View
          style={[
            styles.mapControls,
            { bottom: overlayFloor + space.sm + asOfHeight + space.md },
          ]}
        >
          <TouchableOpacity
            style={styles.mapControl}
            onPress={faceNorth}
            accessibilityRole="button"
            accessibilityLabel="Face the map north"
          >
            <Ionicons name="compass-outline" size={22} color={t.textSoft} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.mapControl, styles.mapControlLast]}
            onPress={recentreOnMe}
            accessibilityRole="button"
            accessibilityLabel="Centre the map on my location"
          >
            <Ionicons name="locate" size={22} color={t.brand} />
          </TouchableOpacity>
        </View>
      )}

      {/* The time control. Demo beat 8 — and the reason it ships.
          It arrived in D02 behind `__DEV__`, as the only way to make decay
          showable: without it, beat 5 means standing on stage saying "trust me,
          in three hours this will fade". D09 takes the `__DEV__` off, because the
          same control answers a question no competing product asks — what will
          this road be like tomorrow? Forward-dated flags are served only inside
          their window, so a procession announced for tomorrow is genuinely absent
          at Now and genuinely there at Tomorrow.

          Presets rather than a slider, deliberately: a slider needs a dependency
          the project does not have, a dragged value fires a request per frame, and
          six taps are repeatable on stage in a way a drag is not. */}
      {!routeMode && (
        <View
          style={[styles.asOfBar, { bottom: overlayFloor + space.sm }]}
          onLayout={event => setAsOfHeight(event.nativeEvent.layout.height)}
        >
          <Text style={styles.asOfLabel}>{asOfSummary(asOfOffsetHours, riskFlags, Date.now())}</Text>
          <View style={styles.asOfButtons}>
            {AS_OF_PRESETS.map(({ hours, label }) => (
              <TouchableOpacity
                key={hours}
                style={[
                  styles.asOfButton,
                  asOfOffsetHours === hours && styles.asOfButtonActive,
                ]}
                onPress={() => setAsOfOffset(hours)}
              >
                <Text
                  // One line, shrinking if it has to. Six presets share the
                  // width and "Tomorrow" is the longest; in Inter it no longer
                  // fits the sixth of a screen the old face did, and it was
                  // wrapping to "Tomorr / ow". Shrinking one label beats
                  // abbreviating it or giving the row a horizontal scroll.
                  numberOfLines={1}
                  adjustsFontSizeToFit
                  minimumFontScale={0.8}
                  style={[
                    styles.asOfButtonText,
                    asOfOffsetHours === hours && styles.asOfButtonTextActive,
                  ]}
                >
                  {label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Flag detail sheet. Demo beat 2. */}
      <RiskFlagSheet
        flag={selectedFlag}
        asOf={riskAsOf}
        onClose={() => setSelectedFlag(null)}
      />

      {/* Loading Indicator */}
      {isRouting && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={t.brand} />
          <Text style={styles.loadingText}>Calculating safest route...</Text>
        </View>
      )}

      {/* Crime Details Modal */}
      {/* A detail the user opened by tapping a pin, so `dismissable`. */}
      <Sheet
        visible={isModalVisible}
        variant="bottom"
        onClose={closeModal}
        dismissable
        padding={space.xl}
      >
          <View style={styles.modalContent}>
            {selectedCrime && (
              <>
                <View style={styles.modalHeader}>
                  <View style={styles.categoryBadge}>
                    <Text
                      style={[
                        styles.categoryText,
                        { color: crimeColor(selectedCrime.category) },
                      ]}
                    >
                      {crimeCategoryLabel(selectedCrime.category)}
                    </Text>
                  </View>
                  <TouchableOpacity onPress={closeModal}>
                    <Ionicons name="close" size={28} color={t.text} />
                  </TouchableOpacity>
                </View>

                <ScrollView showsVerticalScrollIndicator={false}>
                  <Text style={styles.crimeTitle}>{selectedCrime.title}</Text>

                  <View style={styles.infoRow}>
                    <Ionicons
                      name="time-outline"
                      size={18}
                      color={t.textSoft}
                    />
                    <Text style={styles.infoText}>
                      {formatDateTime(selectedCrime.incident_date_time)}
                    </Text>
                  </View>

                  {selectedCrime.location_name && (
                    <View style={styles.infoRow}>
                      <Ionicons
                        name="location-outline"
                        size={18}
                        color={t.textSoft}
                      />
                      <Text style={styles.infoText}>
                        {selectedCrime.location_name}
                      </Text>
                    </View>
                  )}

                  {/* A "Verified Report" badge was here, gated on a `verified`
                      boolean that nothing could ever set to true. The column is gone
                      (B13): this product cannot establish that an incident happened,
                      so there was no honest way to earn the tick. What replaced it is
                      the cluster layer -- corroboration by several independent
                      people, which is a claim the system can actually make. */}

                  <View style={styles.divider} />

                  <Text style={styles.sectionLabel}>Description</Text>
                  <Text style={styles.description}>
                    {selectedCrime.description}
                  </Text>
                </ScrollView>
              </>
            )}
          </View>
      </Sheet>

      {/* JG1. The journey could not be written; the route still works. */}
      <Dialog
        visible={!!journeyNotice}
        tone="warn"
        icon="cloud-offline"
        title="Journey not recorded"
        message={`${journeyNotice ?? ''}\n\nDirections will still work, but this journey will not be here if the app restarts.`}
        actions={[{ label: 'Continue anyway', primary: true }]}
        onClose={() => setJourneyNotice(null)}
      />
    </View>
  );
};

const makeStyles = (t: Palette) =>
StyleSheet.create({
    container: {
      flex: 1,
    },
    map: {
      flex: 1,
    },
    // Risk layer status pill, top-left. Left, because the report and route buttons
    // own the top-right corner.
    /**
     * The snapped position marker: a brand dot with a white collar.
     *
     * A collar rather than a shadow, because `showsUserLocation` draws Google's own
     * blue dot in the same place and the two have to be separable at a glance --
     * one is where the phone thinks you are, the other is where that puts you on
     * the route, and the distance between them is the honest measure of the fix.
     */
    // A full-width row that only exists to centre the chip. See the note at the
    // call site for why the chip cannot centre itself.
    recentreRow: {
      position: 'absolute',
      left: 0,
      right: 0,
      alignItems: 'center',
    },
    // Small, light and out of the way: it appears only after the user has panned,
    // and it is an offer rather than a prompt.
    recentreChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.xs,
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderRadius: radius.pill,
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth * 2,
      borderColor: t.glassBorder,
      boxShadow: [{ offsetX: 0, offsetY: 4, blurRadius: 12, color: t.shadow }],
    },
    recentreText: { ...type.caption, color: t.brand },
    // JG1's resume card. Two rows inside the same `Glass` shell the search box
    // uses, so the card reads as the same family of surface rather than a new one.
    resumeRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.sm,
    },
    // `flex: 1` so the two labels ellipsize inside the row instead of pushing the
    // icon off the card. A destination label is whatever the user typed, and some
    // of them are a full address.
    resumeText: { flex: 1 },
    resumeTitle: { ...type.label, color: t.text },
    resumeDetail: { ...type.caption, color: t.textSoft },
    resumeActions: {
      flexDirection: 'row',
      justifyContent: 'flex-end',
      alignItems: 'center',
      gap: space.sm,
      marginTop: space.sm,
    },
    // End is the quieter of the two. Resuming is the expected action; ending a
    // journey the app had to ask about should take a deliberate press.
    resumeEnd: {
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderRadius: radius.pill,
      borderWidth: StyleSheet.hairlineWidth * 2,
      borderColor: t.glassBorder,
    },
    resumeEndText: { ...type.caption, color: t.textSoft },
    resumeGo: {
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderRadius: radius.pill,
      backgroundColor: t.brand,
    },
    resumeGoText: { ...type.caption, color: t.onBrand },
    riskBadge: {
      position: 'absolute',
      left: space.xl,
      flexDirection: 'row',
      alignItems: 'center',
      ...glassSurface(t),
      paddingHorizontal: space.sm,
      paddingVertical: 6,
      borderRadius: radius.pill,
      ...lift(t, 2),
    },
    riskDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
      marginRight: 6,
    },
    // `flexShrink` rather than `flex: 1`: the badge should still hug a short label
    // rather than stretching to the full width it is now allowed.
    riskBadgeLabel: {
      flexShrink: 1,
    },
    riskBadgeText: {
      ...type.caption,
      color: t.text,
    },
    riskBadgeButton: {
      marginLeft: space.sm,
      minWidth: 20,
      alignItems: 'center',
    },
    reportButton: {
      position: 'absolute',
      // `top` is set inline, below the search card. See the geometry note on
      // `fabColumnTop`; a static top here is what put it behind the card.
      right: space.xl,
      backgroundColor: t.brand,
      width: FAB_SIZE,
      height: FAB_SIZE,
      borderRadius: FAB_SIZE / 2,
      justifyContent: 'center',
      alignItems: 'center',
      ...lift(t, 4),
    },
    // Enters route mode. Keep it above the search card: it sits just below that card
    // and the card grows when a place resolves, so without this it can end up buried.
    //
    // That is not hypothetical. In route mode this button used to be the only way
    // *out*, positioned inside the route card which carries zIndex 10 and elevation 8
    // — it lost every stacking contest, could not be tapped, and left a reload as the
    // only escape. Found on a phone during D03's walkthrough with tsc, ESLint and Jest
    // all green; z-order and reachability are not things they can see.
    //
    // Both values are needed: zIndex settles it on iOS, elevation on Android.
    actionButton: {
      position: 'absolute',
      width: FAB_SIZE,
      height: FAB_SIZE,
      borderRadius: FAB_SIZE / 2,
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 11,
      ...lift(t, 4),
    },
    // Sits at the end of the source row now, where a header used to be a row of
    // its own. The left margin keeps it clear of the spinner sharing that row.
    routeClose: { marginLeft: space.sm },
    loadingOverlay: {
      ...StyleSheet.absoluteFill,  // RN 0.86 removed absoluteFillObject; absoluteFill is now the plain object
      backgroundColor: 'rgba(255, 255, 255, 0.7)',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 20,
    },
    loadingText: {
      ...type.bodyStrong,
      marginTop: space.lg,
      color: t.brand,
    },
    // The dev-only "as of" control. Sits above the SOS button rather than beside it:
    // during a demo the presenter's thumb is on this, and a mis-tap that fired an SOS
    // would be memorable for the wrong reason.
    // A column, right-aligned, so the two controls read as one control cluster
    // rather than as two more floating actions.
    mapControls: {
      position: 'absolute',
      right: space.xl,
      alignItems: 'center',
    },
    mapControl: {
      width: 44,
      height: 44,
      borderRadius: 22,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth * 2,
      borderColor: t.line,
      marginBottom: space.sm,
      ...lift(t, 3),
    },
    mapControlLast: {
      marginBottom: 0,
    },
    asOfBar: {
      position: 'absolute',
      left: space.lg,
      right: space.lg,
      ...glassSurface(t),
      borderRadius: radius.card,
      paddingVertical: space.sm,
      paddingHorizontal: space.lg,
      borderWidth: 1,
      borderColor: t.line,
      ...lift(t, 3),
    },
    asOfLabel: {
      ...type.caption,
      color: t.textSoft,
      marginBottom: space.xs,
    },
    asOfButtons: {
      flexDirection: 'row',
      gap: space.xs,
    },
    asOfButton: {
      flex: 1,
      paddingVertical: space.xs,
      paddingHorizontal: 2,
      borderRadius: radius.sm,
      backgroundColor: t.fillSoft,
      alignItems: 'center',
    },
    asOfButtonActive: {
      backgroundColor: t.brand,
    },
    asOfButtonText: {
      ...type.caption,
      color: t.textSoft,
    },
    asOfButtonTextActive: {
      color: t.onBrand,
    },
    // The scrim, the fill, the radius, the edge and the shadow are `Sheet`'s
    // now. `maxHeight` stays: a crime report can be long, and the map behind it
    // is the context the user is reading it against.
    modalContent: {
      maxHeight: '100%',
    },
    modalHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: space.xl,
    },
    categoryBadge: {
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      backgroundColor: t.bg,
      borderRadius: radius.md,
    },
    categoryText: {
      ...type.bodyStrong,
    },
    crimeTitle: {
      ...type.heading,
      color: t.text,
      marginBottom: space.lg,
    },
    infoRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: space.sm,
      gap: space.sm,
    },
    infoText: {
      ...type.body,
      color: t.textSoft,
    },
    divider: {
      height: 1,
      backgroundColor: t.fillStrong,
      marginVertical: space.xl,
    },
    sectionLabel: {
      ...type.overline,
      color: t.textFaint,
      marginBottom: space.sm,
    },
    description: {
      ...type.body,
      color: t.textSoft,
    },
    searchContainer: {
      position: 'absolute',
      left: space.xl,
      right: space.xl,
      zIndex: 10,
    },
    searchBox: {
      // No fill, border, radius OR PADDING here. `Glass` draws the first three,
      // and the fourth was a real bug: `style` lands on the SHELL and the
      // `padding` prop on the inner content box, so a padding here applies *in
      // addition* to the prop. The children were inset 32pt on every side instead
      // of 16 -- 64pt of vertical whitespace, a quarter of this card's height,
      // spent on nothing.
      //
      // Introduced by the glassmorphic migration, whose note read "what stays is
      // the padding and the elevation". The elevation was right; the padding was
      // already coming from the prop.
      borderRadius: radius.card,
    },
    inputRow: {
      flexDirection: 'row',
      alignItems: 'center',
      // 36, not 40. These are text inputs inside a card and the whole row takes
      // the tap, so the 44pt target guidance is met by the row's hit area rather
      // than by its height. Four points, twice, is eight points of map.
      height: 36,
    },
    activeInputRow: {
      backgroundColor: '#f8f9fa',
      borderRadius: radius.sm,
    },
    inputDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
      marginRight: space.lg,
    },
    sourceDot: {
      backgroundColor: t.brand,
      opacity: 0.5,
    },
    destDot: {
      backgroundColor: t.danger,
    },
    profileRow: {
      flexDirection: 'row',
      gap: space.sm,
      paddingTop: space.xs,
      marginTop: space.xs,
      borderTopWidth: 1,
      borderTopColor: t.lineSoft,
    },
    profileChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 5,
      paddingHorizontal: space.lg,
      paddingVertical: 6,
      borderRadius: radius.md,
      backgroundColor: t.fillSoft,
    },
    profileChipActive: { backgroundColor: t.brandStrong },
    profileChipText: { ...type.caption, color: t.textSoft },
    // `onBrand`, not `brandStrong`. The active chip's FILL is `brandStrong`, so
    // colouring its label the same token painted the text in the background colour
    // and the selected mode became invisible -- the one chip that most needs to be
    // readable was the only unreadable one.
    profileChipTextActive: { color: t.onBrand },
    connectorLine: {
      width: 2,
      // Purely decorative -- it says "these two fields are the ends of one
      // journey" -- so it is the first thing to give up height. Still long enough
      // to read as a line rather than as a dash.
      height: 12,
      backgroundColor: t.fillStrong,
      marginLeft: 3, // slightly offset to align with 8px dot center
      marginVertical: 1,
    },
    input: {
      ...type.body,
      flex: 1,
      color: t.text,

      // ---- why the next three lines exist ---------------------------------
      // Android's EditText arrives with its own vertical padding -- roughly
      // 4-8dp top and bottom, from the platform's text field background -- on
      // top of the 22pt line box. That measured the input at a little over
      // 40dp inside a row fixed at 36, and an Android ViewGroup clips what
      // overflows it. The ascenders had headroom to lose; the descenders did
      // not, so "Mirpur Bangla School and College" came out with the tails
      // sliced off both g's and "My Location" lost the tail of its y.
      //
      // It is invisible on iOS, where the padding is not there, which is why
      // this looked like one person's device.
      //
      // `paddingVertical: 0` removes the platform's padding, `alignSelf:
      // 'stretch'` makes the input exactly the row's 36 -- so it can no longer
      // overflow whatever the row's height becomes -- and `textAlignVertical`
      // (Android-only; iOS centres a single-line input already) keeps the text
      // on the row's centre line rather than against its top.
      paddingVertical: 0,
      alignSelf: 'stretch',
      textAlignVertical: 'center',
    },
    suggestionsContainer: {
      marginTop: space.sm,
      borderRadius: radius.md,
      maxHeight: 200,
    },
    suggestionItem: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: space.lg,
      borderBottomWidth: 1,
      borderBottomColor: t.line,
    },
    suggestionText: {
      ...type.body,
      marginLeft: space.lg,
      color: t.text,
      flex: 1,
    },
  });

export default MapScreen;
