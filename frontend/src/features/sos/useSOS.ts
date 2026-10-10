/**
 * The SOS flow, in one place. D09, defect 14.
 *
 * Before this, `HomeScreen` had a working SOS — token refresh, forced location
 * fetch, upload progress, the two-phase "uploading / sending" distinction — and
 * `MapScreen`'s identically-styled red button was a `// TODO` that popped an alert
 * saying SOS was activated. Two buttons, one of them a lie, on the screen a user is
 * most likely to be looking at when something is happening around them.
 *
 * This is a straight extraction of the working one, not a rewrite. Every comment
 * below describing a bug that was fixed on a phone came with the code, and the
 * behaviour is unchanged — which is the point: the fix for defect 14 must not also
 * be the day SOS changed.
 *
 * `useSOS()` owns the state and the network call. `SOSFlow` renders the two modals.
 * A screen wires SOS in three lines:
 *
 *     const sos = useSOS();
 *     <TouchableOpacity onPress={sos.start} />
 *     <SOSFlow sos={sos} />
 */
import { useCallback, useEffect, useState } from 'react';
import { Alert } from 'react-native';
import { Accelerometer } from 'expo-sensors';
import { useLocationStore } from '../../store';
import AuthService from '../../services/auth.service';
import { API_BASE_URL } from '../../constants/app.constants';

/** Which half of the send we are in. The upload finishes long before the alert does. */
export type SosStage = 'uploading' | 'sending';

export interface SosController {
  cameraVisible: boolean;
  sending: boolean;
  progress: number;
  stage: SosStage;
  /** Open the camera. Safe to call from a button or from the shake listener. */
  start: () => void;
  cancel: () => void;
  onVideoRecorded: (uri: string) => Promise<void>;
  onCameraError: (message: string) => void;
}

/**
 * Shake-to-SOS threshold, in g.
 *
 * Carried over as it was found: the comment in `HomeScreen` said 3.5 and the code
 * said 6.0. The code wins here because 6.0 is what has actually been used on a
 * device, and changing a trigger threshold while extracting a hook would mean two
 * changes in one commit with only one of them tested. Reconciling it properly with
 * a measurement is B5.
 */
const SHAKE_THRESHOLD = 6.0;

export function useSOS(): SosController {
  const { currentLocation, getCurrentLocation } = useLocationStore();

  const [cameraVisible, setCameraVisible] = useState(false);
  const [sending, setSending] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<SosStage>('uploading');

  const start = useCallback(() => {
    setCameraVisible(true);
    // Ask for a fix now rather than discovering we have none after the recording.
    if (!currentLocation) {
      getCurrentLocation().catch(err => console.log('Bg location fetch failed:', err));
    }
  }, [currentLocation, getCurrentLocation]);

  const onVideoRecorded = useCallback(async (uri: string) => {
    setCameraVisible(false);
    setSending(true);

    try {
      // Fetched at trigger time, not read from the store.
      //
      // `useAuthStore().token` is captured once by `initialize()` and never
      // updated, and a Supabase access token lasts an hour -- so an SOS sent from a
      // session older than that went out with a dead token and the backend answered
      // 401 after the video had already uploaded. `getAuthToken()` asks Supabase,
      // which refreshes if needed. This is the single most important call in the
      // app to get right; it must not depend on how long the app has been open.
      const token = await AuthService.getAuthToken();
      if (!token) {
        throw new Error('You are not logged in. Please Logout and Login again.');
      }

      // Read straight from the store rather than through the closure: this
      // function was created on an earlier render and `currentLocation` captured
      // there can be stale, or null from before the fetch above returned.
      let finalLocation = useLocationStore.getState().currentLocation;
      if (!finalLocation) {
        try {
          await getCurrentLocation();
          finalLocation = useLocationStore.getState().currentLocation;
        } catch (e: any) {
          throw new Error(e.message || 'Location data unavailable. Cannot send SOS.');
        }
      }
      if (!finalLocation) {
        throw new Error('Location not available. Please enable GPS and try again.');
      }

      const formData = new FormData();
      formData.append('latitude', String(finalLocation.latitude));
      formData.append('longitude', String(finalLocation.longitude));

      const fileType = uri.split('.').pop() || 'mp4';
      // @ts-ignore - React Native's FormData takes this shape for a file
      formData.append('video', {
        uri,
        name: `sos_video.${fileType}`,
        type: `video/${fileType}`,
      });

      setProgress(0);
      setStage('uploading');

      // Progress simulation, so the bar moves even on a fast local network where
      // `onprogress` may fire once at 100%.
      let simulated = 0;
      const ticker = setInterval(() => {
        simulated += Math.random() * 5;
        if (simulated > 98) simulated = 98;
        setProgress(prev => Math.max(prev, Math.floor(simulated)));
      }, 200);

      // XHR rather than the api.service axios client, deliberately: this is the one
      // request in the app that needs real upload progress, and `onUploadProgress`
      // does not fire on React Native's axios adapter.
      const data: any = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_BASE_URL}/sos/trigger`);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        xhr.upload.onprogress = event => {
          if (event.lengthComputable) {
            const realPercent = Math.round((event.loaded / event.total) * 100);
            setProgress(prev => {
              const next = Math.max(prev, realPercent);
              simulated = next;
              return next;
            });
            // Once the bytes are gone, the wait is the server's: it is talking to
            // the SMTP relay. Saying "uploading 98%" through that is how a working
            // SOS looks broken -- which is exactly how it read the first time this
            // was run on a phone. Tell the truth instead.
            if (event.loaded >= event.total) {
              setStage('sending');
            }
          }
        };

        xhr.onload = () => {
          clearInterval(ticker);
          if (xhr.status >= 200 && xhr.status < 300) {
            setProgress(100);
            try {
              resolve(JSON.parse(xhr.response));
            } catch {
              reject(new Error('Invalid server response'));
            }
          } else if (xhr.status === 401) {
            reject(new Error('Session expired. Please start the App again or Logout/Login.'));
          } else {
            try {
              const errData = JSON.parse(xhr.response);
              reject(new Error(errData.detail || errData.message || 'Failed to send SOS'));
            } catch {
              reject(new Error(`Server Error: ${xhr.status}`));
            }
          }
        };

        xhr.onerror = () => {
          clearInterval(ticker);
          reject(new Error('Network request failed. Please check internet connection.'));
        };

        xhr.send(formData);
      });

      Alert.alert(
        'SOS Sent!',
        `Emergency services and ${data.contacts_notified} contacts have been notified.\n` +
          `Police Stations found: ${data.police_stations_found ?? 0}`,
        [{ text: 'OK' }],
      );
    } catch (error: any) {
      console.error('SOS Error:', error);
      Alert.alert('SOS Failed', error.message || 'Could not send SOS alert. Please try again.');
    } finally {
      setSending(false);
    }
  }, [getCurrentLocation]);

  const cancel = useCallback(() => setCameraVisible(false), []);

  const onCameraError = useCallback((message: string) => {
    setCameraVisible(false);
    Alert.alert('Recording Error', message);
  }, []);

  // Shake to trigger. Lives in the hook so it follows SOS onto whichever screen
  // consumes it, rather than only working while Home happens to be mounted.
  useEffect(() => {
    Accelerometer.setUpdateInterval(200);
    const subscription = Accelerometer.addListener(({ x, y, z }) => {
      if (Math.sqrt(x * x + y * y + z * z) > SHAKE_THRESHOLD) {
        if (!cameraVisible && !sending) {
          start();
        }
      }
    });
    return () => subscription && subscription.remove();
  }, [cameraVisible, sending, start]);

  return {
    cameraVisible,
    sending,
    progress,
    stage,
    start,
    cancel,
    onVideoRecorded,
    onCameraError,
  };
}
