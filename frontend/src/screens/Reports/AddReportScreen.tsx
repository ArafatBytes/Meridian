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
import MapView, { Marker, PROVIDER_GOOGLE } from '../../components/MapComponent';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import DateTimePicker from '@react-native-community/datetimepicker';
import * as ImagePicker from 'expo-image-picker';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useLocationStore } from '../../store';
import { DEFAULT_MAP_REGION } from '../../constants';
import { crimeService, CrimeAnalysisResult } from '../../services';

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
    getCurrentLocation();
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
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${coordinate.latitude}&lon=${coordinate.longitude}`,
      );
      const data = await response.json();
      if (data.display_name) {
        setLocationName(data.display_name);
      } else {
        setLocationName('Location address not available');
      }
    } catch (error) {
      console.log('Error getting location name:', error);
      setLocationName('Failed to fetch location address');
    } finally {
      setIsFetchingLocationName(false); // Stop loading
    }
  };

  const fetchSuggestions = async (query: string) => {
    setIsFetchingSuggestions(true);
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=5`,
      );
      const data = await response.json();
      setSuggestions(data);
      setShowSuggestions(data.length > 0);
    } catch (error) {
      console.log('Error fetching suggestions:', error);
      setSuggestions([]);
      setShowSuggestions(false);
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
      // Perform a fresh search with the exact query typed by user
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1`,
      );
      const data = await response.json();

      if (data && data.length > 0) {
        const location = data[0];
        const coordinate = {
          latitude: parseFloat(location.lat),
          longitude: parseFloat(location.lon),
        };

        setSelectedLocation(coordinate);
        setLocationName(location.display_name);
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

  const handleDateChange = (event: any, selectedDate?: Date) => {
    if (Platform.OS === 'android') {
      setShowDatePicker(false);
    }

    // Always update if we have a selected date and user didn't dismiss
    if (selectedDate && event.type !== 'dismissed') {
      // Preserve the time when changing date
      const newDateTime = new Date(selectedDate.getTime());
      const currentTime =
        incidentDateTime.getHours() * 60 + incidentDateTime.getMinutes();
      const now = new Date();

      // Check if the selected date is today
      const isToday =
        selectedDate.getDate() === now.getDate() &&
        selectedDate.getMonth() === now.getMonth() &&
        selectedDate.getFullYear() === now.getFullYear();

      // If today and time would be in future, use current time
      if (isToday && currentTime > now.getHours() * 60 + now.getMinutes()) {
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
    }
  };
  const handleTimeChange = (event: any, selectedTime?: Date) => {
    if (Platform.OS === 'android') {
      setShowTimePicker(false);
    }

    // Always update if we have a selected time and user didn't dismiss
    if (selectedTime && event.type !== 'dismissed') {
      // Create new date preserving the date part, updating only time
      const newDateTime = new Date(incidentDateTime.getTime());
      newDateTime.setHours(
        selectedTime.getHours(),
        selectedTime.getMinutes(),
        0,
        0,
      );
      setIncidentDateTime(newDateTime);
    }
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
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
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
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
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
      const result = await crimeService.analyzeCrimeImage(imageUri, 0.25);

      if (result.success) {
        setAnalysisResult(result);
        setShowAIResults(true);

        // Auto-fill form with AI suggestions
        if (result.crime_type) {
          setSelectedCategory(result.crime_type);
        }
        if (result.title) {
          setTitle(result.title);
        }
        if (result.description) {
          setDescription(result.description);
        }

        Alert.alert(
          'AI Analysis Complete! 🤖',
          `Detected: ${result.crime_type}\nConfidence: ${(result.confidence! * 100).toFixed(1)}%\n\nThe form has been auto-filled. Please review and submit.`,
          [{ text: 'OK' }],
        );
      } else {
        setShowAIResults(false);

        // Check if it's a "no crime detected" scenario vs actual error
        const message = result.message || '';
        const isNoCrime =
          message.toLowerCase().includes('no crime') ||
          message.toLowerCase().includes('crime indicators') ||
          message.toLowerCase().includes('validation_failed') ||
          message.toLowerCase().includes('no relevant objects') ||
          message.toLowerCase() === 'validation failed';

        if (isNoCrime) {
          Alert.alert(
            'No Crime Detected ✅',
            'The AI did not detect any crime indicators in this image. This appears to be a normal scene.\n\nIf you still want to report an incident, please fill the form manually.',
            [{ text: 'OK' }],
          );
        } else {
          Alert.alert(
            'Analysis Failed',
            message ||
            'Could not analyze the image. Please fill the form manually.',
            [{ text: 'OK' }],
          );
        }
      }
    } catch (error: any) {
      setShowAIResults(false);
      Alert.alert('Error', 'Failed to analyze image: ' + error.message);
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
          const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${currentLocation.latitude}&lon=${currentLocation.longitude}`,
          );
          const data = await response.json();
          if (data.display_name) {
            setLocationName(data.display_name);
          } else {
            setLocationName('Location address not available');
          }
        } catch (error) {
          console.log('Error getting location name:', error);
          setLocationName('Failed to fetch location address');
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

        {/* AI Analysis Results - Separate Section */}
        {showAIResults && analysisResult && (
          <View style={styles.aiResultsContainer}>
            <View style={styles.aiResultsCard}>
              <View style={styles.aiResultsHeader}>
                <MaterialCommunityIcons
                  name="check-circle"
                  size={24}
                  color={colors.success}
                />
                <Text style={styles.aiResultsTitle}>AI Analysis Complete</Text>
              </View>

              <View style={styles.aiResultRow}>
                <Text style={styles.aiResultLabel}>Detected Crime:</Text>
                <Text style={styles.aiResultValue}>
                  {analysisResult.crime_type?.toUpperCase()}
                </Text>
              </View>

              <View style={styles.aiResultRow}>
                <Text style={styles.aiResultLabel}>Confidence:</Text>
                <View style={styles.confidenceContainer}>
                  <View
                    style={[
                      styles.confidenceBar,
                      { width: `${(analysisResult.confidence || 0) * 100}%` },
                    ]}
                  />
                  <Text style={styles.confidenceText}>
                    {((analysisResult.confidence || 0) * 100).toFixed(1)}%
                  </Text>
                </View>
              </View>

              {analysisResult.details && (
                <View style={styles.aiResultRow}>
                  <Text style={styles.aiResultLabel}>Detected Objects:</Text>
                  <Text style={styles.aiResultValue}>
                    {analysisResult.details.detected_objects?.join(', ')}
                  </Text>
                </View>
              )}

              {/* Phase 2: Pose Analysis Display */}
              {analysisResult.pose_analysis &&
                analysisResult.pose_analysis.poses_detected > 0 && (
                  <View style={styles.poseAnalysisSection}>
                    <View style={styles.poseAnalysisHeader}>
                      <MaterialCommunityIcons
                        name="human-handsup"
                        size={20}
                        color={colors.primary}
                      />
                      <Text style={styles.poseAnalysisTitle}>
                        Pose & Action Analysis
                      </Text>
                    </View>

                    {/* Person Count */}
                    <View style={styles.aiResultRow}>
                      <Text style={styles.aiResultLabel}>
                        Persons Detected:
                      </Text>
                      <Text style={styles.aiResultValue}>
                        {analysisResult.details?.person_count ||
                          analysisResult.pose_analysis.poses_detected}
                      </Text>
                    </View>

                    {/* Action Badges */}
                    {analysisResult.pose_analysis.actions &&
                      analysisResult.pose_analysis.actions.length > 0 && (
                        <View style={styles.actionsContainer}>
                          <Text style={styles.aiResultLabel}>
                            Detected Actions:
                          </Text>
                          <View style={styles.actionBadgesContainer}>
                            {analysisResult.pose_analysis.actions.map(
                              (action: string, index: number) => {
                                const actionEmoji =
                                  {
                                    punching: '🥊',
                                    kicking: '🦵',
                                    hands_raised: '🙌',
                                    reaching: '👐',
                                    running: '🏃',
                                    fallen: '🤕',
                                    crouching: '🧎',
                                    standing: '🧍',
                                  }[action] || '👤';

                                return (
                                  <View key={index} style={styles.actionBadge}>
                                    <Text style={styles.actionBadgeText}>
                                      {actionEmoji} {action.replace('_', ' ')}
                                    </Text>
                                  </View>
                                );
                              },
                            )}
                          </View>
                        </View>
                      )}

                    {/* Threat Level Indicators */}
                    {analysisResult.pose_analysis.threat_levels &&
                      analysisResult.pose_analysis.threat_levels.length > 0 && (
                        <View style={styles.threatLevelContainer}>
                          <Text style={styles.aiResultLabel}>
                            Threat Assessment:
                          </Text>
                          <View style={styles.threatBadgesContainer}>
                            {(() => {
                              const threats =
                                analysisResult.pose_analysis.threat_levels;
                              const highCount = threats.filter(
                                (t: string) => t === 'high',
                              ).length;
                              const mediumCount = threats.filter(
                                (t: string) => t === 'medium',
                              ).length;
                              const lowCount = threats.filter(
                                (t: string) => t === 'low',
                              ).length;

                              return (
                                <>
                                  {highCount > 0 && (
                                    <View
                                      style={[
                                        styles.threatBadge,
                                        styles.threatHigh,
                                      ]}
                                    >
                                      <Text style={styles.threatBadgeText}>
                                        ⚠️ High Threat ({highCount})
                                      </Text>
                                    </View>
                                  )}
                                  {mediumCount > 0 && (
                                    <View
                                      style={[
                                        styles.threatBadge,
                                        styles.threatMedium,
                                      ]}
                                    >
                                      <Text style={styles.threatBadgeText}>
                                        ⚡ Medium Threat ({mediumCount})
                                      </Text>
                                    </View>
                                  )}
                                  {lowCount > 0 && (
                                    <View
                                      style={[
                                        styles.threatBadge,
                                        styles.threatLow,
                                      ]}
                                    >
                                      <Text style={styles.threatBadgeText}>
                                        ✓ Low Threat ({lowCount})
                                      </Text>
                                    </View>
                                  )}
                                </>
                              );
                            })()}
                          </View>
                        </View>
                      )}

                    {/* Interaction Analysis */}
                    {analysisResult.pose_analysis.interaction && (
                      <View style={styles.interactionContainer}>
                        <Text style={styles.aiResultLabel}>Interaction:</Text>
                        <View style={styles.interactionBox}>
                          <View style={styles.interactionRow}>
                            <Text style={styles.interactionLabel}>Type:</Text>
                            <Text style={styles.interactionValue}>
                              {analysisResult.pose_analysis.interaction.interaction_type.replace(
                                /_/g,
                                ' ',
                              )}
                            </Text>
                          </View>
                          <View style={styles.interactionRow}>
                            <Text style={styles.interactionLabel}>Risk:</Text>
                            <Text
                              style={[
                                styles.interactionValue,
                                analysisResult.pose_analysis.interaction
                                  .risk_level === 'high' && styles.riskHigh,
                                analysisResult.pose_analysis.interaction
                                  .risk_level === 'medium' && styles.riskMedium,
                              ]}
                            >
                              {analysisResult.pose_analysis.interaction.risk_level.toUpperCase()}
                            </Text>
                          </View>
                          <View style={styles.interactionRow}>
                            <Text style={styles.interactionLabel}>
                              Proximity:
                            </Text>
                            <Text style={styles.interactionValue}>
                              {
                                analysisResult.pose_analysis.interaction
                                  .proximity
                              }
                            </Text>
                          </View>
                        </View>
                      </View>
                    )}
                  </View>
                )}

              {/* Phase 3: Scene Analysis Display */}
              {analysisResult.scene_analysis && (
                <View style={styles.sceneAnalysisSection}>
                  <View style={styles.sceneAnalysisHeader}>
                    <MaterialCommunityIcons
                      name="city-variant"
                      size={20}
                      color={colors.primary}
                    />
                    <Text style={styles.sceneAnalysisTitle}>
                      Scene & Environment
                    </Text>
                  </View>

                  {/* Scene Type */}
                  <View style={styles.aiResultRow}>
                    <Text style={styles.aiResultLabel}>Location Type:</Text>
                    <Text style={styles.aiResultValue}>
                      🏙️{' '}
                      {analysisResult.scene_analysis.scene_type
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (l: string) => l.toUpperCase())}
                    </Text>
                  </View>

                  {/* Lighting Condition */}
                  <View style={styles.aiResultRow}>
                    <Text style={styles.aiResultLabel}>Lighting:</Text>
                    <Text style={styles.aiResultValue}>
                      💡{' '}
                      {analysisResult.scene_analysis.lighting_condition
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (l: string) => l.toUpperCase())}
                    </Text>
                  </View>

                  {/* Crowd Density */}
                  <View style={styles.aiResultRow}>
                    <Text style={styles.aiResultLabel}>Crowd Density:</Text>
                    <Text style={styles.aiResultValue}>
                      👥{' '}
                      {analysisResult.scene_analysis.crowd_density
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (l: string) => l.toUpperCase())}
                    </Text>
                  </View>

                  {/* Time of Day */}
                  <View style={styles.aiResultRow}>
                    <Text style={styles.aiResultLabel}>Time of Day:</Text>
                    <Text style={styles.aiResultValue}>
                      🕐{' '}
                      {analysisResult.scene_analysis.time_of_day
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (l: string) => l.toUpperCase())}
                    </Text>
                  </View>

                  {/* Isolation Level */}
                  <View style={styles.aiResultRow}>
                    <Text style={styles.aiResultLabel}>Isolation:</Text>
                    <Text style={styles.aiResultValue}>
                      🏝️{' '}
                      {analysisResult.scene_analysis.isolation_level
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (l: string) => l.toUpperCase())}
                    </Text>
                  </View>

                  {/* Environmental Risk Badge */}
                  {analysisResult.scene_analysis.risk_level !== 'low' && (
                    <View style={styles.environmentalRiskContainer}>
                      <View
                        style={[
                          styles.environmentalRiskBadge,
                          analysisResult.scene_analysis.risk_level === 'high'
                            ? styles.envRiskHigh
                            : styles.envRiskMedium,
                        ]}
                      >
                        <Text style={styles.environmentalRiskText}>
                          ⚠️{' '}
                          {analysisResult.scene_analysis.risk_level.toUpperCase()}{' '}
                          RISK ENVIRONMENT
                        </Text>
                      </View>
                    </View>
                  )}
                </View>
              )}

              {/* Phase 4: ML Fusion Decision Engine Display */}
              {analysisResult.decision_engine &&
                analysisResult.fusion_signals && (
                  <View style={styles.decisionEngineSection}>
                    <View style={styles.decisionEngineHeader}>
                      <MaterialCommunityIcons
                        name="brain"
                        size={20}
                        color={colors.primary}
                      />
                      <Text style={styles.decisionEngineTitle}>
                        AI Decision Engine
                      </Text>
                      <View style={styles.engineBadge}>
                        <Text style={styles.engineBadgeText}>
                          {analysisResult.decision_engine === 'ml_fusion_v1'
                            ? '⚡ ML Fusion'
                            : '📋 Rule-Based'}
                        </Text>
                      </View>
                    </View>

                    {/* Signal Scores Breakdown */}
                    <View style={styles.signalScoresContainer}>
                      <Text style={styles.signalScoresLabel}>
                        Multi-Signal Analysis:
                      </Text>

                      {/* Object Detection Score */}
                      <View style={styles.scoreRow}>
                        <View style={styles.scoreLabel}>
                          <Text style={styles.scoreLabelText}>🎯 Objects</Text>
                          <Text style={styles.scoreValue}>
                            {analysisResult.fusion_signals.object_score.toFixed(
                              1,
                            )}
                          </Text>
                        </View>
                        <View style={styles.scoreBarContainer}>
                          <View
                            style={[
                              styles.scoreBarFill,
                              {
                                width: `${Math.min(analysisResult.fusion_signals.object_score, 100)}%`,
                                backgroundColor:
                                  analysisResult.fusion_signals.object_score >
                                    70
                                    ? colors.success
                                    : analysisResult.fusion_signals
                                      .object_score > 40
                                      ? colors.warning
                                      : colors.error,
                              },
                            ]}
                          />
                        </View>
                      </View>

                      {/* Pose Analysis Score */}
                      <View style={styles.scoreRow}>
                        <View style={styles.scoreLabel}>
                          <Text style={styles.scoreLabelText}>💪 Actions</Text>
                          <Text style={styles.scoreValue}>
                            {analysisResult.fusion_signals.pose_score.toFixed(
                              1,
                            )}
                          </Text>
                        </View>
                        <View style={styles.scoreBarContainer}>
                          <View
                            style={[
                              styles.scoreBarFill,
                              {
                                width: `${Math.min(analysisResult.fusion_signals.pose_score, 100)}%`,
                                backgroundColor:
                                  analysisResult.fusion_signals.pose_score > 70
                                    ? colors.success
                                    : analysisResult.fusion_signals.pose_score >
                                      40
                                      ? colors.warning
                                      : colors.error,
                              },
                            ]}
                          />
                        </View>
                      </View>

                      {/* Scene Analysis Score */}
                      <View style={styles.scoreRow}>
                        <View style={styles.scoreLabel}>
                          <Text style={styles.scoreLabelText}>🏙️ Scene</Text>
                          <Text style={styles.scoreValue}>
                            {analysisResult.fusion_signals.scene_score.toFixed(
                              1,
                            )}
                          </Text>
                        </View>
                        <View style={styles.scoreBarContainer}>
                          <View
                            style={[
                              styles.scoreBarFill,
                              {
                                width: `${Math.min(analysisResult.fusion_signals.scene_score, 100)}%`,
                                backgroundColor:
                                  analysisResult.fusion_signals.scene_score > 70
                                    ? colors.success
                                    : analysisResult.fusion_signals
                                      .scene_score > 40
                                      ? colors.warning
                                      : colors.error,
                              },
                            ]}
                          />
                        </View>
                      </View>

                      {/* Fusion Score - Main Result */}
                      <View style={styles.fusionScoreContainer}>
                        <View style={styles.fusionScoreHeader}>
                          <Text style={styles.fusionScoreLabel}>
                            ⚡ Weighted Fusion Score
                          </Text>
                          <Text style={styles.fusionScoreValue}>
                            {analysisResult.fusion_signals.weighted_score.toFixed(
                              1,
                            )}
                          </Text>
                        </View>
                        <View style={styles.fusionScoreBarContainer}>
                          <View
                            style={[
                              styles.fusionScoreBarFill,
                              {
                                width: `${Math.min(analysisResult.fusion_signals.weighted_score, 100)}%`,
                                backgroundColor:
                                  analysisResult.fusion_signals.weighted_score >
                                    75
                                    ? '#4CAF50'
                                    : analysisResult.fusion_signals
                                      .weighted_score > 50
                                      ? '#FF9800'
                                      : '#F44336',
                              },
                            ]}
                          />
                        </View>
                      </View>
                    </View>

                    {/* Signals Used Badge */}
                    <View style={styles.signalsUsedContainer}>
                      <MaterialCommunityIcons
                        name="signal"
                        size={16}
                        color={
                          analysisResult.fusion_signals.signals_used === 3
                            ? colors.success
                            : analysisResult.fusion_signals.signals_used === 2
                              ? colors.warning
                              : colors.info
                        }
                      />
                      <Text style={styles.signalsUsedText}>
                        Using {analysisResult.fusion_signals.signals_used}/3 AI
                        signals for decision
                      </Text>
                    </View>
                  </View>
                )}

              <View style={styles.aiInfoBox}>
                <Ionicons
                  name="information-circle"
                  size={16}
                  color={colors.info}
                />
                <Text style={styles.aiInfoText}>
                  Form auto-filled with AI suggestions. Please review and edit
                  if needed.
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
                onChange={handleDateChange}
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
              onChange={handleDateChange}
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
                onChange={handleTimeChange}
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
              onChange={handleTimeChange}
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
              provider={PROVIDER_GOOGLE}
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
  confidenceContainer: {
    position: 'relative',
    height: 24,
    backgroundColor: colors.border,
    borderRadius: borderRadius.sm,
    overflow: 'hidden',
    justifyContent: 'center',
  },
  confidenceBar: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: colors.success,
  },
  confidenceText: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
    zIndex: 1,
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
  poseAnalysisSection: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border + '40',
  },
  poseAnalysisHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
    gap: spacing.xs,
  },
  poseAnalysisTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.primary,
  },

  // Action Badges
  actionsContainer: {
    marginTop: spacing.sm,
  },
  actionBadgesContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  actionBadge: {
    backgroundColor: colors.primary + '15',
    borderWidth: 1,
    borderColor: colors.primary + '30',
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs / 2,
  },
  actionBadgeText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: '500',
  },

  // Threat Level Badges
  threatLevelContainer: {
    marginTop: spacing.sm,
  },
  threatBadgesContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  threatBadge: {
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderWidth: 1,
  },
  threatHigh: {
    backgroundColor: '#FEE2E2',
    borderColor: '#EF4444',
  },
  threatMedium: {
    backgroundColor: '#FEF3C7',
    borderColor: '#F59E0B',
  },
  threatLow: {
    backgroundColor: '#D1FAE5',
    borderColor: '#10B981',
  },
  threatBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },

  // Interaction Analysis
  interactionContainer: {
    marginTop: spacing.sm,
  },
  interactionBox: {
    backgroundColor: colors.surface + '80',
    borderRadius: borderRadius.sm,
    padding: spacing.sm,
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border + '30',
  },
  interactionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.xs / 2,
  },
  interactionLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  interactionValue: {
    fontSize: fontSize.xs,
    color: colors.text,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  riskHigh: {
    color: '#EF4444',
  },
  riskMedium: {
    color: '#F59E0B',
  },

  // Phase 3: Scene Analysis Styles
  sceneAnalysisSection: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border + '40',
  },
  sceneAnalysisHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
    gap: spacing.xs,
  },
  sceneAnalysisTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.primary,
  },

  // Environmental Risk Badge
  environmentalRiskContainer: {
    marginTop: spacing.sm,
  },
  environmentalRiskBadge: {
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderWidth: 1,
    alignItems: 'center',
  },
  envRiskHigh: {
    backgroundColor: '#FEE2E2',
    borderColor: '#EF4444',
  },
  envRiskMedium: {
    backgroundColor: '#FEF3C7',
    borderColor: '#F59E0B',
  },
  environmentalRiskText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.text,
  },

  // Phase 4: ML Fusion Decision Engine Styles
  decisionEngineSection: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border + '40',
  },
  decisionEngineHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
    gap: spacing.xs,
  },
  decisionEngineTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.primary,
    flex: 1,
  },
  engineBadge: {
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

  // Signal Scores
  signalScoresContainer: {
    marginTop: spacing.sm,
  },
  signalScoresLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  scoreRow: {
    marginBottom: spacing.sm,
  },
  scoreLabel: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  scoreLabelText: {
    fontSize: fontSize.sm,
    fontWeight: '500',
    color: colors.text,
  },
  scoreValue: {
    fontSize: fontSize.sm,
    fontWeight: '700',
    color: colors.primary,
  },
  scoreBarContainer: {
    height: 8,
    backgroundColor: colors.border,
    borderRadius: borderRadius.sm,
    overflow: 'hidden',
  },
  scoreBarFill: {
    height: '100%',
    borderRadius: borderRadius.sm,
  },

  // Fusion Score (Main Result)
  fusionScoreContainer: {
    marginTop: spacing.md,
    padding: spacing.sm,
    backgroundColor: colors.primary + '10',
    borderRadius: borderRadius.md,
    borderWidth: 2,
    borderColor: colors.primary + '30',
  },
  fusionScoreHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  fusionScoreLabel: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  fusionScoreValue: {
    fontSize: fontSize.lg,
    fontWeight: '800',
    color: colors.primary,
  },
  fusionScoreBarContainer: {
    height: 12,
    backgroundColor: colors.border,
    borderRadius: borderRadius.sm,
    overflow: 'hidden',
  },
  fusionScoreBarFill: {
    height: '100%',
    borderRadius: borderRadius.sm,
  },

  // Signals Used
  signalsUsedContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.sm,
    padding: spacing.xs,
    backgroundColor: colors.background,
    borderRadius: borderRadius.sm,
    gap: spacing.xs,
  },
  signalsUsedText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontStyle: 'italic',
  },
});

export default AddReportScreen;
