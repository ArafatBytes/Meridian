import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  StatusBar,
  Alert,
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
import { useAuthStore } from '../../store';
import { GlassCard } from '../../components/GlassCard';
import { useSosController } from '../../features/guardian/GuardianProvider';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MainTabParamList } from '../../types';

type HomeScreenNavigationProp = BottomTabNavigationProp<
  MainTabParamList,
  'Home'
>;

const HomeScreen: React.FC = () => {
  const { user } = useAuthStore();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<HomeScreenNavigationProp>();
  const rootNavigation = useNav<any>();

  // Defect 14 extracted the SOS flow — token refresh, location, upload
  // progress — out of this screen and into `useSOS`. B6a/B8 then moved the
  // *instance* up to the app root, because calling `useSOS()` per screen gave
  // this app two shake listeners and two camera modals per shake: the tab
  // navigator keeps visited screens mounted, so Home and Map each had one.
  //
  // There is now exactly one controller, one shake listener and one voice guard,
  // all in `features/guardian/GuardianProvider`. This is a consumer.
  const sos = useSosController();

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
  // audio.
  //
  // B8 built it. Shout detection, the hot-word match and the automatic trigger
  // all live in `features/voice/useVoiceGuard`, mounted once in
  // `GuardianProvider` so a shouted phrase works on whatever screen is showing.
  // Nothing is uploaded and nothing is recorded until a match fires.

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

      {/* SOSFlow is rendered once by GuardianProvider at the app root. */}

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
          onPress={() => sos.start('button')}
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

});

export default HomeScreen;
