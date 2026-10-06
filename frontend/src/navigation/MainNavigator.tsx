import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MainTabParamList } from '../types';
import { colors } from '../theme';

// Import screens and navigators
import HomeScreen from '../screens/Home/HomeScreen';
import MapScreen from '../screens/Map/MapScreen';
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

const MainNavigator: React.FC = () => {
  const insets = useSafeAreaInsets();

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: {
          backgroundColor: colors.white,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          paddingBottom: insets.bottom,
          paddingTop: 8,
          height: 54 + insets.bottom,
          elevation: 8,
          shadowColor: colors.shadowDark,
          shadowOffset: { width: 0, height: -2 },
          shadowOpacity: 0.1,
          shadowRadius: 8,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          marginTop: 4,
        },
        tabBarIconStyle: {
          marginTop: 4,
        },
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
        component={MapScreen}
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
