import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { MainTabParamList } from '../types';
import TabBar from './TabBar';

// Import screens and navigators
import HomeScreen from '../screens/Home/HomeScreen';
import MapNavigator from './MapNavigator';
import ReportsNavigator from './ReportsNavigator';
import ProfileNavigator from './ProfileNavigator';

const Tab = createBottomTabNavigator<MainTabParamList>();

// Icon components for tab bar with filled/outlined variants for active/inactive states
const HomeIcon = ({
  color,
  size,
  focused,
}: {
  color: string;
  size: number;
  focused: boolean;
}) => (
  <Ionicons
    name={focused ? 'home' : 'home-outline'}
    size={size}
    color={color}
  />
);

const MapIcon = ({
  color,
  size,
  focused,
}: {
  color: string;
  size: number;
  focused: boolean;
}) => (
  <Ionicons name={focused ? 'map' : 'map-outline'} size={size} color={color} />
);

const ReportsIcon = ({
  color,
  size,
  focused,
}: {
  color: string;
  size: number;
  focused: boolean;
}) => (
  <MaterialCommunityIcons
    name={focused ? 'file-document' : 'file-document-outline'}
    size={size}
    color={color}
  />
);

const ProfileIcon = ({
  color,
  size,
  focused,
}: {
  color: string;
  size: number;
  focused: boolean;
}) => (
  <Ionicons
    name={focused ? 'person' : 'person-outline'}
    size={size}
    color={color}
  />
);

/**
 * The four tabs.
 *
 * `tabBar` replaces the stock bar with `TabBar` — floating, blurred, iOS-style.
 * That file explains why it is hand-built; the short version is that the stock
 * bar cannot detach from the bottom edge, and glass needs something behind it.
 *
 * Two consequences of the bar now floating *over* content rather than sitting
 * beneath it:
 *
 * * `tabBarStyle` and the tint options are gone. Colour comes from `useTheme()`
 *   inside `TabBar`, so it follows dark mode; the old options read a
 *   module-level `colors` and could not.
 * * A screen at the root of a tab has to reserve room at the bottom or its last
 *   row sits under the bar. That number is `TAB_BAR_CLEARANCE` in
 *   `navigation/metrics.ts` — a leaf module, because exporting it from here put
 *   four require cycles in the bundle. A *pushed* screen needs nothing: the bar
 *   slides out of the way, see `TabBar`.
 */
const MainNavigator: React.FC = () => {
  return (
    <Tab.Navigator
      tabBar={(props) => <TabBar {...props} />}
      screenOptions={{
        headerShown: false,
        // Kept so content can scroll behind the floating bar instead of being
        // clipped above it — the blur has nothing to work with otherwise.
        tabBarStyle: { position: 'absolute' },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          tabBarLabel: 'Home',
          tabBarIcon: HomeIcon,
        }}
      />
      <Tab.Screen
        name="Map"
        component={MapNavigator}
        options={{
          tabBarLabel: 'Map',
          tabBarIcon: MapIcon,
        }}
      />
      <Tab.Screen
        name="Reports"
        component={ReportsNavigator}
        options={{
          tabBarLabel: 'Reports',
          tabBarIcon: ReportsIcon,
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileNavigator}
        options={{
          tabBarLabel: 'Profile',
          tabBarIcon: ProfileIcon,
        }}
      />
    </Tab.Navigator>
  );
};

export default MainNavigator;
