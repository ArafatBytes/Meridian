/**
 * The people a journey could be told to. JG3.
 *
 * The emergency contacts, read once, filtered for the one thing JG3 needs from
 * them — an email address — and offered to the route card with **Nobody** first.
 *
 * ## Why an email address is the whole requirement
 *
 * JG3 sends email and nothing else. No SMS, no push to a guardian, no
 * guardian-side app — `JG3_PLAN.md` §6. So a contact without an email cannot be
 * a guardian, and the server says so with a 422 rather than accepting the
 * journey and silently telling nobody. This hook keeps those contacts in the
 * list but marks them unusable: hiding them would make a contact somebody
 * deliberately added look like it had never been saved, and that is a worse
 * mystery than a greyed-out row with a reason on it.
 *
 * ## Why Supabase directly
 *
 * Same as `EmergencyContactsScreen`, which is the screen that writes them.
 * `emergency_contacts` has RLS with the owner policy, so this reads the
 * caller's own rows and nothing else — unlike `journeys`, which has RLS with no
 * policies at all and is the reason the journey calls go through the backend.
 * Adding an endpoint to re-expose a table the app already reads would be a
 * second definition of the same list.
 */
import { useCallback, useEffect, useState } from 'react';

import { supabase } from '../../lib/supabase';
import { useAuthStore } from '../../store';

export interface GuardianOption {
  id: string;
  name: string;
  /** Null when the contact has no email, which is what makes it unusable. */
  email: string | null;
  /** False when Meridian has no way to reach them. */
  usable: boolean;
}

export interface UseGuardians {
  options: GuardianOption[];
  loading: boolean;
  /** Re-read, for when somebody adds a contact and comes back. */
  reload: () => Promise<void>;
}

/** Trimmed, or null. An empty string in the column is the same as no address. */
function address(email: unknown): string | null {
  if (typeof email !== 'string') return null;
  const trimmed = email.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function toOptions(
  rows: { id: string; name: string | null; email: string | null }[],
): GuardianOption[] {
  return rows.map(row => {
    const email = address(row.email);
    return {
      id: row.id,
      // A contact saved with no name still has to be pickable, and "Contact"
      // beats an empty row that cannot be told apart from its neighbour.
      name: row.name?.trim() || 'Contact',
      email,
      usable: email !== null,
    };
  });
}

/**
 * Read the caller's contacts, or an empty list.
 *
 * A module-level function rather than a closure in the hook, so the effect
 * below can await it before touching state: a `setState` reached synchronously
 * from an effect body is a cascading render, and the same reason shaped
 * `useJourney`'s launch read. Returning a value rather than setting state also
 * means the no-user case is one `return []` instead of a second write path.
 */
async function read(userId: string | null): Promise<GuardianOption[]> {
  if (!userId) return [];
  try {
    const { data, error } = await supabase
      .from('emergency_contacts')
      .select('id, name, email')
      .eq('user_id', userId)
      // Oldest first, unlike the contacts screen. This is a list somebody picks
      // from rather than a feed of what they just added, and a list whose rows
      // move as contacts are added is one where muscle memory picks the wrong
      // person.
      .order('created_at', { ascending: true });

    if (error) throw error;
    return toOptions(data ?? []);
  } catch (e: any) {
    // Not surfaced. The picker's absence degrades to "Nobody", which is the
    // default and a working journey -- JG2's behaviour exactly. A dialog here
    // would interrupt someone planning a route to tell them about a list they
    // had not asked to see.
    console.warn('Could not load contacts for the guardian picker:', e?.message);
    return [];
  }
}

export function useGuardians(): UseGuardians {
  const { user } = useAuthStore();
  const userId = user?.id ?? null;
  const [options, setOptions] = useState<GuardianOption[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const loaded = await read(userId);
      if (cancelled) return;
      setOptions(loaded);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const reload = useCallback(async () => {
    setOptions(await read(userId));
  }, [userId]);

  return { options, loading, reload };
}
