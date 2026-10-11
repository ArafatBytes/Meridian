import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
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
import { spacing, borderRadius, fontSize } from '../../theme';
import { useTheme } from '../../theme/ThemeProvider';
import { useStyles } from '../../theme/useStyles';
import type { Palette } from '../../theme/palette';
import { glassSurface, lift } from '../../theme/surfaces';
import { Glass, Sheet } from '../../components/motion';
import { fontFamily, space } from '../../theme/type';
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
import { TAB_BAR_CLEARANCE } from '../../navigation/metrics';
import PlaceSearch from '../../components/PlaceSearch';
import { AS_OF_PRESETS, asOfSummary } from '../../features/risk/scheduled';
import type { GeoResolution } from '../../types/contracts/geo';

interface CrimeReportData {
  id: string;
  category: CrimeCategory;
  title: string;
  description: string;
  incident_date_time: string;
  latitude: string;
  longitude: string;
  location_name: string | null;
  verified: boolean;
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
 *   - the time control sat at `insets.bottom + spacing.xxl * 2` (96) while the SOS
 *     button occupies `insets.bottom + spacing.xl` upwards (32 to 112), so a
 *     full-width bar lay across the top of an 80pt emergency button;
 *   - the report and route buttons started at `insets.top + spacing.xl` (32) while
 *     the search card starts at `insets.top + spacing.xs` (4) and is ~42 tall, so
 *     the card — which has the higher zIndex — covered the top of both;
 *   - the risk badge is content-sized with no right bound, so a long label
 *     ("31 risk flags · news 4 min ago") ran underneath the SOS button.
 *
 * The fix is to name the sizes and derive the positions from them, so a button that
 * changes size moves the things around it instead of silently overlapping them.
 */
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
  const { t } = useTheme();
  const styles = useStyles(makeStyles);
  const { currentLocation, getCurrentLocation } = useLocationStore();
  const [region, setRegion] = useState(DEFAULT_MAP_REGION);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [crimeReports, setCrimeReports] = useState<CrimeReportData[]>([]);
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

  // Search State
  const [sourceLocation, setSourceLocation] = useState<Location | null>(null);
  const [sourceQuery, setSourceQuery] = useState('My Location');
  const [destQuery, setDestQuery] = useState('');

  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [activeSearch, setActiveSearch] = useState<'source' | 'destination' | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const insets = useSafeAreaInsets();
  const { width: windowWidth } = useWindowDimensions();

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


  const fetchCrimeReports = async () => {
    try {
      const { data, error } = await supabase
        .from('crime_reports')
        .select(
          'id, category, title, description, incident_date_time, latitude, longitude, location_name, verified',
        )
        .order('created_at', { ascending: false });

      if (error) throw error;
      setCrimeReports(data || []);
    } catch (error: any) {
      console.error('Error fetching crime reports:', error);
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
    try {
      const result = await riskService.getFlagsInRegion(region, asOf);
      setRiskFlags(result.flags);
      setRiskAsOf(result.asOf);
      setRiskError(null);
    } catch (error: any) {
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

  const handleMapPress = async (e: any) => {
    if (!routeMode || !currentLocation) return;

    const coord = e.nativeEvent.coordinate;
    const dest = { latitude: coord.latitude, longitude: coord.longitude };
    setDestination(dest);
    setDestQuery("Selected Location"); // Placeholder text
    calculateRouteTo(sourceLocation || currentLocation, dest);
  };

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
  const searchTop = insets.top + spacing.xs;
  const fabColumnTop = searchTop + searchHeight + spacing.sm;
  // Every bottom overlay measures from here rather than from `insets.bottom`.
  // The tab bar now floats *over* this screen instead of sitting below it, so
  // the safe floor moved up by its height — and because the geometry note above
  // derives the SOS button, the risk badge and the time control from one base,
  // changing the base keeps all three in the same relationship.
  const bottomFloor = insets.bottom + TAB_BAR_CLEARANCE;
  // What the time control has to clear. It was the top of the SOS button; with
  // that gone it is just the floor plus the badge's own row, so the control sits
  // lower and gives the map back the strip it was using.
  const overlayFloor = bottomFloor + spacing.xl + 28;
  // `maxWidth` rather than a `right` bound: setting both `left` and `right` on an
  // absolute element stretches it, so a badge reading "0 risk flags" would sit in a
  // pill the width of the screen. This hugs the label.
  //
  // It used to subtract `SOS_SIZE` to stop short of the SOS button. That button
  // is gone, so the badge gets two thirds of the width — enough for the longest
  // real label ("31 risk flags · news 4 min ago") without ellipsis.
  const riskBadgeMaxWidth = (windowWidth - spacing.lg * 2) * 0.66;

  return (
    <View style={styles.container}>
      <MapView
        provider={MAP_PROVIDER}
        style={styles.map}
        region={region}
        showsUserLocation
        showsMyLocationButton
        showsCompass
        onPress={handleMapPress}
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

        {!routeMode && crimeReports.map(crime => (
          <Marker
            key={crime.id}
            coordinate={{
              latitude: parseFloat(crime.latitude),
              longitude: parseFloat(crime.longitude),
            }}
            title={crime.title}
            description={crimeCategoryLabel(crime.category)}
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

      {/* Route Search Interface (Google Maps Style) */}
      {routeMode && (
        <View style={[styles.searchContainer, { top: searchTop }]}>
          <Glass style={styles.searchBox} padding={spacing.md} radius={borderRadius.lg} intensity={30} elevated>
            {/* The way out of route mode. It lives inside the card because the
                floating button that used to do this job sat underneath the card and
                could not be tapped, and route mode has no other exit — a reload was
                the only escape. A close control belongs on the thing it closes. */}
            <View style={styles.routeHeader}>
              <Text style={styles.routeHeaderTitle}>Plan a route</Text>
              <TouchableOpacity
                onPress={toggleRouteMode}
                hitSlop={12}
                accessibilityRole="button"
                accessibilityLabel="Close route planning"
              >
                <Ionicons name="close" size={20} color={t.textSoft} />
              </TouchableOpacity>
            </View>

            {/* Source Input */}
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
                      color={active ? t.brandStrong : t.textSoft}
                    />
                    <Text style={[styles.profileChipText, active && styles.profileChipTextActive]}>
                      {mode === 'driving' ? 'Driving' : 'Walking'}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </Glass>

          {/* Suggestions List */}
          {suggestions.length > 0 && (
            <Glass style={styles.suggestionsContainer} padding={0} radius={borderRadius.md} elevated>
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
              right: spacing.lg,
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
      {routeMode && calculatedRoutes.length > 0 && (
        <RouteComparisonCard
          routes={calculatedRoutes}
          selectedIndex={selectedRouteIndex}
          onSelect={setSelectedRouteIndex}
          bottomInset={bottomFloor}
        />
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
              bottom: bottomFloor + spacing.xl,
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
                [`${riskFlags.length} risk flags`, newsLabel(ingestion, isFetchingNews)]
                  .filter(Boolean)
                  .join(' · ')}
            </Text>
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
        <View style={[styles.asOfBar, { bottom: overlayFloor + spacing.sm }]}>
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

                  {selectedCrime.verified && (
                    <View style={styles.verifiedBadge}>
                      <Ionicons
                        name="checkmark-circle"
                        size={16}
                        color={t.ok}
                      />
                      <Text style={styles.verifiedText}>Verified Report</Text>
                    </View>
                  )}

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
    riskBadge: {
      position: 'absolute',
      left: spacing.lg,
      flexDirection: 'row',
      alignItems: 'center',
      ...glassSurface(t),
      paddingHorizontal: spacing.sm,
      paddingVertical: 6,
      borderRadius: borderRadius.full,
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
      fontFamily: fontFamily.bodySemi,
      color: t.text,
      fontSize: fontSize.xs,
    },
    riskBadgeButton: {
      marginLeft: spacing.sm,
      minWidth: 20,
      alignItems: 'center',
    },
    reportButton: {
      position: 'absolute',
      // `top` is set inline, below the search card. See the geometry note on
      // `fabColumnTop`; a static top here is what put it behind the card.
      right: spacing.lg,
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
    routeHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginBottom: spacing.sm,
    },
    routeHeaderTitle: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.sm,
      color: t.text,
    },
    loadingOverlay: {
      ...StyleSheet.absoluteFill,  // RN 0.86 removed absoluteFillObject; absoluteFill is now the plain object
      backgroundColor: 'rgba(255, 255, 255, 0.7)',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 20,
    },
    loadingText: {
      fontFamily: fontFamily.bodySemi,
      marginTop: spacing.md,
      fontSize: fontSize.md,
      color: t.brand,
    },
    // The dev-only "as of" control. Sits above the SOS button rather than beside it:
    // during a demo the presenter's thumb is on this, and a mis-tap that fired an SOS
    // would be memorable for the wrong reason.
    asOfBar: {
      position: 'absolute',
      left: spacing.md,
      right: spacing.md,
      ...glassSurface(t),
      borderRadius: borderRadius.lg,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderWidth: 1,
      borderColor: t.line,
      ...lift(t, 3),
    },
    asOfLabel: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.xs,
      color: t.textSoft,
      marginBottom: spacing.xs,
    },
    asOfButtons: {
      flexDirection: 'row',
      gap: spacing.xs,
    },
    asOfButton: {
      flex: 1,
      paddingVertical: spacing.xs,
      paddingHorizontal: 2,
      borderRadius: borderRadius.sm,
      backgroundColor: t.fillSoft,
      alignItems: 'center',
    },
    asOfButtonActive: {
      backgroundColor: t.brand,
    },
    asOfButtonText: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.xs,
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
      marginBottom: spacing.lg,
    },
    categoryBadge: {
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      backgroundColor: t.bg,
      borderRadius: borderRadius.md,
    },
    categoryText: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.md,
    },
    crimeTitle: {
      fontFamily: fontFamily.display,
      fontSize: fontSize.xl,
      color: t.text,
      marginBottom: spacing.md,
    },
    infoRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginBottom: spacing.sm,
      gap: spacing.sm,
    },
    infoText: {
      fontFamily: fontFamily.body,
      fontSize: fontSize.md,
      color: t.textSoft,
    },
    verifiedBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: t.ok,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderRadius: borderRadius.md,
      alignSelf: 'flex-start',
      marginTop: spacing.sm,
      gap: spacing.xs,
    },
    verifiedText: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.sm,
      color: t.ok,
    },
    divider: {
      height: 1,
      backgroundColor: t.fillStrong,
      marginVertical: spacing.lg,
    },
    sectionLabel: {
      fontFamily: fontFamily.bodySemi,
      fontSize: fontSize.md,
      color: t.text,
      marginBottom: spacing.sm,
    },
    description: {
      fontFamily: fontFamily.body,
      fontSize: fontSize.md,
      color: t.textSoft,
      lineHeight: 22,
    },
    searchContainer: {
      position: 'absolute',
      left: spacing.lg,
      right: spacing.lg,
      zIndex: 10,
    },
    searchBox: {
      // No fill, border or radius here: `Glass` draws all three. What stays is
      // the padding. The lift is `Glass`'s own `elevated`, which it applies on
      // request -- so this does not add one of its own.
      borderRadius: borderRadius.lg,
      padding: spacing.md,
    },
    inputRow: {
      flexDirection: 'row',
      alignItems: 'center',
      height: 40,
    },
    activeInputRow: {
      backgroundColor: '#f8f9fa',
      borderRadius: borderRadius.sm,
    },
    inputDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
      marginRight: spacing.md,
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
      gap: spacing.sm,
      paddingTop: spacing.sm,
      marginTop: spacing.xs,
      borderTopWidth: 1,
      borderTopColor: t.lineSoft,
    },
    profileChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 5,
      paddingHorizontal: spacing.md,
      paddingVertical: 6,
      borderRadius: borderRadius.md,
      backgroundColor: t.fillSoft,
    },
    profileChipActive: { backgroundColor: t.brandStrong },
    profileChipText: { fontFamily: fontFamily.bodySemi, fontSize: fontSize.xs, color: t.textSoft,},
    profileChipTextActive: { color: t.brandStrong },
    connectorLine: {
      width: 2,
      height: 20,
      backgroundColor: t.fillStrong,
      marginLeft: 3, // slightly offset to align with 8px dot center
      marginVertical: 2,
    },
    input: {
      fontFamily: fontFamily.body,
      flex: 1,
      fontSize: fontSize.md,
      color: t.text,
    },
    suggestionsContainer: {
      marginTop: spacing.sm,
      borderRadius: borderRadius.md,
      maxHeight: 200,
    },
    suggestionItem: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: spacing.md,
      borderBottomWidth: 1,
      borderBottomColor: t.line,
    },
    suggestionText: {
      fontFamily: fontFamily.body,
      marginLeft: spacing.md,
      fontSize: fontSize.md,
      color: t.text,
      flex: 1,
    },
  });

export default MapScreen;
