import { Platform } from 'react-native';
import MapView, {
  Marker,
  PROVIDER_GOOGLE,
  Callout,
  Polyline,
  Circle,
} from 'react-native-maps';

/**
 * Which map engine to render with.
 *
 * **Android:** Google Maps, which is the only option there.
 *
 * **iOS: Apple Maps**, by passing `undefined` — and that is the fix for a blank
 * white map. Every screen used to pass `PROVIDER_GOOGLE` unconditionally, which
 * on iOS forces the Google Maps SDK. **Expo Go for iOS does not contain that
 * SDK**, so `MapView` mounted, laid out, and rendered nothing: no error, no
 * warning, just a white rectangle with the markers invisible on top of it.
 *
 * Apple Maps needs no API key, works in Expo Go today, and supports everything
 * this app asks of a map — markers with `pinColor`, circles, polylines.
 *
 * Google Maps on iOS would need a real API key (so a billing account) *and* a
 * development build rather than Expo Go, because `app.json`'s
 * `ios.config.googleMapsApiKey` is only read when the native project is
 * generated. If the product later wants identical maps on both platforms, that is
 * the work — it is not a one-line change, and it is not needed for the demo.
 *
 * Import this instead of `PROVIDER_GOOGLE` in screens. `PROVIDER_GOOGLE` is still
 * exported for anything that genuinely needs to force Google.
 */
export const MAP_PROVIDER = Platform.OS === 'android' ? PROVIDER_GOOGLE : undefined;

/*
 * ## The map has its own light/dark, and it does not read our theme
 *
 * Every other surface in the app is painted by `useTheme()`. The map is not:
 * the tiles, the roads and the labels are drawn by the native Maps SDK, which
 * has its own colour scheme and its own idea of when to use the dark one.
 *
 * That default is **the phone's** setting. `MapView` resolves
 * `userInterfaceStyle` to `'system'` when the prop is absent, which becomes
 * `MapColorScheme.FOLLOW_SYSTEM` on Android and the matching Apple Maps
 * behaviour on iOS. So a phone in dark mode gave a charcoal map inside an app
 * the user had set to light, and a phone in light mode gave a white map inside
 * the dark app — markers, route lines and the risk circles all picked for the
 * other background.
 *
 * The fix is one prop: pass the app's resolved `mode`.
 *
 * ## Why it also needs a `key`
 *
 * On Android the scheme is read **once**, at map creation, out of
 * `GoogleMapOptions`. `MapViewManager.setUserInterfaceStyle` is literally a
 * no-op with the comment `do nothing (initialProp)`. Changing the prop on a
 * live map therefore does nothing at all.
 *
 * And the Map screen stays mounted when you leave the tab — deliberately, see
 * `detachInactiveScreens` in `MainNavigator.tsx` — so a user who toggles the
 * theme on Settings and walks back to the map would keep the old scheme for the
 * rest of the session. `key={mode}` is what forces a new native map, and it is
 * safe here in a way that the tab-detach case was not: a key change unmounts
 * the whole subtree, so the markers and circles mount fresh into the new map
 * rather than being silently absent from it.
 *
 * `customMapStyle` is the other route and a worse one. It is runtime-settable,
 * but it means carrying a hundred lines of Google style JSON for the dark map
 * and hoping its interaction with the colour scheme stays defined. Two props
 * are cheaper than a stylesheet we would have to maintain by eye.
 *
 * Enforced by `theme.ui.test.ts`, because a map missing this looks fine on a
 * phone whose setting happens to agree with the app's.
 */

// Circle was added in D01 for the risk overlay: a risk flag has a radius, and a
// pin alone implies a point when the claim is about an area.
export { Marker, PROVIDER_GOOGLE, Callout, Polyline, Circle };
export default MapView;
