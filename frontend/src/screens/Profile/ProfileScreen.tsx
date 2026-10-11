import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, spacing, borderRadius, fontSize } from '../../theme';
import { useAuthStore } from '../../store';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ProfileStackParamList } from '../../types';

type ProfileScreenNavigationProp = NativeStackNavigationProp<
  ProfileStackParamList,
  'ProfileView'
>;

interface Props {
  navigation: ProfileScreenNavigationProp;
}

const ProfileScreen: React.FC<Props> = ({ navigation }) => {
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
          } catch (error) {
            Alert.alert('Error', 'Failed to logout');
          }
        },
      },
    ]);
  };

  // `icon` must be typed, not inferred. An array literal infers `icon: string`,
  // and Ionicons' `name` prop is a union of ~1,300 glyph names, so a plain
  // string is not assignable. Typing it here also means a typo in an icon name
  // is a compile error rather than a silently blank icon.
  type MenuItem = {
    icon: React.ComponentProps<typeof Ionicons>['name'];
    title: string;
    onPress: () => void;
  };

  const menuItems: MenuItem[] = [
    {
      icon: 'person-outline',
      title: 'Edit Profile',
      onPress: () => navigation.navigate('EditProfile'),
    },
    {
      icon: 'call-outline',
      title: 'Emergency Contacts',
      onPress: () => navigation.navigate('EmergencyContacts'),
    },
    {
      icon: 'alert-circle-outline',
      title: 'SOS Hot Words',
      onPress: () => navigation.navigate('SOSHotWords'),
    },
    {
      icon: 'document-text-outline',
      title: 'SOS History',
      onPress: () => navigation.navigate('SOSHistory'),
    },
    {
      // B6a/B8. The automatic protections: zone alerts, voice SOS, shake SOS.
      // First among the new rows because it is the one a user actually needs to
      // visit -- the other switches are useless until these are armed.
      icon: 'shield-checkmark-outline',
      title: 'Guardian — automatic SOS & zone alerts',
      onPress: () => navigation.navigate('Guardian'),
    },
    {
      // B6a. Per-category preferences, the hourly cap, a delivery self-test and
      // the alert history. Above the four dead rows below it on purpose: those
      // have been placeholders since D01 and this one works.
      icon: 'notifications-outline',
      title: 'Alerts',
      onPress: () => navigation.navigate('AlertPreferences'),
    },
    { icon: 'time-outline', title: 'Tracking History', onPress: () => {} },
    { icon: 'settings-outline', title: 'Settings', onPress: () => {} },
    { icon: 'information-circle-outline', title: 'About', onPress: () => {} },
    { icon: 'help-circle-outline', title: 'Help & Support', onPress: () => {} },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{
        paddingBottom: insets.bottom + 80,
      }}
    >
      <View style={[styles.header, { paddingTop: insets.top + spacing.xl }]}>
        <View style={styles.avatarContainer}>
          {user?.avatar_url ? (
            <Image source={{ uri: user.avatar_url }} style={styles.avatar} />
          ) : (
            <View style={styles.avatarPlaceholder}>
              <Ionicons name="person" size={60} color={colors.white} />
            </View>
          )}
        </View>
        <Text style={styles.name}>{user?.name}</Text>
        <Text style={styles.email}>{user?.email}</Text>
        <Text style={styles.phone}>{user?.phone || 'No phone number'}</Text>
      </View>

      <View style={styles.section}>
        {menuItems.map((item, index) => (
          <TouchableOpacity
            key={index}
            style={styles.menuItem}
            onPress={item.onPress}
          >
            <View style={styles.menuItemLeft}>
              <Ionicons name={item.icon} size={24} color={colors.primary} />
              <Text style={styles.menuItemText}>{item.title}</Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color={colors.gray400} />
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Ionicons name="log-out-outline" size={24} color={colors.error} />
        <Text style={styles.logoutText}>Logout</Text>
      </TouchableOpacity>

      <View style={styles.footer}>
        <Text style={styles.footerText}>Meridian v1.0.0</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    backgroundColor: colors.primary,
    padding: spacing.xl,
    alignItems: 'center',
  },
  avatarContainer: {
    marginBottom: spacing.md,
    width: 100,
    height: 100,
    borderRadius: 50,
    overflow: 'hidden',
  },
  avatar: {
    width: 100,
    height: 100,
  },
  avatarPlaceholder: {
    width: 100,
    height: 100,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  name: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.white,
    marginBottom: spacing.xs,
  },
  email: {
    fontSize: fontSize.md,
    color: colors.white,
    marginBottom: spacing.xs,
  },
  phone: {
    fontSize: fontSize.md,
    color: colors.white,
  },
  section: {
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
  },
  menuItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  menuItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  menuItemText: {
    fontSize: fontSize.md,
    color: colors.textPrimary,
    marginLeft: spacing.md,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    margin: spacing.lg,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.error,
  },
  logoutText: {
    fontSize: fontSize.md,
    color: colors.error,
    fontWeight: '600',
    marginLeft: spacing.sm,
  },
  footer: {
    padding: spacing.lg,
    alignItems: 'center',
  },
  footerText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});

export default ProfileScreen;
