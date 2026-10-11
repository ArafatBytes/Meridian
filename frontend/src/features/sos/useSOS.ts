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
 *     <TouchableOpacity onPress={() => sos.start('button')} />
 *     <SOSFlow sos={sos} />
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert } from 'react-native';
import { useLocationStore } from '../../store';
import AuthService from '../../services/auth.service';
import { API_BASE_URL } from '../../constants/app.constants';

/** Which half of the send we are in. The upload finishes long before the alert does. */
export type SosStage = 'uploading' | 'sending';

/**
 * What set this SOS off.
 *
 * Carried to the server as `voice_activated` and stored on the incident, so the
 * history screen can say which it was. B8 / S18 — `sos_service` had
 * `voice_activated=False  # the voice path sets this once S18 lands` sitting in
 * it, and this is that path.
 */
export type SosTrigger = 'button' | 'shake' | 'hot-word';

/**
 * How the send ended, for the screen to render.
 *
 * State rather than `Alert.alert`, for two reasons beyond appearance. The
 * native dialog cannot say *what was sent* in any structured way — it takes one
 * string, so the counts had to be jammed into a sentence with a `\n` in it —
 * and it cannot be styled, so the most important moment in the product looked
 * like a system error.
 *
 * `videoAttached` is carried because "SOS sent" while the video was silently
 * dropped is the kind of quiet lie this codebase keeps refusing to tell: on a
 * phone whose camera cannot record, the alert still goes out, and the person
 * should be able to see which half arrived.
 */
export interface SosResult {
  ok: boolean;
  contactsNotified: number;
  policeStationsFound: number;
  videoAttached: boolean;
  /** Why it failed. Only set when `ok` is false. */
  message?: string;
}

export interface SosController {
  cameraVisible: boolean;
  sending: boolean;
  progress: number;
  stage: SosStage;
  /**
   * Whether the send has been put in the corner.
   *
   * The upload is unaffected either way: it is an in-flight `XMLHttpRequest`
   * held by this hook, which lives in `GuardianProvider` at the app root, so it
   * neither knows nor cares what is on screen. Minimising hides a modal; it
   * does not pause, cancel or restart anything.
   */
  minimized: boolean;
  /** Put the send in the corner and give the app back. */
  minimize: () => void;
  /** Bring the full progress card back. */
  expand: () => void;
  /** The outcome sheet's contents, or null when there is nothing to show. */
  result: SosResult | null;
  /** Close the outcome sheet. */
  dismissResult: () => void;
  /**
   * Open the camera. Safe to call from a button, the shake listener, or the
   * hot-word listener.
   *
   * The trigger source is remembered until the send completes rather than passed
   * to `onVideoRecorded`, because the camera screen sits between the two and has
   * no business knowing or forwarding it.
   */
  start: (trigger?: SosTrigger) => void;
  cancel: () => void;
  /** `null` sends the SOS with location only — see the implementation. */
  onVideoRecorded: (uri: string | null) => Promise<void>;
  onCameraError: (message: string) => void;
}

// The shake threshold now lives in `features/guardian/guardianStore` as a
// user-calibrated setting. See the note where the listener used to be.

export function useSOS(): SosController {
  const { currentLocation, getCurrentLocation } = useLocationStore();

  const [cameraVisible, setCameraVisible] = useState(false);
  const [sending, setSending] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<SosStage>('uploading');
  const [result, setResult] = useState<SosResult | null>(null);
  const [minimized, setMinimized] = useState(false);

  // A ref, not state: it is read inside `onVideoRecorded`, which was created on
  // an earlier render, and the whole reason this file exists is that reading
  // changing values out of a stale closure is how SOS broke before (defect 14).
  const triggerRef = useRef<SosTrigger>('button');

  const start = useCallback((trigger: SosTrigger = 'button') => {
    triggerRef.current = trigger;
    setCameraVisible(true);
    // Ask for a fix now rather than discovering we have none after the recording.
    if (!currentLocation) {
      getCurrentLocation().catch(err => console.log('Bg location fetch failed:', err));
    }
  }, [currentLocation, getCurrentLocation]);

  /**
   * Send the SOS. `uri` is null when there is no video to send.
   *
   * **A failed recording must not kill the alert.** `/sos/trigger` has always
   * taken the video as optional (`video: Optional[UploadFile] = File(None)`),
   * and the SOS's actual job is to tell somebody where you are. The clip is
   * evidence — valuable, and not a prerequisite.
   *
   * This matters beyond defensiveness: on the Vivo V2344 (Unisoc ums9230) this
   * app was tested on, CameraX never delivers a single video frame to its
   * VideoCapture surface. Measured from logcat: the recording runs its full ten
   * seconds, audio is captured throughout, and `Recorder` logs "waiting for
   * video keyframe" 43 times a second for the entire duration at every quality
   * offered — LOWEST, SD and the 1080p default. Audio works; video never
   * arrives. Before this change, that meant the SOS did nothing at all on that
   * handset.
   */
  const onVideoRecorded = useCallback(async (uri: string | null) => {
    setCameraVisible(false);
    setSending(true);
    // Each send starts in the foreground. Inheriting `minimized` from the
    // last one would mean an SOS that reported itself only in a corner —
    // and the one before it was minimised by somebody who is no longer
    // necessarily holding the phone.
    setMinimized(false);

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
      // B8 / S18. Provenance, not a credential -- nothing is authorised on it.
      formData.append('voice_activated', String(triggerRef.current === 'hot-word'));

      if (uri) {
        const fileType = uri.split('.').pop() || 'mp4';
        // @ts-ignore - React Native's FormData takes this shape for a file
        formData.append('video', {
          uri,
          name: `sos_video.${fileType}`,
          type: `video/${fileType}`,
        });
      } else {
        console.warn('SOS: sending location only — no video was captured.');
      }

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
          // `event.total > 0`, not `event.lengthComputable`: React Native
          // hardcodes `lengthComputable: true` on upload progress
          // (`Libraries/Network/XMLHttpRequest.js:329`), so the flag says
          // nothing about whether `total` is usable.
          if (event.total > 0) {
            // Clamped. `loaded` and `total` are counted by different pieces of
            // the platform -- a counting sink on the request body against the
            // multipart body's own computed length -- and on a real Android
            // handset `loaded` ran past `total`, so the overlay read "192%
            // Completed" during a working SOS. A progress bar that can read
            // 192% is one nobody believes at 40% either.
            const realPercent = Math.min(
              100,
              Math.round((event.loaded / event.total) * 100),
            );
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

      setResult({
        ok: true,
        contactsNotified: data.contacts_notified ?? 0,
        policeStationsFound: data.police_stations_found ?? 0,
        videoAttached: Boolean(uri),
      });
    } catch (error: any) {
      console.error('SOS Error:', error);
      setResult({
        ok: false,
        contactsNotified: 0,
        policeStationsFound: 0,
        videoAttached: false,
        message: error.message || 'Could not send the alert. Please try again.',
      });
    } finally {
      setSending(false);
    }
  }, [getCurrentLocation]);

  const cancel = useCallback(() => setCameraVisible(false), []);

  const dismissResult = useCallback(() => setResult(null), []);

  const minimize = useCallback(() => setMinimized(true), []);
  const expand = useCallback(() => setMinimized(false), []);

  /**
   * The camera failed. Send the SOS anyway, with location only.
   *
   * This used to close the camera, show "Recording Error" and stop — so a
   * device that cannot record video could not raise an SOS at all. The alert is
   * the point; the video is a bonus. The user is told what was and was not sent,
   * because "SOS sent" when the video was dropped would be a quiet lie.
   */
  const onCameraError = useCallback(
    (message: string) => {
      setCameraVisible(false);
      Alert.alert(
        'Sending without video',
        `The camera could not record on this phone, so your location is being sent ` +
          `to your emergency contacts without a video.

${message}`,
      );
      void onVideoRecorded(null);
    },
    [onVideoRecorded],
  );

  // Shake-to-SOS used to live here, and that was the bug.
  //
  // `useSOS()` was called in HomeScreen, MapScreen and SOSHotWordsScreen, and the
  // app's root is a bottom-tab navigator that keeps visited screens mounted. So
  // after a user had looked at two tabs there were **two accelerometer
  // subscriptions and two shake handlers**, and one shake opened two camera
  // modals and sent two alerts.
  //
  // It is now a single subscription in `features/guardian/GuardianProvider`,
  // which is mounted exactly once at the app root and is also where the voice
  // guard lives — a shouted hot word has to work on whatever screen the person is
  // on, which is impossible from inside a screen component. The threshold moved
  // with it, into `guardianStore`, where the user can calibrate it against a live
  // reading instead of inheriting a constant that disagreed with its own comment
  // (3.5 in the comment, 6.0 in the code).

  return {
    cameraVisible,
    sending,
    progress,
    stage,
    minimized,
    minimize,
    expand,
    result,
    dismissResult,
    start,
    cancel,
    onVideoRecorded,
    onCameraError,
  };
}
