/**
 * The Map tab, as a stack. D09.
 *
 * The tab used to be `MapScreen` on its own, which left nowhere to push a screen
 * that belongs to the map. The news page does: it is the articles behind the pins
 * that are on screen, so it reads as a drill-down from the map and not as a
 * separate section of the app.
 *
 * `MapStackParamList` has declared `CrimeReport` and `ReportDetails` since D01 and
 * neither has ever had a screen — reporting lives under the Reports stack. They are
 * deliberately not registered here: registering a route to a screen that does not
 * exist is worse than the dangling declaration, and the declaration is being left
 * alone rather than tidied inside a feature sprint.
 */
import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MapStackParamList } from '../types';
import MapScreen from '../screens/Map/MapScreen';
import NewsScreen from '../screens/Map/NewsScreen';
import JourneyScreen from '../screens/Map/JourneyScreen';

const Stack = createNativeStackNavigator<MapStackParamList>();

const MapNavigator: React.FC = () => (
  <Stack.Navigator screenOptions={{ headerShown: false }}>
    <Stack.Screen name="MapView" component={MapScreen} />
    <Stack.Screen name="News" component={NewsScreen} />
    {/* JG3. The journey behind the card -- its state in a sentence, the answer
        button, and what has already been sent. A drill-down from the map for
        the same reason the news page is one: it is about the thing currently on
        screen, not a section of its own. */}
    <Stack.Screen name="Journey" component={JourneyScreen} />
  </Stack.Navigator>
);

export default MapNavigator;
