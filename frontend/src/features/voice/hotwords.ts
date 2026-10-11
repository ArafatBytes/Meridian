/**
 * Matching a spoken phrase against a user's SOS hot words. B8 / S18.
 *
 * Pure: no recogniser, no permissions, no native modules. Given a transcript and
 * a list of phrases, it answers whether one of them was said. That is the whole
 * of this file, and keeping it separate from `useHotWordListener` is what makes
 * the matching testable — the hook needs a microphone and a physical device, and
 * the matching is where the bugs are.
 *
 * ## Why this is not `transcript.includes(phrase)`
 *
 * Four reasons, each of which produced a wrong answer in practice:
 *
 * **Case and spacing.** A recogniser returns `"Help me"`, `"help me"`, or
 * `"help  me"` depending on the engine, the locale and whether punctuation is
 * on. All three are the same utterance.
 *
 * **Punctuation.** With `addsPunctuation` the transcript is `"Help me!"`, and a
 * naive `includes("help me")` works by luck — until the phrase is the whole
 * utterance and the engine appends a full stop, giving `"Help me."` against a
 * stored `"help me"`, which still works, and then someone stores `"help me."`
 * and it stops working for everyone.
 *
 * **Word boundaries.** A substring match on a short phrase is dangerous in the
 * other direction: a user who stores `"help"` would be triggered by
 * `"helpful"`, `"helper"`, `"helping out"`. For an SOS that fires an alert to
 * emergency contacts, a false positive is not a cosmetic bug.
 *
 * **Bangla.** Bengali has no case and takes agglutinative suffixes, so
 * `বাঁচাও` appears as `বাঁচাওo`-style inflections and compounds in real
 * transcripts. A word-boundary match on the Latin model would miss them, so
 * Bangla is matched as a substring — the same split, for the same reason, as
 * `app/policy/framing.py`'s banned-term matching, which learned it first.
 *
 * ## The false-positive bias
 *
 * This matcher is deliberately **strict**. `MIN_PHRASE_LENGTH` rejects phrases
 * too short to be safe, and the Latin path requires whole words. An SOS triggers
 * a real alert to real people; the cost of a missed hot word is that the user
 * presses the button, which they can do, and the cost of a false one is a
 * stranger being told somebody is in danger when they are not.
 */

/**
 * The shortest hot word worth accepting, in characters.
 *
 * Four, because at three a recogniser's ordinary mis-hearings start matching.
 * "Bus", "box" and "bas" are one phoneme apart and all plausible in a Dhaka
 * street; a three-letter trigger would fire on traffic noise. The screen refuses
 * anything shorter and says why rather than storing a phrase that will either
 * never fire or always fire.
 */
export const MIN_PHRASE_LENGTH = 4;

/**
 * The longest. Longer than this is a sentence, and a sentence will never be
 * recognised identically twice.
 */
export const MAX_PHRASE_LENGTH = 60;

/**
 * Characters stripped before comparison.
 *
 * Punctuation and the Bengali danda (`।`), which is what a Bangla recogniser
 * emits as a full stop and which no user types into a hot-word field.
 */
const PUNCTUATION = /[.,!?;:'"“”‘’()[\]{}…।\-_/\\]/g;

/** Any run of whitespace, including the non-breaking space some engines emit. */
const WHITESPACE = /[\s ]+/g;

/**
 * Normalise a transcript or a phrase to a comparable form.
 *
 * Lowercased, punctuation removed, whitespace collapsed, trimmed. Applied to
 * **both** sides of every comparison — normalising only the transcript is a bug
 * that hides until somebody stores a phrase with a capital letter in it.
 */
export function normalise(text: string): string {
  return text
    .toLowerCase()
    .replace(PUNCTUATION, ' ')
    .replace(WHITESPACE, ' ')
    .trim();
}

/** Whether a string contains any character outside the ASCII range. */
const hasNonAscii = (text: string): boolean => /[^\u0000-\u007F]/.test(text);

/**
 * Whether `phrase` occurs in `transcript` as whole words.
 *
 * Both are already normalised, so this is a token-sequence search rather than a
 * regex: building a `RegExp` from user input would need escaping, and an escaped
 * `\b` does not behave usefully around non-Latin characters anyway.
 */
function containsWholeWords(transcript: string, phrase: string): boolean {
  const haystack = transcript.split(' ');
  const needle = phrase.split(' ');
  if (needle.length === 0 || needle.length > haystack.length) return false;

  for (let start = 0; start <= haystack.length - needle.length; start += 1) {
    let matched = true;
    for (let offset = 0; offset < needle.length; offset += 1) {
      if (haystack[start + offset] !== needle[offset]) {
        matched = false;
        break;
      }
    }
    if (matched) return true;
  }
  return false;
}

/**
 * Whether this phrase was said in this transcript.
 *
 * Latin phrases match on whole words; phrases containing non-ASCII characters
 * match as substrings. See the module docstring for why the two scripts are
 * treated differently — it is the same reasoning `framing.py` uses.
 */
export function phraseWasSaid(transcript: string, phrase: string): boolean {
  const spoken = normalise(transcript);
  const target = normalise(phrase);
  if (!spoken || !target) return false;

  return hasNonAscii(target)
    ? spoken.includes(target)
    : containsWholeWords(spoken, target);
}

/**
 * The first stored phrase that was said, or null.
 *
 * Returns the **phrase as the user stored it**, not the normalised form, because
 * the caller shows it back to them — "Triggered by: Help me" has to read the way
 * they typed it.
 *
 * Longest first, so that a user with both `"help"` and `"help me now"` sees the
 * more specific one attributed. The trigger is the same either way; the
 * attribution is what they will remember.
 */
export function matchHotWord(transcript: string, phrases: readonly string[]): string | null {
  const ordered = [...phrases].sort((a, b) => normalise(b).length - normalise(a).length);
  for (const phrase of ordered) {
    if (phraseWasSaid(transcript, phrase)) return phrase;
  }
  return null;
}

/** Why a phrase cannot be used as a hot word, or null if it can. */
export function hotWordProblem(phrase: string, existing: readonly string[] = []): string | null {
  const normalised = normalise(phrase);

  if (!normalised) {
    return 'Enter a word or phrase.';
  }
  if (normalised.length < MIN_PHRASE_LENGTH) {
    return `Too short — use at least ${MIN_PHRASE_LENGTH} characters. Very short phrases are set off by ordinary speech and background noise.`;
  }
  if (normalised.length > MAX_PHRASE_LENGTH) {
    return `Too long — keep it under ${MAX_PHRASE_LENGTH} characters. A whole sentence is never recognised the same way twice.`;
  }
  if (existing.some(other => normalise(other) === normalised)) {
    return 'You already have this phrase.';
  }
  // A phrase that is a *superset* of an existing one can never fire: the shorter
  // one matches first and triggers, so this one is unreachable. Worth saying,
  // because the user's mental model is that adding more phrases adds coverage.
  const shadowing = existing.find(
    other => normalise(other) && phraseWasSaid(normalised, other),
  );
  if (shadowing) {
    return `"${shadowing}" is already in this phrase, so it would trigger first. This one would never be used.`;
  }
  return null;
}
