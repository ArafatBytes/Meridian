/**
 * Hot-word matching. B8 / S18.
 *
 * This matcher decides whether to fire an SOS, which emails somebody's emergency
 * contacts. Both directions of error are real: a missed phrase means the feature
 * does not work, and a false match means a stranger is told a person is in danger
 * when they are not. So both directions are tested, and the false-positive cases
 * are the longer list.
 */

import {
  MAX_PHRASE_LENGTH,
  MIN_PHRASE_LENGTH,
  hotWordProblem,
  matchHotWord,
  normalise,
  phraseWasSaid,
} from './hotwords';

describe('normalise', () => {
  it('lowercases, strips punctuation and collapses whitespace', () => {
    expect(normalise('  Help   ME, now!  ')).toBe('help me now');
  });

  it('strips the Bengali danda', () => {
    // `।` is what a Bangla recogniser emits as a full stop, and no user types it
    // into a hot-word field. Left in, it would make every Bangla phrase fail.
    expect(normalise('আমাকে বাঁচাও।')).toBe('আমাকে বাঁচাও');
  });

  it('collapses the non-breaking space some engines emit', () => {
    expect(normalise('help me')).toBe('help me');
  });

  it('is idempotent', () => {
    expect(normalise(normalise('Help me!'))).toBe(normalise('Help me!'));
  });
});

describe('phraseWasSaid — it fires when it should', () => {
  it.each([
    ['help me', 'help me'],
    ['Help me', 'help me'],
    ['HELP ME', 'help me'],
    ['Help me!', 'help me'],
    ['Please help me right now', 'help me'],
    ['help  me', 'help me'],
    ['Somebody, help me.', 'Help Me'],
  ])('matches %p against %p', (transcript, phrase) => {
    expect(phraseWasSaid(transcript, phrase)).toBe(true);
  });

  it('matches the phrase at the start, middle and end of a transcript', () => {
    expect(phraseWasSaid('help me please stop', 'help me')).toBe(true);
    expect(phraseWasSaid('oh god help me please', 'help me')).toBe(true);
    expect(phraseWasSaid('please someone help me', 'help me')).toBe(true);
  });
});

describe('phraseWasSaid — it does NOT fire when it should not', () => {
  /**
   * The case a substring match gets wrong, and the reason the Latin path is
   * token-based.
   *
   * A user who stores `help` would otherwise be triggered by "helpful",
   * "helper", "helping" — all ordinary words, all of which would send an alert
   * to their emergency contacts.
   */
  it.each([
    ['that was helpful', 'help'],
    ['he is a helper', 'help'],
    ['helping out today', 'help'],
    ['I am unhelpful', 'help'],
  ])('does not match %p against %p', (transcript, phrase) => {
    expect(phraseWasSaid(transcript, phrase)).toBe(false);
  });

  it('requires the words in order and adjacent', () => {
    expect(phraseWasSaid('me help', 'help me')).toBe(false);
    expect(phraseWasSaid('help somebody me', 'help me')).toBe(false);
  });

  it('does not match an empty transcript or an empty phrase', () => {
    expect(phraseWasSaid('', 'help me')).toBe(false);
    expect(phraseWasSaid('help me', '')).toBe(false);
    expect(phraseWasSaid('   ', 'help me')).toBe(false);
    expect(phraseWasSaid('help me', '   ')).toBe(false);
  });

  it('does not match a phrase longer than the transcript', () => {
    expect(phraseWasSaid('help', 'help me now please')).toBe(false);
  });
});

describe('phraseWasSaid — Bangla', () => {
  /**
   * Bengali has no case and takes agglutinative suffixes, so the script is
   * matched as a substring rather than on word boundaries — the same split, for
   * the same reason, as `app/policy/framing.py`'s banned-term matching.
   *
   * A token-boundary match would miss the inflected and compounded forms that
   * actually appear in transcripts.
   */
  it('matches a Bangla phrase', () => {
    expect(phraseWasSaid('আমাকে বাঁচাও', 'বাঁচাও')).toBe(true);
    expect(phraseWasSaid('কেউ আমাকে বাঁচাও।', 'আমাকে বাঁচাও')).toBe(true);
  });

  it('matches a Bangla phrase inside a compound, which Latin matching would not', () => {
    expect(phraseWasSaid('বাঁচাওবাঁচাও', 'বাঁচাও')).toBe(true);
  });

  it('still does not match a Bangla phrase that was not said', () => {
    expect(phraseWasSaid('আমি ভালো আছি', 'বাঁচাও')).toBe(false);
  });
});

describe('matchHotWord', () => {
  it('returns null when nothing matches', () => {
    expect(matchHotWord('the weather is fine', ['help me', 'বাঁচাও'])).toBeNull();
  });

  it('returns the phrase exactly as the user stored it', () => {
    // Not the normalised form: the screen shows this back to them, and
    // "Triggered by: help me" when they typed "Help Me" reads as a different app.
    expect(matchHotWord('somebody help me', ['Help Me'])).toBe('Help Me');
  });

  /**
   * Longest first, so the more specific phrase is the one attributed.
   *
   * The trigger is identical either way — an SOS fires. What differs is what the
   * user is told set it off, and "help me now" is more informative than "help".
   */
  it('attributes the most specific matching phrase', () => {
    expect(matchHotWord('please help me now', ['help', 'help me now'])).toBe('help me now');
    expect(matchHotWord('please help me now', ['help me now', 'help'])).toBe('help me now');
  });

  it('handles an empty phrase list', () => {
    expect(matchHotWord('help me', [])).toBeNull();
  });
});

describe('hotWordProblem', () => {
  it('accepts a sensible phrase', () => {
    expect(hotWordProblem('help me')).toBeNull();
    expect(hotWordProblem('বাঁচাও')).toBeNull();
  });

  it('rejects an empty phrase', () => {
    expect(hotWordProblem('   ')).toMatch(/Enter a word/);
  });

  /**
   * Short phrases are refused, and the message says why rather than just "too
   * short".
   *
   * At three characters a recogniser's ordinary mis-hearings start matching:
   * "bus", "box" and "bas" are one phoneme apart and all plausible on a Dhaka
   * street. A three-letter trigger fires on traffic.
   */
  it('rejects a phrase too short to be safe', () => {
    const problem = hotWordProblem('sos');
    expect(problem).toMatch(new RegExp(String(MIN_PHRASE_LENGTH)));
    expect(problem).toMatch(/noise/);
  });

  it('accepts a phrase exactly at the minimum', () => {
    expect(hotWordProblem('help')).toBeNull();
  });

  it('rejects a whole sentence', () => {
    const problem = hotWordProblem('x'.repeat(MAX_PHRASE_LENGTH + 1));
    expect(problem).toMatch(/Too long/);
  });

  it('rejects a duplicate, ignoring case and punctuation', () => {
    expect(hotWordProblem('Help me!', ['help me'])).toMatch(/already have/);
  });

  /**
   * A phrase containing an existing phrase can never fire, and saying so is
   * worth a branch of its own.
   *
   * The user's mental model is that adding phrases adds coverage. It does not:
   * with `help` stored, adding `help me now` creates an entry that is
   * unreachable, because `help` matches first and triggers. Storing it silently
   * would leave them believing they had configured something they had not.
   */
  it('rejects a phrase that an existing one would shadow', () => {
    const problem = hotWordProblem('help me now', ['help']);
    expect(problem).toMatch(/"help"/);
    expect(problem).toMatch(/never be used/);
  });

  it('allows a phrase that merely shares a word with an existing one', () => {
    expect(hotWordProblem('help me', ['save me'])).toBeNull();
  });
});
