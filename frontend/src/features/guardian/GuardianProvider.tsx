/**
 * One SOS, one shake listener, one voice guard, for the whole app. B6a / B8.
 *
 * ## The bug this fixes
 *
 * `useSOS()` was being called in `HomeScreen`, `MapScreen` **and**
 * `SOSHotWordsScreen`. The app's root is a bottom-tab navigator, which keeps
 * visited screens mounted — so after a user had looked at Home and the Map there
 * were **two accelerometer subscriptions and two shake handlers**, and a single
 * shake opened two camera modals and sent two SOS alerts. Three, once the hot
 * words screen was visited.
 *
 * Nothing caught it because each screen is correct in isolation, and the
 * duplicate only exists once two tabs have been visited — which no test does and
 * a quick manual check does not either.
 *
 * ## Why automatic triggers force the fix rather than merely benefiting from it
 *
 * A shouted hot word has to work on whatever screen the person is on. So does a
 * shake. Neither can live inside a screen component, because the screen may not
 * be mounted — and if it is mounted several times over, the trigger fires
 * several times over. There is exactly one place in this app that is always
 * mounted exactly once, and this is it.
 *
 * So the accelerometer listener moved **out** of `useSOS` and into here, and the
 * controller is handed to screens through context. A screen that wants the red
 * button calls `useSosController()` and gets the same instance everybody else
 * has.
 *
 * ## What is not here
 *
 * Zone alerts. Those are registered with the operating system
 * (`features/geofence/`) and fire through a background task with the app closed,
 * so they need no component at all — which is the point of using the OS's
 * geofencing rather than a JS timer.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Modal, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Accelerometer } from 'expo-sensors';

import { SOSFlow } from '../sos/SOSFlow';
import { useSOS, type SosController, type SosTrigger } from '../sos/useSOS';
import { useGuardianStore } from './guardianStore';
import { useLiveMeters } from './liveMeters';
import { useVoiceGuard } from '../voice/useVoiceGuard';

/**
 * How long the cancel window is, in seconds.
 *
 * Five. Long enough to stop a false positive, short enough that it is not a
 * delay anybody would notice in a real emergency — and the camera starts
 * recording the moment it closes, so nothing is lost by waiting.
 */
const COUNTDOWN_SECONDS = 5;

/**
 * Minimum gap between two automatic triggers, in milliseconds.
 *
 * A shake is not one event: the accelerometer reports every sample above the
 * threshold, so one violent shake is a dozen crossings over about a second.
 * Without this, each of them would try to open the camera.
 *
 * It also guards the voice path, where a `continuous` recogniser emits interim
 * and final results for the same utterance.
 */
const TRIGGER_COOLDOWN_MS = 20_000;

const SosContext = createContext<SosController | null>(null);

/**
 * The shared SOS controller.
 *
 * Throws rather than returning null when used outside the provider. A silent
 * null here would mean a red button that does nothing — which is defect 14 all
 * over again, and it took a sprint to find the first time.
 */
export function useSosController(): SosController {
  const controller = useContext(SosContext);
  if (!controller) {
    throw new Error(
      'useSosController() outside <GuardianProvider>. SOS is mounted once, at the ' +
        'app root — see features/guardian/GuardianProvider.tsx.',
    );
  }
  return controller;
}

export const GuardianProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const sos = useSOS();
  const shakeEnabled = useGuardianStore(state => state.shakeEnabled);
  const shakeThresholdG = useGuardianStore(state => state.shakeThresholdG);
  const confirmCountdown = useGuardianStore(state => state.confirmCountdown);

  // Refs because the accelerometer handler and the voice callback are created
  // once and read these on every sample. State here would mean a stale
  // threshold for as long as the subscription lived.
  const lastTriggerRef = useRef(0);
  const sendingRef = useRef(false);
  const thresholdRef = useRef(shakeThresholdG);
  const confirmRef = useRef(confirmCountdown);
  const startRef = useRef(sos.start);
  const busyRef = useRef({ camera: sos.cameraVisible, sending: sos.sending });

  useEffect(() => {
    thresholdRef.current = shakeThresholdG;
    confirmRef.current = confirmCountdown;
    startRef.current = sos.start;
    busyRef.current = { camera: sos.cameraVisible, sending: sos.sending };
  }, [shakeThresholdG, confirmCountdown, sos.start, sos.cameraVisible, sos.sending]);

  /**
   * Fire an SOS from an automatic trigger.
   *
   * Shared by shake and voice so the cooldown, the busy check and the countdown
   * behave identically whichever set it off. `reason` is shown to the user —
   * being told *why* the phone is about to call for help is the difference
   * between a feature and a malfunction.
   */
  // `useCallback` with no dependencies, not a plain function in the render body.
  // Two reasons, and the second is a lint error rather than taste:
  //
  //  * everything mutable is read from a ref, so it genuinely has no deps -- the
  //    accelerometer subscription captures this once and must not be torn down
  //    and rebuilt on every render of the whole app;
  //  * React Compiler rejects calling `Date.now()` from the render body
  //    ("cannot call impure function during render"), because it cannot tell
  //    this is only ever reached from an event handler. Inside a callback it can.
  const triggerAutomatically = useCallback((trigger: SosTrigger, reason: string) => {
    const now = Date.now();
    const sinceLast = now - lastTriggerRef.current;
    if (sinceLast < TRIGGER_COOLDOWN_MS) {
      // Previously a bare `return`, which made the cooldown invisible: trigger
      // once, try again twenty seconds later, and in between every shake and
      // every shout did nothing at all with no feedback anywhere. It read
      // exactly like the feature being broken.
      const waitSeconds = Math.ceil((TRIGGER_COOLDOWN_MS - sinceLast) / 1000);
      console.log(
        `[guardian] ${trigger} ignored: ${waitSeconds}s of cooldown left (one SOS per ` +
          `${TRIGGER_COOLDOWN_MS / 1000}s).`,
      );
      useLiveMeters.getState().set({
        error: `Ignored — ${waitSeconds}s left of the ${TRIGGER_COOLDOWN_MS / 1000}s cooldown after the last trigger.`,
      });
      return;
    }
    if (busyRef.current.camera || busyRef.current.sending || sendingRef.current) {
      console.log(`[guardian] ${trigger} ignored: an SOS is already in flight.`);
      return;
    }
    lastTriggerRef.current = now;

    if (!confirmRef.current) {
      startRef.current(trigger);
      return;
    }

    // ONE dialog, driven by a ref the countdown reads -- not one per second.
    //
    // The previous version called `Alert.alert` every second with a new title,
    // on the belief that Android replaces the dialog. **It does not: it stacks
    // them.** Five seconds of countdown left five dialogs piled on the screen,
    // each with its own live "Send now" handler, and dismissing the top one left
    // four behind.
    sendingRef.current = true;
    setCountdown({ trigger, reason, remaining: COUNTDOWN_SECONDS });
  }, []);

  /**
   * The countdown, rendered once by this provider.
   *
   * In provider state rather than an `Alert` because it has to be a single
   * element that updates, and because it must render above whatever screen is
   * showing -- which a provider wrapping the navigator does by definition.
   */
  const [countdown, setCountdown] = useState<{
    trigger: SosTrigger;
    reason: string;
    remaining: number;
  } | null>(null);

  useEffect(() => {
    if (!countdown) return;
    if (countdown.remaining <= 0) {
      setCountdown(null);
      sendingRef.current = false;
      startRef.current(countdown.trigger);
      return;
    }
    const timer = setTimeout(
      () => setCountdown(current => (current ? { ...current, remaining: current.remaining - 1 } : null)),
      1000,
    );
    return () => clearTimeout(timer);
  }, [countdown]);

  const cancelCountdown = () => {
    setCountdown(null);
    sendingRef.current = false;
    // The cooldown is not reset on cancel. A cancelled trigger still means
    // something set it off, and re-triggering a second later would be the same
    // false positive again.
  };

  const sendNow = () => {
    const pending = countdown;
    setCountdown(null);
    sendingRef.current = false;
    if (pending) startRef.current(pending.trigger);
  };


  // -----------------------------------------------------------------------
  // Shake
  // -----------------------------------------------------------------------
  //
  // The single subscription. It was inside `useSOS`, which meant one per screen
  // that used SOS — see the module docstring.
  useEffect(() => {
    if (!shakeEnabled) return;

    Accelerometer.setUpdateInterval(200);
    const subscription = Accelerometer.addListener(({ x, y, z }) => {
      const magnitude = Math.sqrt(x * x + y * y + z * z);
      if (magnitude < thresholdRef.current) return;
      triggerAutomatically('shake', `The phone was shaken hard (${magnitude.toFixed(1)}g).`);
    });

    return () => subscription?.remove();
    // `triggerAutomatically` is recreated every render and reads everything
    // mutable from refs, so it is deliberately not a dependency — listing it
    // would tear down and rebuild the accelerometer subscription on every
    // render of the whole app.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shakeEnabled]);

  // -----------------------------------------------------------------------
  // Voice
  // -----------------------------------------------------------------------
  //
  // Owns the recogniser session and the shout gate; see `useVoiceGuard`. Mounted
  // here for the same reason as the accelerometer: a shouted hot word has to
  // work on whatever screen the person is on, and must fire once.
  useVoiceGuard({
    onTrigger: (phrase, loudness) =>
      triggerAutomatically(
        'hot-word',
        `You shouted "${phrase}" (loudness ${loudness.toFixed(1)}).`,
      ),
    // Deaf while an SOS is in flight, listening again once it is done. The
    // countdown and the camera both own the microphone; the guard waits rather
    // than fighting them for it, then resumes. See `VoiceGuardOptions.paused`.
    paused: Boolean(countdown) || sos.cameraVisible || sos.sending,
  });

  return (
    <SosContext.Provider value={sos}>
      {children}
      {/* The camera and progress modals, mounted once. Any trigger from
          anywhere in the app renders here. */}
      <SOSFlow sos={sos} />

      {/* The cancel window. One element that counts down, rendered above
          whatever screen is showing -- this provider wraps the navigator, so
          "above everything" is structural rather than a z-index fight. */}
      <Modal transparent visible={Boolean(countdown)} animationType="fade">
        <View style={styles.backdrop}>
          <View style={styles.card}>
            <Text style={styles.count}>{countdown?.remaining ?? 0}</Text>
            <Text style={styles.title}>Sending SOS</Text>
            <Text style={styles.reason}>{countdown?.reason}</Text>
            <Text style={styles.detail}>
              Your location and a short video will go to your emergency contacts.
            </Text>
            <View style={styles.actions}>
              <TouchableOpacity style={styles.cancel} onPress={cancelCountdown}>
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.send} onPress={sendNow}>
                <Text style={styles.sendText}>Send now</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SosContext.Provider>
  );
};

export default GuardianProvider;

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
  },
  // Large, because this is read at a glance by somebody who may be in trouble
  // and is the one number that matters: how long they have to stop it.
  count: { fontSize: 56, fontWeight: '800', color: '#E53935', lineHeight: 62 },
  title: { fontSize: 20, fontWeight: '700', color: '#111827', marginTop: 4 },
  reason: {
    fontSize: 14,
    color: '#374151',
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 20,
  },
  detail: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 17,
  },
  actions: { flexDirection: 'row', gap: 12, marginTop: 20, alignSelf: 'stretch' },
  cancel: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#D1D5DB',
    alignItems: 'center',
  },
  cancelText: { fontSize: 16, fontWeight: '600', color: '#374151' },
  send: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#E53935',
    alignItems: 'center',
  },
  sendText: { fontSize: 16, fontWeight: '700', color: '#FFFFFF' },
});
