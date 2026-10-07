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

// Circle was added in D01 for the risk overlay: a risk flag has a radius, and a
// pin alone implies a point when the claim is about an area.
export { Marker, PROVIDER_GOOGLE, Callout, Polyline, Circle };
export default MapView;
