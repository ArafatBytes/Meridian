import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Text,
  Alert,
  Modal,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Keyboard,
  Platform,
} from 'react-native';

import MapView, {
  Marker,
  MAP_PROVIDER,
  Polyline,
  Circle,
} from '../../components/MapComponent';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { CompositeNavigationProp } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { NavigationProp } from '@react-navigation/native';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useLocationStore } from '../../store';
import { DEFAULT_MAP_REGION } from '../../constants';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { supabase } from '../../lib/supabase';
import { CrimeCategory, MainTabParamList } from '../../types';
import { crimeCategoryLabel } from '../../types/contracts/crime';
import type { RiskFlag } from '../../types/contracts/risk';
import { routeService, RouteResponse, Location } from '../../services/route.service';
import { riskService } from '../../services/risk.service';

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
 * Severity bands, in the order they are tested.
 *
 * Keyed off `severity0` — severity at the moment the flag was observed. D02 adds
 * decay on read, at which point this colours the severity *now* and a fading flag
 * visibly changes colour. Four bands rather than a continuous gradient because a
 * pin is small and a judge should be able to read it from across a room.
 */
const RISK_SEVERITY_BANDS: { min: number; color: string; label: string }[] = [
  { min: 70, color: '#D32F2F', label: 'Severe' },
  { min: 50, color: '#F57C00', label: 'High' },
  { min: 30, color: '#FBC02D', label: 'Moderate' },
  { min: 0, color: '#78909C', label: 'Low' },
];

const riskBand = (severity: number) =>
  RISK_SEVERITY_BANDS.find(band => severity >= band.min) ??
  RISK_SEVERITY_BANDS[RISK_SEVERITY_BANDS.length - 1];

/**
 * Hex colour plus an alpha channel, for the radius circles.
 *
 * `react-native-maps` takes rgba strings for fill and stroke. Eight-digit hex is
 * accepted on both platforms and keeps the band table in one notation.
 */
const withAlpha = (hex: string, alpha: string) => `${hex}${alpha}`;

// Colors for routes based on safety score
const getRouteColor = (safetyScore: number) => {
  if (safetyScore >= 80) return colors.success; // Green (Safe)
  if (safetyScore >= 50) return colors.warning; // Yellow (Moderate)
  return colors.error; // Red (Unsafe)
};

type MapScreenNavigationProp = CompositeNavigationProp<
  BottomTabNavigationProp<MainTabParamList, 'Map'>,
  NavigationProp<any>
>;

interface Props {
  navigation: MapScreenNavigationProp;
}

const MapScreen: React.FC<Props> = ({ navigation }) => {
  const { currentLocation, getCurrentLocation } = useLocationStore();
  const [region, setRegion] = useState(DEFAULT_MAP_REGION);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [crimeReports, setCrimeReports] = useState<CrimeReportData[]>([]);
  const [riskFlags, setRiskFlags] = useState<RiskFlag[]>([]);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [selectedCrime, setSelectedCrime] = useState<CrimeReportData | null>(
    null,
  );
  const [isModalVisible, setIsModalVisible] = useState(false);

  // Routing State
  const [routeMode, setRouteMode] = useState(false);
  const [destination, setDestination] = useState<Location | null>(null);
  const [calculatedRoutes, setCalculatedRoutes] = useState<RouteResponse[]>([]);
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
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`,
      );
      const data = await response.json();
      setSuggestions(data);
    } catch (error) {
      console.log('Error fetching suggestions:', error);
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

  const calculateRouteTo = async (start: Location | null, end: Location) => {
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
        avoid_high_crime_zones: true
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
  const fetchRiskFlags = async (asOf?: Date) => {
    try {
      const result = await riskService.getFlagsInRegion(region, asOf);
      setRiskFlags(result.flags);
      setRiskError(null);
    } catch (error: any) {
      // Not fatal: the crime layer and routing still work without it.
      console.warn('Risk flags unavailable:', error?.message ?? error);
      setRiskError('Risk layer unavailable');
    }
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
  // map fighting the user. D04 replaces this with explicit pull-to-refresh.
  useEffect(() => {
    fetchRiskFlags();
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

  const handleSOSPress = () => {
    Alert.alert(
      'SOS Emergency',
      'Are you sure you want to activate SOS alert?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Activate',
          style: 'destructive',
          onPress: () => {
            // TODO: Implement SOS activation
            Alert.alert(
              'SOS Activated',
              'Emergency contacts have been notified',
            );
          },
        },
      ],
    );
  };

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

        {/* Routes */}
        {calculatedRoutes.map((route, index) => {
          const isSelected = index === selectedRouteIndex;
          return (
            <Polyline
              key={route.route_id}
              coordinates={route.path.map(p => ({ latitude: p.latitude, longitude: p.longitude }))}
              strokeColor={index === 0 ? '#2196F3' : index === 1 ? '#FFC107' : '#B0BEC5'}
              strokeWidth={isSelected ? 5 : 3}
              onPress={() => setSelectedRouteIndex(index)}
              tappable={true}
              lineDashPattern={isSelected ? undefined : [10, 5]}
              zIndex={isSelected ? 10 : 1}
            />
          );
        })}

        {/* Risk flag radius circles.
            Drawn before the markers so the pins sit on top of them. A flag is a
            claim about an AREA — a bare pin would overstate how precisely the
            location is known. */}
        {!routeMode && riskFlags.map(flag => {
          const band = riskBand(flag.severity0);
          return (
            <Circle
              key={`risk-circle-${flag.flagId}`}
              center={{ latitude: flag.lat, longitude: flag.lon }}
              radius={flag.radiusM}
              strokeWidth={1}
              strokeColor={withAlpha(band.color, '99')}
              fillColor={withAlpha(band.color, '26')}
            />
          );
        })}

        {/* Risk flag pins.
            The callout text is `mobilityStatement` and nothing else. It is the
            only user-facing string the server produced through
            app/policy/framing.py, and building a label from `kind` here would put
            the word "clash" on a map that has committed not to say it. */}
        {!routeMode && riskFlags.map(flag => {
          const band = riskBand(flag.severity0);
          return (
            <Marker
              key={`risk-${flag.flagId}`}
              coordinate={{ latitude: flag.lat, longitude: flag.lon }}
              title={flag.mobilityStatement}
              description={`${band.label} · ${Math.round(flag.severity0)}/100 · ${
                flag.status === 'confirmed'
                  ? `${flag.sourceCount} sources`
                  : 'unconfirmed'
              }`}
              pinColor={band.color}
            />
          );
        })}

        {/* Crime Report Markers */}
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

      {/* Route Search Interface (Google Maps Style) */}
      {routeMode && (
        <View style={[styles.searchContainer, { top: insets.top + spacing.xs }]}>
          <View style={styles.searchBox}>
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
                placeholderTextColor={colors.textSecondary}
                selectTextOnFocus
              />
              {activeSearch === 'source' && isSearching && <ActivityIndicator size="small" color={colors.primary} />}
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
                placeholderTextColor={colors.textSecondary}
                autoFocus={true}
              />
              {activeSearch === 'destination' && isSearching && <ActivityIndicator size="small" color={colors.primary} />}
            </View>
          </View>

          {/* Suggestions List */}
          {suggestions.length > 0 && (
            <View style={styles.suggestionsContainer}>
              <ScrollView keyboardShouldPersistTaps="always">
                {suggestions.map((item, index) => (
                  <TouchableOpacity
                    key={index}
                    style={styles.suggestionItem}
                    onPress={() => handleSuggestionSelect(item)}
                  >
                    <Ionicons name="location-outline" size={20} color={colors.textSecondary} />
                    <Text style={styles.suggestionText}>{item.display_name}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}
        </View>
      )}

      {/* SOS Button (Hide in route mode) */}
      {!routeMode && (
        <TouchableOpacity
          style={[styles.sosButton, { bottom: insets.bottom + spacing.xl }]}
          onPress={handleSOSPress}
          activeOpacity={0.8}
        >
          <MaterialCommunityIcons
            name="alarm-light"
            size={32}
            color={colors.white}
          />
          <Text style={styles.sosButtonText}>SOS</Text>
        </TouchableOpacity>
      )}

      {/* Report Button (Hide in route mode) */}
      {!routeMode && (
        <TouchableOpacity
          style={[styles.reportButton, { top: insets.top + spacing.xl }]}
          onPress={() => {
            navigation.navigate('Reports');
            setTimeout(() => {
              navigation.navigate('AddReport');
            }, 100);
          }}
        >
          <Ionicons name="warning" size={24} color={colors.white} />
        </TouchableOpacity>
      )}

      {/* Route Button */}
      <TouchableOpacity
        style={[
          styles.actionButton,
          {
            top: insets.top + spacing.xl + (routeMode ? 0 : 70),
            right: spacing.lg,
            backgroundColor: routeMode ? colors.error : colors.primary
          }
        ]}
        onPress={toggleRouteMode}
      >
        <Ionicons name={routeMode ? "close" : "navigate"} size={24} color={colors.white} />
      </TouchableOpacity>

      {/* Route Info Card */}
      {routeMode && calculatedRoutes.length > 0 && (
        <View style={[styles.routeInfoCard, { bottom: insets.bottom + spacing.md }]}>
          <Text style={styles.routeTitle}>
            Route {selectedRouteIndex + 1} of {calculatedRoutes.length}
          </Text>

          <View style={styles.routeStatsRow}>
            <View style={styles.routeStat}>
              <Ionicons name="shield-checkmark" size={20} color={getRouteColor(calculatedRoutes[selectedRouteIndex].safety_score)} />
              <Text style={[styles.statValue, { color: getRouteColor(calculatedRoutes[selectedRouteIndex].safety_score) }]}>
                {calculatedRoutes[selectedRouteIndex].safety_score.toFixed(1)}% Safe
              </Text>
            </View>

            <View style={styles.routeStat}>
              <Ionicons name="time-outline" size={20} color={colors.text} />
              <Text style={styles.statValue}>
                {calculatedRoutes[selectedRouteIndex].duration_minutes} min
              </Text>
            </View>

            <View style={styles.routeStat}>
              <MaterialCommunityIcons name="map-marker-distance" size={20} color={colors.text} />
              <Text style={styles.statValue}>
                {calculatedRoutes[selectedRouteIndex].distance_km.toFixed(1)} km
              </Text>
            </View>
          </View>

          <Text style={styles.routeDescription}>
            {selectedRouteIndex === 0 ? "Recommended: Best balance of safety and distance." :
              calculatedRoutes[selectedRouteIndex].safety_score > calculatedRoutes[0].safety_score ? "Safest option available." : "Alternative route."}
          </Text>

          <View style={styles.routeSelectionDots}>
            {calculatedRoutes.map((_, i) => (
              <TouchableOpacity
                key={i}
                style={[styles.dot, i === selectedRouteIndex && styles.activeDot]}
                onPress={() => setSelectedRouteIndex(i)}
              />
            ))}
          </View>
        </View>
      )}

      {/* Risk layer status.
          Small, but it is what turns "the map looks the same as yesterday" into a
          readable answer: either a flag count, or the reason there is none. */}
      {!routeMode && (
        <View style={[styles.riskBadge, { top: insets.top + spacing.xs }]}>
          <View
            style={[
              styles.riskDot,
              { backgroundColor: riskError ? colors.error : colors.success },
            ]}
          />
          <Text style={styles.riskBadgeText}>
            {riskError ?? `${riskFlags.length} risk flags`}
          </Text>
        </View>
      )}

      {/* Loading Indicator */}
      {isRouting && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Calculating safest route...</Text>
        </View>
      )}

      {/* Crime Details Modal */}
      <Modal
        visible={isModalVisible}
        transparent
        animationType="slide"
        onRequestClose={closeModal}
      >
        <View style={styles.modalOverlay}>
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
                    <Ionicons name="close" size={28} color={colors.text} />
                  </TouchableOpacity>
                </View>

                <ScrollView showsVerticalScrollIndicator={false}>
                  <Text style={styles.crimeTitle}>{selectedCrime.title}</Text>

                  <View style={styles.infoRow}>
                    <Ionicons
                      name="time-outline"
                      size={18}
                      color={colors.textSecondary}
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
                        color={colors.textSecondary}
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
                        color={colors.success}
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
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
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
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: borderRadius.full,
    elevation: 3,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
  },
  riskDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  riskBadgeText: {
    color: colors.text,
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  sosButton: {
    position: 'absolute',
    bottom: spacing.xl,
    right: spacing.lg,
    backgroundColor: colors.error,
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 8,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
  },
  sosButtonText: {
    color: colors.white,
    fontSize: 12,
    fontWeight: 'bold',
    marginTop: 4,
  },
  reportButton: {
    position: 'absolute',
    top: spacing.xl,
    right: spacing.lg,
    backgroundColor: colors.primary,
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  actionButton: {
    position: 'absolute',
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  routeInfoCard: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    elevation: 8,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
  },
  routeTitle: {
    fontSize: fontSize.md,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  routeStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: spacing.sm,
  },
  routeStat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statValue: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  routeDescription: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  routeSelectionDots: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.border,
  },
  activeDot: {
    backgroundColor: colors.primary,
    width: 20,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFill,  // RN 0.86 removed absoluteFillObject; absoluteFill is now the plain object
    backgroundColor: 'rgba(255, 255, 255, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 20,
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.primary,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.white,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    padding: spacing.xl,
    maxHeight: '70%',
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
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
  },
  categoryText: {
    fontSize: fontSize.md,
    fontWeight: 'bold',
  },
  crimeTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
    marginBottom: spacing.md,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  infoText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  verifiedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.successLight,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    alignSelf: 'flex-start',
    marginTop: spacing.sm,
    gap: spacing.xs,
  },
  verifiedText: {
    fontSize: fontSize.sm,
    color: colors.success,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.lg,
  },
  sectionLabel: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  description: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  searchContainer: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    zIndex: 10,
  },
  searchBox: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    elevation: 8,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
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
    backgroundColor: colors.primary,
    opacity: 0.5,
  },
  destDot: {
    backgroundColor: colors.error,
  },
  connectorLine: {
    width: 2,
    height: 20,
    backgroundColor: colors.border,
    marginLeft: 3, // slightly offset to align with 8px dot center
    marginVertical: 2,
  },
  input: {
    flex: 1,
    fontSize: fontSize.md,
    color: colors.text,
  },
  suggestionsContainer: {
    marginTop: spacing.sm,
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    elevation: 4,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    maxHeight: 200,
  },
  suggestionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  suggestionText: {
    marginLeft: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    flex: 1,
  },
});

export default MapScreen;
