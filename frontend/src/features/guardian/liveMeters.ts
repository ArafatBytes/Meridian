/**
 * Live readings from the guard, for the screen to draw. B8.
 *
 * A separate store from `guardianStore`, and the split is deliberate.
 *
 * `guardianStore` holds **settings** — they change when the user touches a
 * control, a few times a day, and they are persisted. This holds **telemetry**:
 * loudness arrives about seven times a second while listening. Putting the two
 * in one store would mean every component subscribed to the shake threshold
 * re-rendering on every audio sample, and would write a stream of volume
 * readings through AsyncStorage.
 *
 * ## Why a store rather than context or a return value
 *
 * `useVoiceGuard` runs **once**, inside `GuardianProvider`, because a second
 * instance would open a second recogniser session on the same microphone. So the
 * Guardian screen cannot call it to get a meter reading — it has to observe the
 * one that is already running. A store is the cheapest way for a writer that is
 * mounted once to be read by a screen that comes and goes, without the provider
 * knowing anything about the screen.
 *
 * Nothing here is persisted: these are facts about this second.
 */

import { create } from 'zustand';

export interface LiveMeters {
  /** Whether the recogniser is actually running. */
  listening: boolean;
  /** Current loudness, −2…10 (Android RMS). Not decibels. */
  loudness: number;
  /** Peak loudness inside the shout window — the value the gate compares. */
  peakLoudness: number;
  /** Last transcript seen. On screen only; never uploaded. */
  heard: string;
  /** A transient problem, e.g. heard the phrase but not loudly enough. */
  error: string | null;
  /** Why the guard cannot listen at all, when it cannot. */
  unavailable: string | null;

  set: (patch: Partial<Omit<LiveMeters, 'set' | 'reset'>>) => void;
  reset: () => void;
}

const IDLE = {
  listening: false,
  loudness: -2,
  peakLoudness: -2,
  heard: '',
  error: null,
  unavailable: null,
} as const;

export const useLiveMeters = create<LiveMeters>()(set => ({
  ...IDLE,
  set: patch => set(patch),
  reset: () => set({ ...IDLE }),
}));
