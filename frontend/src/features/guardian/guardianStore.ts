/**
 * The three automatic protections, and their settings. B6a / B8.
 *
 *   zone alerts   background GPS → a notification when you approach a flagged road
 *   voice SOS     a shouted hot word → SOS, automatically
 *   shake SOS     shaking the phone hard → SOS, automatically
 *
 * One store, because they are one feature from the user's side — "watch out for
 * me" — and because every one of them has a threshold that only means anything
 * once it has been calibrated on a real phone. Those thresholds are the whole
 * reason this is persisted: a number the user tuned once and lost on the next
 * launch is worse than a number they cannot change.
 *
 * ## Why thresholds are settings and not constants
 *
 * Both the shout gate and the shake gate are **device-dependent**, and not
 * slightly:
 *
 * * Loudness arrives as Android's RMS value on a **−2 to 10** scale, not as
 *   decibels. What counts as a shout depends on the microphone, the case over
 *   it, and how the person holds the phone. There is no universally correct
 *   number, so the screen shows a live meter and lets them set it from what they
 *   actually see.
 * * Shake magnitude is in g, and the inherited code disagreed with its own
 *   comment — 3.5 in the comment, 6.0 in the code (**defect: the shake
 *   threshold**, which `IMPLEMENTATION_PLAN.md` logs for B5 and asks to be
 *   settled "with a measurement"). A slider plus a live reading is the
 *   measurement, taken by the person whose phone it is.
 *
 * Shipping one constant for every handset is how a panic trigger ends up either
 * firing in a pocket or not firing when someone is being attacked.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

/**
 * Default shout gate, on the recogniser's −2…10 scale.
 *
 * 6.0 is well above conversational speech (roughly 1–4 on the devices this was
 * read on) and reachable by a raised voice without screaming. It is a starting
 * point for the meter, not a measurement — the screen exists because this number
 * is wrong on some phone.
 */
export const DEFAULT_SHOUT_THRESHOLD = 6.0;

/**
 * Default shake gate, in g.
 *
 * 6.0 g, which is what the inherited code actually used — chosen over the 3.5 in
 * its comment because 6.0 is the value that has been run on a device, and
 * because 3.5 g is reachable by putting a phone down firmly. A deliberate SOS
 * shake is violent; a pocket is not.
 */
export const DEFAULT_SHAKE_THRESHOLD_G = 6.0;

/** Bounds for the sliders. Outside these the trigger is useless in one direction. */
export const SHOUT_RANGE = { min: 2, max: 9.5 } as const;
export const SHAKE_RANGE = { min: 2.5, max: 12 } as const;

export interface GuardianState {
  /** Background GPS → zone notifications. Survives the app being closed. */
  zoneAlertsEnabled: boolean;
  /** Listening for a shouted hot word. Only while the app is open — see `voice/`. */
  voiceArmed: boolean;
  /** Shake-to-SOS. Only while the app is open; the accelerometer needs a live JS context. */
  shakeEnabled: boolean;

  shoutThreshold: number;
  shakeThresholdG: number;

  /**
   * Whether a triggered SOS gives a countdown before sending.
   *
   * On by default, and the default is the argued one. The brief asks for SOS to
   * fire *automatically*, and it does — this does not require a tap, it is a
   * five-second window in which the person can stop it. An automatic trigger
   * with no way to cancel means every false positive emails somebody's family to
   * say they are in danger, and both triggers here are heuristics: a recogniser
   * mishearing a word, a phone dropped on a hard floor.
   *
   * Turning it off makes the send instant, which is the right choice for someone
   * who has tested their own thresholds and trusts them.
   */
  confirmCountdown: boolean;

  setZoneAlertsEnabled: (value: boolean) => void;
  setVoiceArmed: (value: boolean) => void;
  setShakeEnabled: (value: boolean) => void;
  setShoutThreshold: (value: number) => void;
  setShakeThresholdG: (value: number) => void;
  setConfirmCountdown: (value: boolean) => void;
}

export const useGuardianStore = create<GuardianState>()(
  persist(
    set => ({
      // All three default OFF. Each one costs battery, two of them hold the
      // microphone or the accelerometer open, and all three can wake somebody's
      // phone — none of that is a thing to switch on for a user who has not
      // asked. Zone alerts additionally require a permission Android only grants
      // from its own settings screen, so defaulting them on would show a feature
      // that was always in a broken state.
      zoneAlertsEnabled: false,
      voiceArmed: false,
      shakeEnabled: false,

      shoutThreshold: DEFAULT_SHOUT_THRESHOLD,
      shakeThresholdG: DEFAULT_SHAKE_THRESHOLD_G,
      confirmCountdown: true,

      setZoneAlertsEnabled: zoneAlertsEnabled => set({ zoneAlertsEnabled }),
      setVoiceArmed: voiceArmed => set({ voiceArmed }),
      setShakeEnabled: shakeEnabled => set({ shakeEnabled }),
      setShoutThreshold: shoutThreshold => set({ shoutThreshold }),
      setShakeThresholdG: shakeThresholdG => set({ shakeThresholdG }),
      setConfirmCountdown: confirmCountdown => set({ confirmCountdown }),
    }),
    {
      name: 'meridian.guardian.v1',
      storage: createJSONStorage(() => AsyncStorage),
      /**
       * `voiceArmed` is deliberately **not** persisted.
       *
       * It holds the microphone open. Restoring it on launch would mean an app
       * that starts listening because of something the user did days ago, with
       * no moment where they chose it — which is the opposite of what an "armed"
       * control means. The two thresholds and the other switches persist;
       * listening is always an explicit act.
       */
      partialize: state => ({
        zoneAlertsEnabled: state.zoneAlertsEnabled,
        shakeEnabled: state.shakeEnabled,
        shoutThreshold: state.shoutThreshold,
        shakeThresholdG: state.shakeThresholdG,
        confirmCountdown: state.confirmCountdown,
      }),
    },
  ),
);
