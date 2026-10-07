import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  StatusBar,
  Alert,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import {
  NavigationProp,
  useNavigation as useNav,
} from '@react-navigation/native';
import {
  colors,
  spacing,
  borderRadius,
  typography,
  shadows,
  gradients,
} from '../../theme';
import { useAuthStore, useLocationStore } from '../../store';
import { GlassCard } from '../../components/GlassCard';
import { SOSCameraModal } from '../../components/SOSCameraModal';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MainTabParamList } from '../../types';
import { API_BASE_URL } from '../../constants/app.constants';
import * as FileSystem from 'expo-file-system';
import { Accelerometer } from 'expo-sensors';

type HomeScreenNavigationProp = BottomTabNavigationProp<
  MainTabParamList,
  'Home'
>;

const HomeScreen: React.FC = () => {
  const { user, token } = useAuthStore();
  const { currentLocation, getCurrentLocation } = useLocationStore();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<HomeScreenNavigationProp>();
  const rootNavigation = useNav<any>();

  const [isSOSModalVisible, setIsSOSModalVisible] = useState(false);
  const [isSendingSOS, setIsSendingSOS] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleSOSPress = () => {
    setIsSOSModalVisible(true);
    // Proactively try to get location if we don't have it
    if (!currentLocation) {
      getCurrentLocation().catch(err => console.log('Bg location fetch failed:', err));
    }
  };

  const handleVideoRecorded = async (uri: string) => {
    setIsSOSModalVisible(false);
    setIsSendingSOS(true);

    try {
      if (!token) {
        throw new Error('You are not logged in. Please Logout and Login again.');
      }

      let finalLocation = currentLocation;

      // If we still don't have location, force fetch it now
      if (!finalLocation) {
        try {
          console.log('Location null, fetching now...');
          await getCurrentLocation();
          // Re-read from store or just await logic?
          // Store updates state, but 'currentLocation' var here is closure stale?
          // Ideally `getCurrentLocation` returns the location, but the store definition returns void.
          // Let's rely on useLocationStore.getState() if accessible or just trust the store update pattern,
          // BUT functional component closure means 'currentLocation' is stale.
          // Better approach: use useLocationStore.getState().currentLocation if available via import,
          // or simply re-fetch it from the store hook if React re-renders? No, that won't work in this async function.

          // Simplest fix: The current structure of useLocationStore doesn't return the loc.
          // I will use `useLocationStore.getState().currentLocation` pattern if I can import store directly,
          // but here I only have the hook.

          // Let's modify the plan: I will just use the hook's returned function,
          // but I can't get the updated state inside this function easily without checking the store directly.

          // Workaround: We will ignore the error for now and assume the 'catch' above in handleSOSPress
          // might have helped, or throw a descriptive error telling user to enable location.

          // Actually, I can import `useLocationStore` directly to get state non-reactively.
          // Let's just catch the error and throw a user friendly message.
          finalLocation = useLocationStore.getState().currentLocation; // Get the latest state directly
          if (!finalLocation) {
            throw new Error('Location not available. Please enable GPS and try again.');
          }
        } catch (e: any) {
          throw new Error(e.message || 'Location data unavailable. Cannot send SOS.');
        }
      }

      if (!finalLocation) {
        // Second check just in case
        throw new Error('Location data unavailable. Cannot send SOS.');
      }

      const formData = new FormData();
      formData.append('latitude', String(finalLocation.latitude));
      formData.append('longitude', String(finalLocation.longitude));

      const fileType = uri.split('.').pop() || 'mp4';
      // @ts-ignore
      formData.append('video', {
        uri,
        name: `sos_video.${fileType}`,
        type: `video/${fileType}`,
      });

      setUploadProgress(0);

      // Progress Simulation (To ensure dynamic UI even on fast/local networks)
      let simulatedProgress = 0;
      const progressInterval = setInterval(() => {
        simulatedProgress += Math.random() * 5; // Increment randomly
        if (simulatedProgress > 98) simulatedProgress = 98; // Cap at 98%
        setUploadProgress(prev => Math.max(prev, Math.floor(simulatedProgress)));
      }, 200);

      const data: any = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE_URL}/sos/trigger`);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const realPercent = Math.round((event.loaded / event.total) * 100);
            setUploadProgress(prev => {
              const newProgress = Math.max(prev, realPercent);
              // Update simulated base so it doesn't drag us down
              simulatedProgress = newProgress;
              return newProgress;
            });
          }
        };

        xhr.onload = () => {
          clearInterval(progressInterval);
          if (xhr.status >= 200 && xhr.status < 300) {
            setUploadProgress(100); // Jump to 100 on success
            try {
              resolve(JSON.parse(xhr.response));
            } catch (e) {
              reject(new Error('Invalid server response'));
            }
          } else if (xhr.status === 401) {
            reject(new Error('Session expired. Please start the App again or Logout/Login.'));
          } else {
            try {
              const errData = JSON.parse(xhr.response);
              reject(new Error(errData.detail || errData.message || 'Failed to send SOS'));
            } catch (e) {
              reject(new Error(`Server Error: ${xhr.status}`));
            }
          }
        };

        xhr.onerror = () => {
          clearInterval(progressInterval);
          reject(new Error('Network request failed. Please check internet connection.'));
        }

        xhr.send(formData);
      });

      Alert.alert(
        'SOS Sent!',
        `Emergency services and ${data.contacts_notified} contacts have been notified.\nPolice Stations found: ${data.police_stations_found ?? 0}`,
        [{ text: 'OK' }]
      );

    } catch (error: any) {
      console.error('SOS Error:', error);
      Alert.alert('SOS Failed', error.message || 'Could not send SOS alert. Please try again.');
    } finally {
      setIsSendingSOS(false);
    }
  };

  // Auto-SOS: Gyration/Shake Detection
  // Threshold: 3.5g (Extremely violent shake required - 98% intensity)
  React.useEffect(() => {
    const THRESHOLD = 6.0;
    Accelerometer.setUpdateInterval(200);

    const subscription = Accelerometer.addListener(data => {
      const { x, y, z } = data;
      const magnitude = Math.sqrt(x * x + y * y + z * z);

      if (magnitude > THRESHOLD) {
        if (!isSOSModalVisible && !isSendingSOS) {
          console.log("🚨 Auto-SOS Triggered by High Intensity Sensor!");
          handleSOSPress();
        }
      }
    });

    return () => subscription && subscription.remove();
  }, [isSOSModalVisible, isSendingSOS]);

  // The voice-activated SOS block that used to live here has been removed.
  //
  // It was defect 4, and it was worse than useless. It started a 1-second
  // recording every 2 seconds, forever, while the Home screen was mounted --
  // then read `status.isRecording` AFTER calling stopAndUnloadAsync(), which is
  // always false, so it fell through to a branch whose trigger was commented
  // out. The net effect was continuous microphone recording with zero
  // detection: all of the battery and privacy cost, none of the feature.
  //
  // Removed now rather than ported, because SDK 57 drops expo-av and porting
  // dead code to a new API is pure waste. Real hot-word detection is S18, and
  // it uses an on-device wake-word engine -- not a polling loop that uploads
  // audio. Until then SOS is the manual button and the shake gesture above.

  const handleReportCrimePress = () => {
    navigation.navigate('Reports');
    setTimeout(() => {
      rootNavigation.navigate('AddReport');
    }, 100);
  };

  const handleContactsPress = () => {
    navigation.navigate('Profile');
    setTimeout(() => {
      rootNavigation.navigate('EmergencyContacts');
    }, 100);
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.background} />

      <SOSCameraModal
        visible={isSOSModalVisible}
        onClose={() => setIsSOSModalVisible(false)}
        onVideoRecorded={handleVideoRecorded}
        onError={(err) => {
          setIsSOSModalVisible(false);
          Alert.alert('Recording Error', err);
        }}
      />

      <Modal transparent visible={isSendingSOS}>
        <View style={styles.loadingOverlay}>
          <View style={styles.loadingCard}>
            <ActivityIndicator size="large" color={colors.danger} />
            <Text style={styles.loadingText}>Uploading Evidence...</Text>

            <View style={styles.progressBarContainer}>
              <View style={[styles.progressBarFill, { width: `${uploadProgress}%` }]} />
            </View>
            <Text style={styles.progressText}>{uploadProgress}% Completed</Text>

            <Text style={styles.loadingSubText}>Please do not close the app</Text>
          </View>
        </View>
      </Modal>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.greeting}>Welcome back,</Text>
          <Text style={styles.name}>{user?.name?.split(' ')[0]} 👋</Text>
          <Text style={styles.subtitle}>Stay safe with Meridian</Text>
        </View>

        {/* SOS Emergency Button */}
        <TouchableOpacity
          style={[styles.sosButtonContainer, styles.sosButton]}
          onPress={handleSOSPress}
        >
          <Ionicons name="alert-circle" size={32} color={colors.white} />
          <Text style={styles.sosButtonText}>SOS Emergency</Text>
        </TouchableOpacity>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.actionGrid}>
            <TouchableOpacity
              style={styles.actionCard}
              onPress={handleReportCrimePress}
            >
              <GlassCard style={styles.actionCardInner}>
                <View style={styles.iconContainer}>
                  <Ionicons
                    name="document-text"
                    size={28}
                    color={colors.primaryLight}
                  />
                </View>
                <Text style={styles.actionText}>Report Crime</Text>
              </GlassCard>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => navigation.navigate('Map')}
            >
              <GlassCard style={styles.actionCardInner}>
                <View style={styles.iconContainer}>
                  <MaterialCommunityIcons
                    name="map-marker-path"
                    size={28}
                    color={colors.secondary}
                  />
                </View>
                <Text style={styles.actionText}>Plan Route</Text>
              </GlassCard>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => navigation.navigate('Map')}
            >
              <GlassCard style={styles.actionCardInner}>
                <View style={styles.iconContainer}>
                  <Ionicons name="location" size={28} color={colors.info} />
                </View>
                <Text style={styles.actionText}>Track Location</Text>
              </GlassCard>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.actionCard}
              onPress={handleContactsPress}
            >
              <GlassCard style={styles.actionCardInner}>
                <View style={styles.iconContainer}>
                  <Ionicons name="people" size={28} color={colors.warning} />
                </View>
                <Text style={styles.actionText}>Contacts</Text>
              </GlassCard>
            </TouchableOpacity>
          </View>
        </View>

        {/* Safety Status */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Safety Status</Text>
          <GlassCard style={styles.statusCard}>
            <View style={styles.statusIcon}>
              <Ionicons
                name="shield-checkmark"
                size={56}
                color={colors.successLight}
              />
            </View>
            <Text style={styles.statusText}>You are in a safe zone</Text>
            <View style={styles.scoreContainer}>
              <Text style={styles.scoreLabel}>Crime Score</Text>
              <View style={styles.scoreBadge}>
                <Text style={styles.scoreValue}>Low</Text>
                <Text style={styles.scoreNumber}>3.2/10</Text>
              </View>
            </View>
          </GlassCard>
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
  },
  header: {
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
  },
  greeting: {
    ...typography.bodyLarge,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  name: {
    ...typography.h1,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
  },
  sosButtonContainer: {
    marginBottom: spacing.xl,
  },
  sosButton: {
    backgroundColor: colors.danger,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.lg,
  },
  sosButtonText: {
    ...typography.h4,
    color: colors.white,
    fontWeight: '700',
    marginLeft: spacing.md,
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.h3,
    color: colors.text,
    marginBottom: spacing.lg,
  },
  actionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  actionCard: {
    width: '48%',
    marginBottom: spacing.md,
  },
  actionCardInner: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xl,
  },
  iconContainer: {
    marginBottom: spacing.md,
  },
  actionText: {
    ...typography.bodySmall,
    color: colors.text,
    fontWeight: '600',
    textAlign: 'center',
  },
  statusCard: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  statusIcon: {
    marginBottom: spacing.lg,
  },
  statusText: {
    ...typography.h4,
    color: colors.text,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  scoreContainer: {
    alignItems: 'center',
  },
  scoreLabel: {
    ...typography.caption,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: spacing.xs,
  },
  scoreBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
  },
  scoreValue: {
    ...typography.body,
    color: colors.successLight,
    fontWeight: '700',
    marginRight: spacing.sm,
  },
  scoreNumber: {
    ...typography.bodySmall,
    color: colors.textSecondary,
  },
  loadingOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingCard: {
    backgroundColor: colors.white,
    padding: spacing.xl,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    ...shadows.lg,
  },
  loadingText: {
    ...typography.h4,
    color: colors.text,
    marginTop: spacing.md,
    fontWeight: 'bold',
  },
  loadingSubText: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  progressBarContainer: {
    width: 200,
    height: 8,
    backgroundColor: '#E5E7EB',
    borderRadius: 4,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 4,
  },
  progressText: {
    ...typography.caption,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },

});

export default HomeScreen;
