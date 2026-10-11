/**
 * Home. The first screen after login, and the one the judges will look at
 * longest, so it carries the design language: Aurora behind glass, a staggered
 * entrance, and depth on touch.
 *
 * ## The fake safety score is gone
 *
 * This screen used to end with a card reading **"You are in a safe zone"** and
 * **"Crime Score — Low, 3.2/10"**. Both were hard-coded string literals. No
 * location was read and no score was computed; it said "safe zone" in the middle
 * of a red flag and "3.2/10" everywhere on earth.
 *
 * In a safety product that is not a placeholder, it is the app telling the user
 * something false about their own situation — the one thing it must never do.
 * And it would not have survived a judge asking "how is that calculated?".
 *
 * It is replaced by `ProtectionCard`, which reports state the app actually
 * holds: whether the OS is monitoring geofences and how many regions, and
 * whether the voice and shake triggers are armed. Every value is read, none is
 * invented. When nothing is on it says so, because "3 of 3 off" is useful and
 * a green shield that means nothing is not.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { NavigationProp, useNavigation as useNav } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTheme } from '../../theme/ThemeProvider';
import { onGradient } from '../../theme/type';
import {
  Aurora,
  Glass,
  Reveal,
  Pressable3D,
  ThemeToggle,
  useAnimatedValue,
} from '../../components/motion';
import { Animated, Easing } from 'react-native';
import { TAB_BAR_CLEARANCE } from '../../navigation/metrics';
import { useAuthStore } from '../../store';
import { useSosController } from '../../features/guardian/GuardianProvider';
import { useGuardianStore } from '../../features/guardian/guardianStore';
import { zoneWatchStatus, type ZoneWatchStatus } from '../../features/geofence/service';
import { MainTabParamList } from '../../types';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

type HomeScreenNavigationProp = BottomTabNavigationProp<MainTabParamList, 'Home'>;

const HomeScreen: React.FC = () => {
  const { t, type, space, radius } = useTheme();
  const { user } = useAuthStore();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<HomeScreenNavigationProp>();
  const rootNavigation = useNav<NavigationProp<Record<string, object | undefined>>>();

  // Defect 14 extracted the SOS flow — token refresh, location, upload
  // progress — out of this screen and into `useSOS`. B6a/B8 then moved the
  // *instance* up to the app root, because calling `useSOS()` per screen gave
  // this app two shake listeners and two camera modals per shake: the tab
  // navigator keeps visited screens mounted, so Home and Map each had one.
  //
  // There is now exactly one controller, one shake listener and one voice guard,
  // all in `features/guardian/GuardianProvider`. This is a consumer.
  const sos = useSosController();

  const { voiceArmed, shakeEnabled, zoneAlertsEnabled } = useGuardianStore();
  const [zones, setZones] = useState<ZoneWatchStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Asks the OS what it is actually monitoring, rather than trusting our own
  // "the user switched it on" flag — those disagree the moment permission is
  // revoked in Settings, which is exactly when the user needs to be told.
  const readZones = useCallback(async () => {
    try {
      setZones(await zoneWatchStatus());
    } catch {
      // `zoneWatchStatus` already swallows the "Not authorized" rejection, but a
      // status card is not worth an error path. No data reads as "off".
      setZones(null);
    }
  }, []);

  // On every focus, not just on mount: the tab navigator keeps this screen
  // mounted, so returning from the Guardian screen after switching something on
  // would otherwise show stale state.
  useFocusEffect(
    useCallback(() => {
      void readZones();
    }, [readZones]),
  );

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await readZones();
    setRefreshing(false);
  }, [readZones]);

  // Both of these hop to the tab first and then push on the root stack, because
  // the target screens live inside other tabs' stacks. The timeout is the
  // inherited workaround for the tab transition — kept, because it works and
  // changing navigation structure days before a demo is not the trade.
  const goToTab = (tab: keyof MainTabParamList, screen: string) => {
    navigation.navigate(tab);
    setTimeout(() => rootNavigation.navigate(screen), 100);
  };

  const firstName = user?.name?.split(' ')[0] ?? 'there';

  return (
    <Aurora intensity="ambient" style={styles.fill}>
      <ScrollView
        style={styles.fill}
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: insets.top + space.lg,
            paddingHorizontal: space.lg,
            // The tab bar floats over this screen now, so the last card has to
            // be pushed clear of it. See `TAB_BAR_CLEARANCE`.
            paddingBottom: insets.bottom + TAB_BAR_CLEARANCE,
          },
        ]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={t.brand}
            colors={[t.brand]}
          />
        }
      >
        {/* Header. The toggle lives here because this is the screen the user
            lands on, and a theme control two taps deep never gets found. */}
        <Reveal index={0}>
          <View style={styles.headerRow}>
            <View style={styles.headerText}>
              <Text style={[type.small, { color: t.textSoft }]}>Welcome back</Text>
              <Text style={[type.hero, { color: t.text }]} numberOfLines={1}>
                {firstName}
              </Text>
            </View>
            <ThemeToggle />
          </View>
        </Reveal>

        {/* SOS. The only warm gradient in the app, and the largest tap target on
            the screen — both deliberate. */}
        <Reveal index={1} style={{ marginTop: space.xl }}>
          <SosButton onPress={() => sos.start('button')} />
        </Reveal>

        {/* Real protection state. */}
        <Reveal index={2} style={{ marginTop: space.xl }}>
          <ProtectionCard
            zones={zones}
            zoneAlertsEnabled={zoneAlertsEnabled}
            voiceArmed={voiceArmed}
            shakeEnabled={shakeEnabled}
            onPress={() => goToTab('Profile', 'Guardian')}
          />
        </Reveal>

        <Reveal index={3} style={{ marginTop: space.xl }}>
          <Text style={[type.overline, styles.overline, { color: t.textFaint }]}>
            Quick actions
          </Text>
        </Reveal>

        <View style={[styles.grid, { marginTop: space.md }]}>
          {[
            {
              key: 'report',
              icon: <Ionicons name="document-text" size={26} color={t.brand} />,
              label: 'Report crime',
              hint: 'Add a flag',
              onPress: () => goToTab('Reports', 'AddReport'),
            },
            {
              key: 'route',
              icon: (
                <MaterialCommunityIcons name="map-marker-path" size={26} color={t.info} />
              ),
              label: 'Plan a route',
              hint: 'Safer path',
              onPress: () => navigation.navigate('Map'),
            },
            {
              key: 'map',
              icon: <Ionicons name="location" size={26} color={t.accent} />,
              label: 'Live map',
              hint: 'Risk nearby',
              onPress: () => navigation.navigate('Map'),
            },
            {
              key: 'contacts',
              icon: <Ionicons name="people" size={26} color={t.warn} />,
              label: 'Contacts',
              hint: 'Who we call',
              onPress: () => goToTab('Profile', 'EmergencyContacts'),
            },
          ].map((action, i) => (
            // The stagger continues from the header rather than restarting, so
            // the screen reads as one entrance instead of two.
            <Reveal key={action.key} index={4 + i} style={styles.gridItem}>
              <Pressable3D onPress={action.onPress} accessibilityLabel={action.label}>
                {/* `blur={false}`: four of these plus the Guardian card plus the
                    tab bar would be six live blurs on one screen, and the demo
                    handset is a budget Unisoc. At this size the tinted fill,
                    the edge and the sheen carry the material on their own — the
                    blur is the part you miss least. See the note in `Glass`. */}
                <Glass padding={space.lg} radius={radius.card} blur={false}>
                  <View
                    style={[
                      styles.actionIcon,
                      { backgroundColor: t.fillSoft, borderRadius: radius.md },
                    ]}
                  >
                    {action.icon}
                  </View>
                  <Text style={[type.bodyStrong, { color: t.text, marginTop: space.md }]}>
                    {action.label}
                  </Text>
                  <Text style={[type.caption, { color: t.textFaint, marginTop: 2 }]}>
                    {action.hint}
                  </Text>
                </Glass>
              </Pressable3D>
            </Reveal>
          ))}
        </View>
      </ScrollView>
    </Aurora>
  );
};

// ---------------------------------------------------------------------------
// SOS
// ---------------------------------------------------------------------------

/**
 * The SOS button, with a sonar ping.
 *
 * A ring expands from the button's centre and fades as it goes, every 2.6 s.
 * It is a fourth motion idea on purpose, distinct from the other three:
 *
 * * `LoadingScreen` pulses **in place** — a thing working.
 * * `Aurora` **drifts** — weather.
 * * `Reveal` **arrives once** — an event.
 * * This **emanates outward** — a thing broadcasting, which is literally what
 *   SOS does. The outward direction is the meaning.
 *
 * Opacity falls to zero well before the ring reaches full size, so the loop has
 * no visible restart; the ring is already invisible when it snaps back.
 *
 * `pointerEvents="none"` on the ring, or it eats taps aimed at the button
 * underneath it — the ring is larger than its parent at full scale.
 */
const SosButton: React.FC<{ onPress: () => void }> = ({ onPress }) => {
  const { g, type, space, radius, t } = useTheme();
  const ping = useAnimatedValue(0);

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(ping, {
        toValue: 1,
        duration: 2_600,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [ping]);

  return (
    <Pressable3D onPress={onPress} tilt={3} accessibilityLabel="Send an SOS">
      <View>
        <Animated.View
          pointerEvents="none"
          style={[
            styles.ping,
            {
              borderRadius: radius.card,
              borderColor: t.danger,
              opacity: ping.interpolate({
                inputRange: [0, 0.65, 1],
                outputRange: [0.45, 0, 0],
              }),
              transform: [
                { scale: ping.interpolate({ inputRange: [0, 1], outputRange: [1, 1.12] }) },
              ],
            },
          ]}
        />
        <Grad
          colors={g.alarm}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[
            styles.sos,
            { borderRadius: radius.card, padding: space.lg, shadowColor: '#E11D48' },
          ]}
        >
          <Ionicons name="alert-circle" size={30} color="#FFFFFF" />
          <View style={{ marginLeft: space.md }}>
            <Text style={[type.heading, onGradient, styles.sosTitle]}>SOS Emergency</Text>
            <Text style={[type.caption, onGradient, styles.sosHint]}>
              Sends your location to your contacts
            </Text>
          </View>
        </Grad>
      </View>
    </Pressable3D>
  );
};

// ---------------------------------------------------------------------------
// Protection
// ---------------------------------------------------------------------------

/**
 * What is actually protecting the user right now. Three rows, all read from real
 * state, and a count in the header so the card can be understood at a glance.
 *
 * The zone row shows what the **OS** reports, not what the user asked for. Those
 * two disagree whenever background location has been revoked, and the honest
 * reading — "you switched it on and it is not running" — is the one worth
 * surfacing. `regionCount` of 0 with monitoring on is also shown as its own
 * state, because that is the normal case outside Dhaka and it is not a fault.
 */
const ProtectionCard: React.FC<{
  zones: ZoneWatchStatus | null;
  zoneAlertsEnabled: boolean;
  voiceArmed: boolean;
  shakeEnabled: boolean;
  onPress: () => void;
}> = ({ zones, zoneAlertsEnabled, voiceArmed, shakeEnabled, onPress }) => {
  const { t, type, space, radius } = useTheme();

  const monitoring = Boolean(zones?.monitoring);
  const regions = zones?.regionCount ?? 0;

  const rows = [
    {
      key: 'zones',
      icon: 'location' as const,
      label: 'Risk zone alerts',
      on: monitoring,
      detail: monitoring
        ? regions > 0
          ? `Watching ${regions} ${regions === 1 ? 'zone' : 'zones'} nearby`
          : 'Active — nothing nearby to watch'
        : zoneAlertsEnabled
          ? 'Switched on, but not running'
          : 'Off',
      // The one case that is a problem rather than a choice: the user asked for
      // it and the OS is not doing it.
      warn: zoneAlertsEnabled && !monitoring,
    },
    {
      key: 'voice',
      icon: 'mic' as const,
      label: 'Shout for help',
      on: voiceArmed,
      detail: voiceArmed ? 'Listening for your phrases' : 'Off',
      warn: false,
    },
    {
      key: 'shake',
      icon: 'phone-portrait' as const,
      label: 'Shake for help',
      on: shakeEnabled,
      detail: shakeEnabled ? 'Watching for a hard shake' : 'Off',
      warn: false,
    },
  ];

  const active = rows.filter((row) => row.on).length;

  return (
    <Pressable3D onPress={onPress} accessibilityLabel="Open Guardian settings">
      <Glass padding={space.lg} radius={radius.card} elevated>
        <View style={styles.cardHead}>
          <View style={styles.headerText}>
            <Text style={[type.overline, styles.overline, { color: t.textFaint }]}>
              Guardian
            </Text>
            <Text style={[type.title, { color: t.text, marginTop: 2 }]}>
              {active === 0
                ? 'Nothing is armed'
                : active === rows.length
                  ? 'Fully protected'
                  : `${active} of ${rows.length} armed`}
            </Text>
          </View>
          <View
            style={[
              styles.countBadge,
              {
                borderRadius: radius.pill,
                backgroundColor: active === 0 ? t.warnSoft : t.okSoft,
              },
            ]}
          >
            <Ionicons
              name={active === 0 ? 'shield-outline' : 'shield-checkmark'}
              size={18}
              color={active === 0 ? t.warn : t.ok}
            />
          </View>
        </View>

        <View style={{ marginTop: space.md }}>
          {rows.map((row) => (
            <View key={row.key} style={[styles.row, { paddingVertical: space.sm }]}>
              <View
                style={[
                  styles.rowDot,
                  {
                    backgroundColor: row.warn
                      ? t.warnSoft
                      : row.on
                        ? t.okSoft
                        : t.fillSoft,
                  },
                ]}
              >
                <Ionicons
                  name={row.icon}
                  size={14}
                  color={row.warn ? t.warn : row.on ? t.ok : t.textFaint}
                />
              </View>
              <View style={styles.headerText}>
                <Text style={[type.bodyStrong, { color: t.text }]}>{row.label}</Text>
                <Text style={[type.caption, { color: row.warn ? t.warn : t.textSoft }]}>
                  {row.detail}
                </Text>
              </View>
            </View>
          ))}
        </View>

        <View style={[styles.cta, { marginTop: space.sm }]}>
          <Text style={[type.label, { color: t.brand }]}>Open Guardian</Text>
          <Ionicons name="chevron-forward" size={14} color={t.brand} />
        </View>
      </Glass>
    </Pressable3D>
  );
};

const styles = StyleSheet.create({
  fill: { flex: 1 },
  content: { flexGrow: 1 },
  headerRow: { flexDirection: 'row', alignItems: 'center' },
  headerText: { flex: 1 },
  overline: { textTransform: 'uppercase' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  gridItem: { width: '48%', marginBottom: 12 },
  actionIcon: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },

  sos: { flexDirection: 'row', alignItems: 'center', shadowOpacity: 0.4, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 8 },
  sosTitle: { color: '#FFFFFF' },
  sosHint: { color: 'rgba(255,255,255,0.85)', marginTop: 2 },
  ping: { ...StyleSheet.absoluteFill, borderWidth: 2 },

  cardHead: { flexDirection: 'row', alignItems: 'flex-start' },
  countBadge: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', alignItems: 'center' },
  rowDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  cta: { flexDirection: 'row', alignItems: 'center', gap: 4 },
});

export default HomeScreen;
