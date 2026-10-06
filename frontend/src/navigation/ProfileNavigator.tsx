import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ProfileStackParamList } from '../types';
import ProfileScreen from '../screens/Profile/ProfileScreen';
import EditProfileScreen from '../screens/Profile/EditProfileScreen';
import EmergencyContactsScreen from '../screens/Profile/EmergencyContactsScreen';
import SOSHotWordsScreen from '../screens/Profile/SOSHotWordsScreen';

const Stack = createNativeStackNavigator<ProfileStackParamList>();

const ProfileNavigator: React.FC = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="ProfileView" component={ProfileScreen} />
      <Stack.Screen name="EditProfile" component={EditProfileScreen} />
      <Stack.Screen
        name="EmergencyContacts"
        component={EmergencyContactsScreen}
      />
      <Stack.Screen name="SOSHotWords" component={SOSHotWordsScreen} />
    </Stack.Navigator>
  );
};

export default ProfileNavigator;
