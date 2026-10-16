/**
 * Profile. The settings hub, and the home of the full theme control.
 *
 * ## The Alerts row came back
 *
 * It was removed, and this note used to explain why: `AlertPreferencesScreen`
 * configures **server-pushed** alerts, and that channel was off at both ends —
 * no `extra.eas.projectId` in the app, so `getExpoPushTokenAsync` was never
 * called and the server had no token to send to, and `PUSH_ENABLED=false` on the
 * backend. A settings screen for a switched-off pipeline, with a test button
 * that fails. The screen was kept and only the route to it removed, with the
 * note that it "becomes a one-line change once there is an EAS project".
 *
 * JG2 is that change. There is an EAS project, FCM credentials are uploaded to
 * it, `PUSH_ENABLED=true`, and a check-in has been delivered to a real phone and
 * answered. `Send me a test alert` works.
 *
 * It is back for a second reason that did not exist before: that screen holds
 * the delivery diagnosis, which is the only place in the app that reports the
 * nine ways push can fail — **three of them silently**, including the one JG2
 * found last, where Android freezes the app and a notification waits for the
 * phone to be woken. That is a question a user will have, and it had nowhere to
 * be asked.
 *
 * The alerts that work without any of this — approaching a risk zone — are still
 * **local** notifications raised by the OS geofence handler, and their switch is
 * still on the Guardian screen with the rest of the automatic behaviour.
 *
 * ## The four dead rows are gone
 *
 * "Tracking History", "Settings", "About" and "Help & Support" were all
 * `onPress: () => {}` — rows that looked tappable, were tappable, and did
 * nothing. Four of the ten. A judge taps one, nothing happens, and now every
 * other row is suspect.
 *
 * A row that does nothing is worse than a missing row: it spends the user's
 * trust to look more complete. What was real is kept and grouped; the version
 * string that "About" would have shown is in the footer, where it already was.
 *
 * ## Grouped, because ten flat rows is a list and not a settings screen
 *
 * Three sections — Account, Safety, Appearance — each its own pane of glass.
 * Grouping is what lets a user find "Guardian" without reading all ten labels,
 * and it is why Appearance can sit at the bottom and still be discoverable: it
 * has a heading, so it is scannable rather than hidden.
 *
 * ## The header is the one place the Aurora gradient fills a whole surface
 *
 * Everywhere else the gradient is a small fill (a button, the tab pill) over the
 * ambient field. Here it is the full header block, which is what gives the
 * screen a top edge and stops the avatar floating in the middle of nothing.
 */

import React from 'react';
import { View, Text, StyleSheet, ScrollView, Alert, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTheme } from '../../theme/ThemeProvider';
import { onGradient } from '../../theme/type';
import {
  Aurora,
  Glass,
  Reveal,
  Pressable3D,
  ThemeChoice,
} from '../../components/motion';
import { TAB_BAR_CLEARANCE } from '../../navigation/metrics';
import { useAuthStore } from '../../store';
import { ProfileStackParamList } from '../../types';

// @ts-ignore - generated types fight `style` in this RN version
const Grad = LinearGradient as any;

type ProfileScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'ProfileView'
>;

interface Props {
  navigation: ProfileScreenNavigationProp;
}

// `icon` must be typed, not inferred. An array literal infers `icon: string`,
// and Ionicons' `name` prop is a union of ~1,300 glyph names, so a plain string
// is not assignable. Typing it here also means a typo in an icon name is a
// compile error rather than a silently blank icon.
type MenuItem = {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  title: string;
  hint?: string;
  onPress: () => void;
};

const ProfileScreen: React.FC<Props> = ({ navigation }) => {
  const { t, g, type, space, radius } = useTheme();
  const { user, logout } = useAuthStore();
  const insets = useSafeAreaInsets();

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout',
        style: 'destructive',
        onPress: async () => {
          try {
            await logout();
          } catch {
            Alert.alert('Error', 'Failed to logout');
          }
        },
      },
    ]);
  };

  const account: MenuItem[] = [
    {
      icon: 'person-outline',
      title: 'Edit profile',
      hint: 'Name, phone, photo',
      onPress: () => navigation.navigate('EditProfile'),
    },
    {
      icon: 'call-outline',
      title: 'Emergency contacts',
      hint: 'Who an SOS reaches',
      onPress: () => navigation.navigate('EmergencyContacts'),
    },
  ];

  const safety: MenuItem[] = [
    {
      // B6a/B8. The automatic protections: zone alerts, voice SOS, shake SOS.
      // First in the section because it is the one a user actually needs to
      // visit — the other switches are useless until these are armed.
      icon: 'shield-checkmark-outline',
      title: 'Guardian',
      hint: 'Automatic SOS and zone alerts',
      onPress: () => navigation.navigate('Guardian'),
    },
    {
      icon: 'mic-outline',
      title: 'SOS hot words',
      hint: 'Phrases that trigger an SOS',
      onPress: () => navigation.navigate('SOSHotWords'),
    },
    {
      icon: 'document-text-outline',
      title: 'SOS history',
      hint: 'Every alert you have sent',
      onPress: () => navigation.navigate('SOSHistory'),
    },
    {
      // Back, after JG2. It was removed because the pipeline behind it was off
      // at both ends -- see the note at the top of this file -- and both ends
      // are now on: `extra.eas.projectId` is set, FCM credentials are uploaded,
      // and the backend runs with `PUSH_ENABLED=true`. `Send me a test alert`
      // works, and the delivery diagnosis is the only place that reports the
      // nine ways push can fail, three of which fail silently.
      icon: 'notifications-outline',
      title: 'Alerts',
      hint: 'What to be told about, and whether it is working',
      onPress: () => navigation.navigate('AlertPreferences'),
    },
    {
      // B9. In Safety rather than a section of its own, because the question it
      // answers is a safety question: whether the protections above are actually
      // running.
      //
      // Last in the section, below `Alerts`, and the two are deliberately in
      // that order: everything above is something you arm, and this is the row
      // you look for when you suspect one of them is not working.
      icon: 'pulse-outline',
      title: 'System status',
      hint: 'Is your map up to date',
      onPress: () => navigation.navigate('SystemStatus'),
    },
  ];

  return (
    <Aurora intensity="ambient" style={styles.fill}>
      <ScrollView
        style={styles.fill}
        contentContainerStyle={{ paddingBottom: insets.bottom + TAB_BAR_CLEARANCE }}
        showsVerticalScrollIndicator={false}
      >
        {/* Header. Bleeds to the screen edges and under the status bar. */}
        <Grad
          colors={g.aurora}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[
            styles.header,
            {
              paddingTop: insets.top + space.xl,
              paddingBottom: space.xl,
              borderBottomLeftRadius: radius.sheet,
              borderBottomRightRadius: radius.sheet,
            },
          ]}
        >
          <Reveal index={0} from="scale">
            <View style={styles.avatarRing}>
              {user?.avatar_url ? (
                <Image source={{ uri: user.avatar_url }} style={styles.avatar} />
              ) : (
                <View style={styles.avatarPlaceholder}>
                  <Ionicons name="person" size={48} color="#FFFFFF" />
                </View>
              )}
            </View>
          </Reveal>

          <Reveal index={1}>
            <Text
              // `onBrand`, which is the token for text that sits ON the Aurora
              // gradient. Without a colour it fell back to the platform
              // default -- black -- so the user's own name was the one
              // unreadable thing on the header. The two lines under it carry
              // their colour in `styles.sub`, which is why they looked right.
              style={[
                type.title,
                onGradient,
                styles.centred,
                { color: t.onBrand, marginTop: space.md },
              ]}
            >
              {user?.name ?? 'Your profile'}
            </Text>
            <Text style={[type.small, onGradient, styles.centred, styles.sub]}>
              {user?.email}
            </Text>
            <Text style={[type.small, onGradient, styles.centred, styles.sub]}>
              {user?.phone || 'No phone number'}
            </Text>
          </Reveal>
        </Grad>

        <View style={{ padding: space.lg }}>
          <Section index={2} title="Account" items={account} />
          <Section index={3} title="Safety" items={safety} />

          {/* Appearance. The three-state control, not the two-state toggle: this
              is where a preference belongs, and it is the only control that can
              get the user back to "follow my phone". */}
          <Reveal index={4} style={{ marginTop: space.xl }}>
            <Text style={[type.overline, styles.overline, { color: t.textFaint }]}>
              Appearance
            </Text>
            <Glass padding={space.lg} radius={radius.card} style={{ marginTop: space.sm }}>
              <Text style={[type.bodyStrong, { color: t.text }]}>Theme</Text>
              <Text style={[type.caption, { color: t.textSoft, marginBottom: space.md }]}>
                System follows your phone's light and dark setting.
              </Text>
              <ThemeChoice />
            </Glass>
          </Reveal>

          <Reveal index={5} style={{ marginTop: space.xl }}>
            <Pressable3D onPress={handleLogout} tilt={3} accessibilityLabel="Log out">
              <Glass padding={space.md} radius={radius.md}>
                <View style={styles.logoutRow}>
                  <Ionicons name="log-out-outline" size={20} color={t.danger} />
                  <Text style={[type.bodyStrong, { color: t.danger, marginLeft: space.sm }]}>
                    Log out
                  </Text>
                </View>
              </Glass>
            </Pressable3D>
          </Reveal>

          <Reveal index={6}>
            <Text
              style={[
                type.caption,
                styles.centred,
                { color: t.textFaint, marginTop: space.xl },
              ]}
            >
              Meridian v1.0.0
            </Text>
          </Reveal>
        </View>
      </ScrollView>
    </Aurora>
  );
};

/**
 * One titled group of rows on a single pane.
 *
 * Dividers are drawn between rows and not after the last one — a trailing
 * divider inside a rounded pane cuts across it and is the detail that makes a
 * grouped list look unfinished.
 */
const Section: React.FC<{ index: number; title: string; items: MenuItem[] }> = ({
  index,
  title,
  items,
}) => {
  const { t, type, space, radius } = useTheme();

  return (
    <Reveal index={index} style={{ marginTop: space.lg }}>
      <Text style={[type.overline, styles.overline, { color: t.textFaint }]}>
        {title}
      </Text>
      {/* These scroll, and a blurred surface is a per-frame GPU cost while it
          moves. Fill, edge and sheen only — see the note in `Glass`. */}
      <Glass padding={0} radius={radius.card} blur={false} style={{ marginTop: space.sm }}>
        {items.map((item, i) => (
          <Pressable3D
            key={item.title}
            onPress={item.onPress}
            tilt={0}
            haptic={false}
            accessibilityLabel={item.title}
          >
            <View
              style={[
                styles.row,
                {
                  padding: space.lg,
                  borderBottomWidth: i === items.length - 1 ? 0 : StyleSheet.hairlineWidth,
                  borderBottomColor: t.line,
                },
              ]}
            >
              <View
                style={[
                  styles.rowIcon,
                  { backgroundColor: t.brandSoft, borderRadius: radius.sm },
                ]}
              >
                <Ionicons name={item.icon} size={18} color={t.brand} />
              </View>
              <View style={styles.rowText}>
                <Text style={[type.bodyStrong, { color: t.text }]}>{item.title}</Text>
                {item.hint ? (
                  <Text style={[type.caption, { color: t.textFaint }]}>{item.hint}</Text>
                ) : null}
              </View>
              <Ionicons name="chevron-forward" size={18} color={t.textFaint} />
            </View>
          </Pressable3D>
        ))}
      </Glass>
    </Reveal>
  );
};

const styles = StyleSheet.create({
  fill: { flex: 1 },
  header: { alignItems: 'center', paddingHorizontal: 24 },
  avatarRing: {
    width: 96,
    height: 96,
    borderRadius: 48,
    overflow: 'hidden',
    borderWidth: 3,
    borderColor: 'rgba(255,255,255,0.5)',
  },
  avatar: { width: '100%', height: '100%' },
  avatarPlaceholder: {
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  centred: { textAlign: 'center' },
  sub: { color: 'rgba(255,255,255,0.9)', marginTop: 2 },
  overline: { textTransform: 'uppercase' },
  row: { flexDirection: 'row', alignItems: 'center' },
  rowIcon: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  rowText: { flex: 1 },
  logoutRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
});

export default ProfileScreen;
