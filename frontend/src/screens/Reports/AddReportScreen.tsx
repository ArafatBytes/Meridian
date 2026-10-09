import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Image,
} from 'react-native';
import MapView, {
  Marker,
  MAP_PROVIDER,
} from '../../components/MapComponent';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import DateTimePicker, {
  DateTimePickerChangeEvent,
} from '@react-native-community/datetimepicker';
import * as ImagePicker from 'expo-image-picker';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useLocationStore } from '../../store';
import { DEFAULT_MAP_REGION } from '../../constants';
import { crimeService, CrimeAnalysisResult } from '../../services';
import { geoService } from '../../services/geo.service';

/**
 * Which tier answered, in words a judge can read off the screen.
 *
 * Shown for `gemini` and `ollama`, and **not** for `replay` -- the owner's call
 * on 2026-10-10. D06 labels a fallback route and D05 labels its synthetic
 * source; this is the one place that rule is not followed, so it is written
 * down rather than left to be inferred from a missing element.
 */
const ENGINE_LABEL: Record<string, string> = {
  gemini: 'live',
  replay: 'rehearsed',
  ollama: 'on this device',
  none: 'unavailable',
};

/** The seven cues, in the order the model answers them. */
const CUE_ORDER: Array<[string, string]> = [
  ['physical_confrontation', 'Physical confrontation'],
  ['weapon_visible', 'Weapon visible'],
  ['property_damage', 'Property damage'],
  ['forced_entry', 'Forced entry'],
  ['unwanted_pursuit', 'Unwanted pursuit'],
  ['struggle_over_property', 'Struggle over property'],
  ['goods_concealed', 'Goods concealed'],
];

const CUE_ICON: Record<string, any> = {
  yes: 'alert-circle',
  no: 'minus-circle-outline',
  unclear: 'help-circle-outline',
};

// `unclear` is amber rather than grey: it is a real answer the model gave, not a
// missing one, and it is the honest result for most ambiguous photos.
const CUE_COLOUR: Record<string, string> = {
  yes: colors.danger,
  no: colors.textSecondary,
  unclear: colors.warning,
};

interface AddReportScreenProps {
  navigation: any;
}

const CRIME_CATEGORIES = [
  { id: 'theft', label: 'Theft', icon: 'bag-personal-outline' },
  { id: 'assault', label: 'Assault', icon: 'hand-back-right-outline' },
  { id: 'harassment', label: 'Harassment', icon: 'account-alert-outline' },
  { id: 'vandalism', label: 'Vandalism', icon: 'hammer-wrench' },
  { id: 'burglary', label: 'Burglary', icon: 'home-alert-outline' },
  { id: 'robbery', label: 'Robbery', icon: 'wallet-outline' },
  { id: 'fraud', label: 'Fraud', icon: 'credit-card-off-outline' },
  { id: 'other', label: 'Other', icon: 'alert-circle-outline' },
];

const AddReportScreen: React.FC<AddReportScreenProps> = ({ navigation }) => {
  const insets = useSafeAreaInsets();
  const { currentLocation, getCurrentLocation } = useLocationStore();

  const [selectedCategory, setSelectedCategory] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [incidentDateTime, setIncidentDateTime] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [locationName, setLocationName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLocation, setSelectedLocation] = useState<{
    latitude: number;
    longitude: number;
  } | null>(null);
  const [region, setRegion] = useState(DEFAULT_MAP_REGION);
  const [isFetchingLocation, setIsFetchingLocation] = useState(false);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetchingLocationName, setIsFetchingLocationName] = useState(false);
  const [isFetchingSuggestions, setIsFetchingSuggestions] = useState(false);

  // AI Crime Detection State
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [showAIResults, setShowAIResults] = useState(false);

  useEffect(() => {
    // The store re-throws after storing the error, so this promise must be
    // handled or a denied permission becomes an uncaught rejection red-box.
    // The screen is still usable without a fix -- the user picks a point on the
    // map instead -- so this is a soft failure, not an alert.
    getCurrentLocation().catch(() => {
      // Intentionally quiet: locationStore already holds the message, and the
      // map defaults to DEFAULT_MAP_REGION.
    });
    // Request camera permissions
    (async () => {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        console.log('Camera permission not granted');
      }
    })();
  }, []);

  // Debounced search suggestions
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery.trim() && searchQuery.length >= 3) {
        fetchSuggestions(searchQuery);
      } else {
        setSuggestions([]);
        setShowSuggestions(false);
        setIsFetchingSuggestions(false);
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  useEffect(() => {
    if (currentLocation) {
      setRegion({
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
        latitudeDelta: 0.01,
        longitudeDelta: 0.01,
      });
      setSelectedLocation({
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
      });
    }
  }, [currentLocation]);

  const handleMapPress = async (event: any) => {
    const { coordinate } = event.nativeEvent;
    setSelectedLocation(coordinate);
    setLocationName(''); // Clear previous location name
    setIsFetchingLocationName(true); // Start loading

    // Reverse geocoding to get location name
    try {
      // D06, defect 10 — through the server proxy. This handler fires on every map tap,
      // so it was the worst of the four offenders: one person choosing a location could
      // issue dozens of identical uncached requests from the device.
      const name = await geoService.reverse(coordinate.latitude, coordinate.longitude);
      setLocationName(name ?? 'Location address not available');
    } finally {
      setIsFetchingLocationName(false); // Stop loading
    }
  };

  const fetchSuggestions = async (query: string) => {
    setIsFetchingSuggestions(true);
    try {
      // D06, defect 10 — through the server proxy. `geoService.search` returns [] rather
      // than throwing when the geocoder is unreachable, which is why there is no catch:
      // no suggestions is a usable state.
      const results = await geoService.search(query);
      setSuggestions(results);
      setShowSuggestions(results.length > 0);
    } finally {
      setIsFetchingSuggestions(false);
    }
  };

  const handleSuggestionSelect = (suggestion: any) => {
    const coordinate = {
      latitude: parseFloat(suggestion.lat),
      longitude: parseFloat(suggestion.lon),
    };

    setSelectedLocation(coordinate);
    setLocationName(suggestion.display_name);
    setRegion({
      latitude: coordinate.latitude,
      longitude: coordinate.longitude,
      latitudeDelta: 0.01,
      longitudeDelta: 0.01,
    });
    setSearchQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    // Close suggestions immediately and clear them
    setShowSuggestions(false);
    setSuggestions([]);

    try {
      // Perform a fresh search with the exact query typed by user.
      // D06, defect 10 — through the server proxy. The proxy already parses lat/lon to
      // numbers, so the parseFloat round-trip through strings is gone with it.
      const data = await geoService.search(searchQuery);

      if (data && data.length > 0) {
        const location = data[0];
        const coordinate = {
          latitude: location.lat,
          longitude: location.lon,
        };

        setSelectedLocation(coordinate);
        // `display_name` is nullable — Nominatim does not always have a name for a
        // result. The old untyped `fetch` made this `any`, so a null would have gone
        // straight into a string state; typing the proxy's response surfaced it.
        setLocationName(location.display_name ?? 'Location address not available');
        setRegion({
          latitude: coordinate.latitude,
          longitude: coordinate.longitude,
          latitudeDelta: 0.01,
          longitudeDelta: 0.01,
        });
        setSearchQuery(''); // Clear search bar after successful search
      } else {
        Alert.alert(
          'Not Found',
          'Location not found. Please try a different search term.',
        );
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to search location. Please try again.');
    }
  };

  const formatDateTime = (date: Date) => {
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${day}/${month}/${year} at ${hours}:${minutes}`;
  };

  // DateTimePicker 9.x deprecated `onChange` in favour of `onValueChange` plus
  // a separate `onDismiss`. Two things follow from that and both simplify this
  // code: `date` is no longer optional, and dismissal no longer reaches these
  // handlers at all, so the old `event.type !== 'dismissed'` guard is gone.
  const handleDateChange = (
    _event: DateTimePickerChangeEvent,
    selectedDate: Date,
  ) => {
    if (Platform.OS === 'android') {
      setShowDatePicker(false);
    }

    // Changing the date must not change the time, so carry the existing
    // hours/minutes across -- except when the result would be in the future
    // on today's date, in which case clamp to now.
    const newDateTime = new Date(selectedDate.getTime());
    const now = new Date();
    const isToday =
      selectedDate.getDate() === now.getDate() &&
      selectedDate.getMonth() === now.getMonth() &&
      selectedDate.getFullYear() === now.getFullYear();
    const keptMinutes =
      incidentDateTime.getHours() * 60 + incidentDateTime.getMinutes();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();

    if (isToday && keptMinutes > nowMinutes) {
      newDateTime.setHours(now.getHours(), now.getMinutes(), 0, 0);
    } else {
      newDateTime.setHours(
        incidentDateTime.getHours(),
        incidentDateTime.getMinutes(),
        0,
        0,
      );
    }
    setIncidentDateTime(newDateTime);
  };

  const handleTimeChange = (
    _event: DateTimePickerChangeEvent,
    selectedTime: Date,
  ) => {
    if (Platform.OS === 'android') {
      setShowTimePicker(false);
    }
    // Keep the date, replace only the time.
    const newDateTime = new Date(incidentDateTime.getTime());
    newDateTime.setHours(
      selectedTime.getHours(),
      selectedTime.getMinutes(),
      0,
      0,
    );
    setIncidentDateTime(newDateTime);
  };

  // ============================================================================
  // AI CRIME DETECTION FUNCTIONS
  // ============================================================================

  const handleTakePhoto = async () => {
    try {
      const permissionResult =
        await ImagePicker.requestCameraPermissionsAsync();

      if (permissionResult.granted === false) {
        Alert.alert(
          'Permission Required',
          'Camera access is needed to capture crime scene photos.',
        );
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ['images'], // MediaTypeOptions is deprecated in SDK 57
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets[0]) {
        const imageUri = result.assets[0].uri;
        setCapturedImage(imageUri);

        // Automatically analyze the image
        await analyzeImage(imageUri);
      }
    } catch (error: any) {
      Alert.alert('Error', 'Failed to capture photo: ' + error.message);
    }
  };

  const handlePickImage = async () => {
    try {
      const permissionResult =
        await ImagePicker.requestMediaLibraryPermissionsAsync();

      if (permissionResult.granted === false) {
        Alert.alert(
          'Permission Required',
          'Photo library access is needed to select crime scene photos.',
        );
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'], // MediaTypeOptions is deprecated in SDK 57
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets[0]) {
        const imageUri = result.assets[0].uri;
        setCapturedImage(imageUri);

        // Automatically analyze the image
        await analyzeImage(imageUri);
      }
    } catch (error: any) {
      Alert.alert('Error', 'Failed to pick image: ' + error.message);
    }
  };

  const analyzeImage = async (imageUri: string) => {
    setIsAnalyzing(true);
    setShowAIResults(false);

    try {
      // The description the reporter has typed so far feeds the corroboration
      // cross-check. Empty is fine and common.
      const result = await crimeService.analyzeCrimeImage(imageUri, description);

      if (!result.success) {
        setShowAIResults(false);
        Alert.alert(
          'Could not analyse the photo',
          (result.message || 'No analysis is available right now.') +
            '\n\nYour photo will still be attached. Please fill the form in yourself.',
          [{ text: 'OK' }],
        );
        return;
      }

      setAnalysisResult(result);
      setShowAIResults(true);

      // Only ever a suggestion, and only when our own rules proposed one. The
      // category that gets filed is whatever the reporter leaves in the form.
      if (result.proposed_category) {
        setSelectedCategory(result.proposed_category);
      }
      // The model's sentence is a starting point for the description, never a
      // replacement for what the reporter already wrote.
      if (result.description && !description.trim()) {
        setDescription(result.description);
      }
    } catch (error: any) {
      setShowAIResults(false);
      Alert.alert(
        'Could not analyse the photo',
        (error.message || 'Something went wrong.') +
          '\n\nYour photo will still be attached.',
        [{ text: 'OK' }],
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRemoveImage = () => {
    setCapturedImage(null);
    setAnalysisResult(null);
    setShowAIResults(false);

    // Clear pre-filled form data
    setSelectedCategory('');
    setTitle('');
    setDescription('');
  };

  const showImageOptions = () => {
    Alert.alert(
      'Add Crime Scene Photo',
      'Choose an option to add a photo for AI analysis',
      [
        {
          text: 'Take Photo',
          onPress: handleTakePhoto,
        },
        {
          text: 'Choose from Library',
          onPress: handlePickImage,
        },
        {
          text: 'Cancel',
          style: 'cancel',
        },
      ],
    );
  };

  // ============================================================================
  // END AI FUNCTIONS
  // ============================================================================

  const handleSubmit = async () => {
    // Validation
    if (!selectedCategory) {
      Alert.alert('Error', 'Please select a crime category');
      return;
    }
    if (!title.trim()) {
      Alert.alert('Error', 'Please enter a title');
      return;
    }
    if (!description.trim()) {
      Alert.alert('Error', 'Please provide a description');
      return;
    }
    if (!selectedLocation) {
      Alert.alert('Error', 'Please select a location on the map');
      return;
    }

    setIsSubmitting(true);

    try {
      // Convert local time to ISO string while preserving the intended time
      // User picks time in Bangladesh (GMT+6), we need to store that exact time as UTC
      const year = incidentDateTime.getFullYear();
      const month = String(incidentDateTime.getMonth() + 1).padStart(2, '0');
      const day = String(incidentDateTime.getDate()).padStart(2, '0');
      const hours = String(incidentDateTime.getHours()).padStart(2, '0');
      const minutes = String(incidentDateTime.getMinutes()).padStart(2, '0');
      const seconds = String(incidentDateTime.getSeconds()).padStart(2, '0');

      // Format as ISO string but treat the picked time as if it's UTC
      // This preserves the exact time the user selected
      const isoString = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}.000Z`;

      // Get current time in Bangladesh timezone (GMT+6) for created_at
      const now = new Date();
      const nowYear = now.getFullYear();
      const nowMonth = String(now.getMonth() + 1).padStart(2, '0');
      const nowDay = String(now.getDate()).padStart(2, '0');
      const nowHours = String(now.getHours()).padStart(2, '0');
      const nowMinutes = String(now.getMinutes()).padStart(2, '0');
      const nowSeconds = String(now.getSeconds()).padStart(2, '0');
      const createdAtString = `${nowYear}-${nowMonth}-${nowDay}T${nowHours}:${nowMinutes}:${nowSeconds}.000Z`;

      // Submit report to Supabase
      await crimeService.submitReport({
        category: selectedCategory,
        title: title.trim(),
        description: description.trim(),
        incident_date_time: isoString,
        latitude: selectedLocation.latitude.toString(),
        longitude: selectedLocation.longitude.toString(),
        location_name: locationName || undefined,
        created_at: createdAtString, // Manual timestamp in local time
        // D07: the photo was uploaded during analysis, so only the path travels
        // here. Both are null when there was no photo, or when no tier answered.
        evidence_photo_path: analysisResult?.evidence_photo_path ?? null,
        vision_analysis: analysisResult?.success
          ? {
              engine: analysisResult.engine,
              description: analysisResult.description,
              people_count: analysisResult.people_count,
              scene: analysisResult.scene,
              cues: analysisResult.cues,
              cues_fired: analysisResult.cues_fired,
              proposed_category: analysisResult.proposed_category,
              confidence: analysisResult.confidence,
              reason: analysisResult.reason,
              agreement: analysisResult.agreement,
              // What the reporter actually chose. The whole point of the review
              // gate is that this can differ from proposed_category.
              filed_category: selectedCategory,
              elapsed_seconds: analysisResult.elapsed_seconds,
            }
          : null,
      });

      Alert.alert('Success', 'Your report has been submitted successfully', [
        {
          text: 'OK',
          onPress: () => navigation.goBack(),
        },
      ]);
    } catch (error: any) {
      Alert.alert(
        'Submission Failed',
        error.message || 'Failed to submit report. Please try again.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUseCurrentLocation = async () => {
    setIsFetchingLocation(true);
    try {
      await getCurrentLocation();
      if (currentLocation) {
        setSelectedLocation({
          latitude: currentLocation.latitude,
          longitude: currentLocation.longitude,
        });
        setRegion({
          latitude: currentLocation.latitude,
          longitude: currentLocation.longitude,
          latitudeDelta: 0.01,
          longitudeDelta: 0.01,
        });

        // Reverse geocode to get location name
        setLocationName(''); // Clear previous location name
        setIsFetchingLocationName(true); // Start loading
        try {
          // D06, defect 10 — through the server proxy.
          const name = await geoService.reverse(
            currentLocation.latitude,
            currentLocation.longitude,
          );
          setLocationName(name ?? 'Location address not available');
        } finally {
          setIsFetchingLocationName(false); // Stop loading
        }
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to get current location. Please try again.');
    } finally {
      setIsFetchingLocation(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="arrow-back" size={24} color={colors.white} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Report Crime</Text>
        <View style={styles.placeholder} />
      </View>

      <ScrollView
        style={styles.content}
        contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}
      >
        {/* Crime Category Selection */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Crime Category *</Text>
          <View style={styles.categoryGrid}>
            {CRIME_CATEGORIES.map(category => (
              <TouchableOpacity
                key={category.id}
                style={[
                  styles.categoryCard,
                  selectedCategory === category.id && styles.categoryCardActive,
                ]}
                onPress={() => setSelectedCategory(category.id)}
              >
                <MaterialCommunityIcons
                  name={category.icon as any}
                  size={28}
                  color={
                    selectedCategory === category.id
                      ? colors.white
                      : colors.primary
                  }
                />
                <Text
                  style={[
                    styles.categoryLabel,
                    selectedCategory === category.id &&
                      styles.categoryLabelActive,
                  ]}
                >
                  {category.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* AI Crime Detection - Camera Section */}
        <View style={styles.aiSectionContainer}>
          <View style={styles.aiSection}>
            <View style={styles.aiHeader}>
              <View style={styles.aiTitleRow}>
                <MaterialCommunityIcons
                  name="robot"
                  size={24}
                  color={colors.primary}
                />
                <Text style={styles.aiTitle}>AI Crime Detection</Text>
                <View style={styles.aiBadge}>
                  <Text style={styles.aiBadgeText}>BETA</Text>
                </View>
              </View>
              <Text style={styles.aiSubtitle}>
                Take a photo and let AI auto-detect the crime type
              </Text>
            </View>

            {!capturedImage ? (
              <TouchableOpacity
                style={styles.cameraButton}
                onPress={showImageOptions}
                disabled={isAnalyzing}
              >
                <MaterialCommunityIcons
                  name="camera-plus"
                  size={40}
                  color={colors.primary}
                />
                <Text style={styles.cameraButtonText}>Capture Crime Scene</Text>
                <Text style={styles.cameraButtonSubtext}>
                  Tap to take photo or choose from library
                </Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.imageContainer}>
                <Image
                  source={{ uri: capturedImage }}
                  style={styles.capturedImage}
                />
                <TouchableOpacity
                  style={styles.removeImageButton}
                  onPress={handleRemoveImage}
                  disabled={isAnalyzing}
                >
                  <Ionicons
                    name="close-circle"
                    size={32}
                    color={colors.error}
                  />
                </TouchableOpacity>

                {isAnalyzing && (
                  <View style={styles.analyzingOverlay}>
                    <ActivityIndicator size="large" color={colors.primary} />
                    <Text style={styles.analyzingText}>Analyzing image...</Text>
                  </View>
                )}
              </View>
            )}
          </View>
        </View>

        {/* What was seen in the photo. D07, ADR 0006. */}
        {showAIResults && analysisResult && (
          <View style={styles.aiResultsContainer}>
            <View style={styles.aiResultsCard}>
              {/* Which tier answered. A replayed or offline answer is labelled
                  rather than passed off as a live one -- same rule as D06's
                  route engine badge and D05's synthetic source. */}
              <View style={styles.aiResultsHeader}>
                <MaterialCommunityIcons
                  name="image-search-outline"
                  size={22}
                  color={colors.primary}
                />
                <Text style={styles.aiResultsTitle}>What the photo shows</Text>
                {/* Owner's call, 2026-10-10: no badge when the answer came from
                    the rehearsal cache. Note what that means — the card still
                    says "live" and "on this device" in the other two cases, so
                    on a replayed photo its silence reads as live. `engine` is
                    still on the API response and still saved into
                    `vision_analysis` on the report, so the record remains
                    accurate even though the screen no longer shows it. */}
                {analysisResult.engine !== 'replay' && (
                  <View style={styles.engineBadge}>
                    <Text style={styles.engineBadgeText}>
                      {ENGINE_LABEL[analysisResult.engine || 'none']}
                    </Text>
                  </View>
                )}
              </View>

              {/* The description is the part we stand behind. */}
              {!!analysisResult.description && (
                <Text style={styles.visionDescription}>
                  {analysisResult.description}
                </Text>
              )}

              <View style={styles.aiResultRow}>
                <Text style={styles.aiResultLabel}>People visible</Text>
                <Text style={styles.aiResultValue}>
                  {analysisResult.people_count ?? 0}
                  {analysisResult.scene ? '  ·  ' + analysisResult.scene : ''}
                </Text>
              </View>

              {/* Every cue, including the ones that came back no. Showing only
                  the hits would make an abstention look like a failure to run. */}
              {!!analysisResult.cues && (
                <View style={styles.cueList}>
                  {CUE_ORDER.map(([key, label]) => {
                    const answer = (analysisResult.cues as any)?.[key] || 'unclear';
                    return (
                      <View key={key} style={styles.cueRow}>
                        <MaterialCommunityIcons
                          name={CUE_ICON[answer]}
                          size={16}
                          color={CUE_COLOUR[answer]}
                        />
                        <Text style={styles.cueLabel}>{label}</Text>
                        <Text
                          style={[styles.cueAnswer, { color: CUE_COLOUR[answer] }]}
                        >
                          {answer}
                        </Text>
                      </View>
                    );
                  })}
                </View>
              )}

              {/* A suggestion, not a verdict. Null is the normal answer. */}
              {analysisResult.proposed_category ? (
                <View style={styles.proposalBox}>
                  <Text style={styles.proposalLabel}>
                    Suggested category ({analysisResult.confidence})
                  </Text>
                  <Text style={styles.proposalValue}>
                    {analysisResult.proposed_category.toUpperCase()}
                  </Text>
                  <Text style={styles.proposalReason}>
                    Because {analysisResult.reason}.
                  </Text>
                  {analysisResult.agreement === 'agrees' && (
                    <Text style={styles.agreeText}>
                      Matches what you wrote
                    </Text>
                  )}
                  {analysisResult.agreement === 'disagrees' && (
                    <Text style={styles.disagreeText}>
                      Your description mentions something different — worth a
                      second look
                    </Text>
                  )}
                </View>
              ) : (
                <View style={styles.proposalBox}>
                  <Text style={styles.proposalLabel}>No category suggested</Text>
                  <Text style={styles.proposalReason}>
                    Nothing in this photo points to a specific category. A
                    photograph cannot show intent or who started something, so
                    please choose the category yourself.
                  </Text>
                </View>
              )}

              <View style={styles.aiInfoBox}>
                <Ionicons
                  name="information-circle"
                  size={16}
                  color={colors.info}
                />
                <Text style={styles.aiInfoText}>
                  You decide what gets filed. This is a suggestion from the
                  photo — change it freely.
                </Text>
              </View>
            </View>
          </View>
        )}

        {/* Title Input */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Title *</Text>
          <TextInput
            style={styles.input}
            placeholder="Brief title of the incident"
            placeholderTextColor={colors.textSecondary}
            value={title}
            onChangeText={setTitle}
            maxLength={100}
          />
        </View>

        {/* Description Input */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Description *</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            placeholder="Provide detailed description of what happened..."
            placeholderTextColor={colors.textSecondary}
            value={description}
            onChangeText={setDescription}
            multiline
            numberOfLines={6}
            textAlignVertical="top"
          />
        </View>

        {/* Date and Time of Incident */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Date & Time of Incident *</Text>
          <View style={styles.dateTimeContainer}>
            <TouchableOpacity
              style={styles.dateTimeButton}
              onPress={() => setShowDatePicker(true)}
            >
              <Ionicons
                name="calendar-outline"
                size={20}
                color={colors.primary}
              />
              <Text style={styles.dateTimeText}>
                {incidentDateTime.toLocaleDateString('en-GB')}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.dateTimeButton}
              onPress={() => setShowTimePicker(true)}
            >
              <Ionicons name="time-outline" size={20} color={colors.primary} />
              <Text style={styles.dateTimeText}>
                {incidentDateTime.toLocaleTimeString('en-US', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Text>
            </TouchableOpacity>
          </View>

          {showDatePicker && Platform.OS === 'ios' && (
            <View style={styles.pickerContainer}>
              <DateTimePicker
                value={incidentDateTime}
                mode="date"
                display="spinner"
                onValueChange={handleDateChange}
                onDismiss={() => setShowDatePicker(false)}
                maximumDate={new Date()}
                textColor="#000000"
                themeVariant="light"
              />
              <TouchableOpacity
                style={styles.pickerCloseButton}
                onPress={() => setShowDatePicker(false)}
              >
                <Text style={styles.pickerCloseButtonText}>Done</Text>
              </TouchableOpacity>
            </View>
          )}

          {showDatePicker && Platform.OS === 'android' && (
            <DateTimePicker
              value={incidentDateTime}
              mode="date"
              display="default"
              onValueChange={handleDateChange}
              onDismiss={() => setShowDatePicker(false)}
              maximumDate={new Date()}
              textColor="#000000"
              themeVariant="light"
            />
          )}

          {showTimePicker && Platform.OS === 'ios' && (
            <View style={styles.pickerContainer}>
              <DateTimePicker
                value={incidentDateTime}
                mode="time"
                display="spinner"
                onValueChange={handleTimeChange}
                onDismiss={() => setShowTimePicker(false)}
                maximumDate={new Date()}
                textColor="#000000"
                themeVariant="light"
                is24Hour={false}
                minuteInterval={1}
              />
              <TouchableOpacity
                style={styles.pickerCloseButton}
                onPress={() => setShowTimePicker(false)}
              >
                <Text style={styles.pickerCloseButtonText}>Done</Text>
              </TouchableOpacity>
            </View>
          )}

          {showTimePicker && Platform.OS === 'android' && (
            <DateTimePicker
              value={incidentDateTime}
              mode="time"
              display="default"
              onValueChange={handleTimeChange}
              onDismiss={() => setShowTimePicker(false)}
              maximumDate={new Date()}
              textColor="#000000"
              themeVariant="light"
              is24Hour={false}
              minuteInterval={1}
            />
          )}
        </View>

        {/* Map Section */}
        <View style={styles.section}>
          <View style={styles.mapHeader}>
            <Text style={styles.sectionTitle}>Select Location on Map *</Text>
            <TouchableOpacity
              style={styles.currentLocationButton}
              onPress={handleUseCurrentLocation}
              disabled={isFetchingLocation}
            >
              {isFetchingLocation ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : (
                <Ionicons name="locate" size={20} color={colors.primary} />
              )}
              <Text style={styles.currentLocationText}>
                {isFetchingLocation ? 'Locating...' : 'Use Current'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Search Bar */}
          <View style={styles.searchWrapper}>
            <View style={styles.searchContainer}>
              <TextInput
                style={styles.searchInput}
                placeholder="Search for a place..."
                placeholderTextColor={colors.textSecondary}
                value={searchQuery}
                onChangeText={setSearchQuery}
                onSubmitEditing={handleSearch}
                returnKeyType="search"
              />
              {isFetchingSuggestions && (
                <View style={styles.searchLoadingContainer}>
                  <ActivityIndicator size="small" color={colors.primary} />
                </View>
              )}
              <TouchableOpacity
                style={styles.searchButton}
                onPress={handleSearch}
              >
                <Ionicons name="search" size={20} color={colors.white} />
              </TouchableOpacity>
            </View>

            {/* Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <ScrollView
                style={styles.suggestionsContainer}
                nestedScrollEnabled
              >
                {suggestions.map((suggestion, index) => (
                  <TouchableOpacity
                    key={suggestion.place_id || index}
                    style={styles.suggestionItem}
                    onPress={() => handleSuggestionSelect(suggestion)}
                  >
                    <Ionicons
                      name="location-outline"
                      size={18}
                      color={colors.primary}
                    />
                    <Text style={styles.suggestionText} numberOfLines={2}>
                      {suggestion.display_name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}
          </View>

          <View style={styles.mapContainer}>
            <MapView
              provider={MAP_PROVIDER}
              style={styles.map}
              region={region}
              onPress={handleMapPress}
              onRegionChangeComplete={setRegion}
            >
              {selectedLocation && (
                <Marker coordinate={selectedLocation}>
                  <View style={styles.customMarker}>
                    <Ionicons name="location" size={40} color={colors.error} />
                  </View>
                </Marker>
              )}
            </MapView>
            <View style={styles.mapOverlay}>
              <View style={styles.mapHint}>
                <Ionicons
                  name="information-circle"
                  size={16}
                  color={colors.primary}
                />
                <Text style={styles.mapHintText}>
                  Tap anywhere on the map to select location
                </Text>
              </View>
            </View>
          </View>

          {/* Selected Location Display */}
          {selectedLocation && (isFetchingLocationName || locationName) ? (
            <View style={styles.selectedLocationContainer}>
              <Ionicons
                name="location"
                size={20}
                color={
                  isFetchingLocationName ? colors.textSecondary : colors.primary
                }
              />
              {isFetchingLocationName ? (
                <>
                  <ActivityIndicator
                    size="small"
                    color={colors.primary}
                    style={{ marginLeft: spacing.sm, marginRight: spacing.sm }}
                  />
                  <Text
                    style={[styles.selectedLocationText, styles.loadingText]}
                  >
                    Fetching location address...
                  </Text>
                </>
              ) : (
                <Text style={styles.selectedLocationText}>{locationName}</Text>
              )}
            </View>
          ) : null}
        </View>

        {/* Submit Button */}
        <TouchableOpacity
          style={[
            styles.submitButton,
            isSubmitting && styles.submitButtonDisabled,
          ]}
          onPress={handleSubmit}
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator size="small" color={colors.white} />
          ) : (
            <Ionicons name="checkmark-circle" size={24} color={colors.white} />
          )}
          <Text style={styles.submitButtonText}>
            {isSubmitting ? 'Submitting...' : 'Submit Report'}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    backgroundColor: colors.primary,
    elevation: 4,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  backButton: {
    padding: spacing.sm,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.white,
  },
  placeholder: {
    width: 40,
  },
  content: {
    flex: 1,
  },
  section: {
    padding: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  categoryCard: {
    width: '48%',
    marginBottom: spacing.md,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 100,
    elevation: 2,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  categoryCardActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
    elevation: 4,
    shadowOpacity: 0.2,
  },
  categoryLabel: {
    fontSize: fontSize.md,
    color: colors.text,
    marginTop: spacing.sm,
    textAlign: 'center',
    fontWeight: '500',
  },
  categoryLabelActive: {
    color: colors.white,
    fontWeight: '600',
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  textArea: {
    minHeight: 120,
    paddingTop: spacing.md,
  },
  dateTimeContainer: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  dateTimeButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    elevation: 2,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  dateTimeText: {
    fontSize: fontSize.md,
    color: colors.text,
    marginLeft: spacing.sm,
    fontWeight: '500',
  },
  pickerContainer: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    elevation: 4,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
  },
  pickerCloseButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  pickerCloseButtonText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  mapHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  currentLocationButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  currentLocationText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    marginLeft: spacing.xs,
    fontWeight: '500',
  },
  mapContainer: {
    height: 250,
    borderRadius: borderRadius.md,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: colors.border,
  },
  map: {
    flex: 1,
  },
  customMarker: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  mapOverlay: {
    position: 'absolute',
    top: spacing.sm,
    left: spacing.sm,
    right: spacing.sm,
  },
  mapHint: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    elevation: 2,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  mapHintText: {
    fontSize: fontSize.sm,
    color: colors.text,
    marginLeft: spacing.xs,
  },
  searchWrapper: {
    marginBottom: spacing.md,
    position: 'relative',
    zIndex: 1000,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  searchInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: spacing.sm,
  },
  searchLoadingContainer: {
    position: 'absolute',
    right: 60,
    top: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
  },
  searchButton: {
    backgroundColor: colors.primary,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
    width: 48,
    height: 48,
  },
  suggestionsContainer: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    elevation: 4,
    shadowColor: colors.shadowDark,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
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
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    marginLeft: spacing.sm,
  },
  selectedLocationContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  selectedLocationText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
    marginLeft: spacing.sm,
  },
  loadingText: {
    color: colors.textSecondary,
    fontStyle: 'italic',
  },
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    padding: spacing.lg,
    borderRadius: borderRadius.md,
    elevation: 4,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
  },
  submitButtonDisabled: {
    backgroundColor: colors.border,
    opacity: 0.6,
  },
  submitButtonText: {
    fontSize: fontSize.lg,
    fontWeight: 'bold',
    color: colors.white,
    marginLeft: spacing.sm,
  },
  // AI Crime Detection Styles
  aiSectionContainer: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  aiSection: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 2,
    borderColor: colors.primary + '30',
    padding: spacing.lg,
  },
  aiHeader: {
    marginBottom: spacing.md,
  },
  aiTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  aiTitle: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
    marginLeft: spacing.sm,
    flex: 1,
  },
  aiBadge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  aiBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: 'bold',
    color: colors.white,
  },
  aiSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginLeft: 32,
  },
  cameraButton: {
    backgroundColor: colors.background,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: colors.primary,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  cameraButtonText: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.sm,
  },
  cameraButtonSubtext: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  imageContainer: {
    position: 'relative',
    marginTop: spacing.md,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  capturedImage: {
    width: '100%',
    height: 250,
    borderRadius: borderRadius.lg,
  },
  removeImageButton: {
    position: 'absolute',
    top: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.white,
    borderRadius: 16,
  },
  analyzingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  analyzingText: {
    color: colors.white,
    fontSize: fontSize.md,
    fontWeight: '600',
    marginTop: spacing.sm,
  },
  aiResultsContainer: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  aiResultsCard: {
    backgroundColor: colors.success + '10',
    borderWidth: 1,
    borderColor: colors.success,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  aiResultsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  aiResultsTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.success,
    marginLeft: spacing.sm,
  },
  aiResultRow: {
    marginBottom: spacing.sm,
  },
  aiResultLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  aiResultValue: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  aiInfoBox: {
    flexDirection: 'row',
    backgroundColor: colors.info + '20',
    padding: spacing.sm,
    borderRadius: borderRadius.sm,
    marginTop: spacing.sm,
  },
  aiInfoText: {
    fontSize: fontSize.xs,
    color: colors.info,
    marginLeft: spacing.xs,
    flex: 1,
  },

  // Phase 2: Pose Analysis Styles

  // Action Badges

  // Threat Level Badges

  // Interaction Analysis

  // Phase 3: Scene Analysis Styles

  // Environmental Risk Badge

  engineBadge: {
    marginLeft: 'auto',
    backgroundColor: colors.primary + '20',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
    borderWidth: 1,
    borderColor: colors.primary + '40',
  },
  engineBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.primary,
  },
  // --- D07: the cue card ----------------------------------------------------
  visionDescription: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  cueList: {
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    paddingTop: spacing.sm,
  },
  cueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: spacing.sm,
  },
  cueLabel: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  cueAnswer: {
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  proposalBox: {
    backgroundColor: colors.borderLight,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  proposalLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  proposalValue: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
    marginTop: 2,
  },
  proposalReason: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
    lineHeight: 19,
  },
  agreeText: {
    fontSize: fontSize.sm,
    color: colors.success,
    marginTop: spacing.sm,
  },
  disagreeText: {
    fontSize: fontSize.sm,
    color: colors.warning,
    marginTop: spacing.sm,
    lineHeight: 19,
  },
});

export default AddReportScreen;
