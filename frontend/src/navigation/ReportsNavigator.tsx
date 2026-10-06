import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ReportsStackParamList } from '../types';
import ReportsScreen from '../screens/Reports/ReportsScreen';
import AddReportScreen from '../screens/Reports/AddReportScreen';
import ReportDetailsScreen from '../screens/Reports/ReportDetailsScreen';

const Stack = createNativeStackNavigator<ReportsStackParamList>();

const ReportsNavigator: React.FC = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="MyReports" component={ReportsScreen} />
      <Stack.Screen name="AddReport" component={AddReportScreen} />
      <Stack.Screen name="ReportDetails" component={ReportDetailsScreen} />
    </Stack.Navigator>
  );
};

export default ReportsNavigator;
