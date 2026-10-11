import React from 'react';
import { StyleSheet } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useIsFocused } from '@react-navigation/native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { MainTabParamList } from '../types';
import { BlurTargetProvider, ClaimBlurTarget } from '../components/motion';
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
 * What the tab bar blurs.
 *
 * Each tab's screen is wrapped in one of these, and the **focused** one hands
 * itself to the `BlurTargetProvider` below as the blur target. The bar then
 * frosts the live screen rather than falling back to an opaque fill, which is
 * what it did on Android for as long as nothing was in scope for it to sample.
 *
 * Why a wrapper per screen instead of one around the navigator: `tabBar`
 * renders the bar *inside* `Tab.Navigator`, so a wrapper around the navigator
 * would be an ancestor of the bar and of its own target at once — the
 * arrangement that killed the render thread, documented in `BlurTarget.tsx`.
 * Wrapping only the screens leaves the bar a sibling of them, which is the one
 * shape that works.
 *
 * `useIsFocused` is read here, in a component that re-renders on focus, rather
 * than inside `ClaimBlurTarget`: all four screens stay mounted in a tab
 * navigator, so without it the target would be whichever tab mounted last.
 */
const withBlurTarget = (Screen: React.ComponentType<any>): React.FC<any> => {
  const Wrapped: React.FC<any> = props => {
    const focused = useIsFocused();
    return (
      <ClaimBlurTarget active={focused} style={styles.fill}>
        <Screen {...props} />
      </ClaimBlurTarget>
    );
  };
  // So the React tree still names the screen in a stack trace or the devtools.
  Wrapped.displayName = `WithBlurTarget(${Screen.displayName || Screen.name || 'Screen'})`;
  return Wrapped;
};

const HomeTab = withBlurTarget(HomeScreen);
const MapTab = withBlurTarget(MapNavigator);
const ReportsTab = withBlurTarget(ReportsNavigator);
const ProfileTab = withBlurTarget(ProfileNavigator);

const styles = StyleSheet.create({ fill: { flex: 1 } });

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
    // Renders no view of its own — see `BlurTarget.tsx`. It is only here to be
    // *above* the bar, so the bar has a target to read.
    <BlurTargetProvider>
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
          component={HomeTab}
          options={{
            tabBarLabel: 'Home',
            tabBarIcon: HomeIcon,
          }}
        />
        <Tab.Screen
          name="Map"
          component={MapTab}
          options={{
            tabBarLabel: 'Map',
            tabBarIcon: MapIcon,
          }}
        />
        <Tab.Screen
          name="Reports"
          component={ReportsTab}
          options={{
            tabBarLabel: 'Reports',
            tabBarIcon: ReportsIcon,
          }}
        />
        <Tab.Screen
          name="Profile"
          component={ProfileTab}
          options={{
            tabBarLabel: 'Profile',
            tabBarIcon: ProfileIcon,
          }}
        />
      </Tab.Navigator>
    </BlurTargetProvider>
  );
};

export default MainNavigator;
