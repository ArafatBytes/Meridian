/**
 * When the place search is allowed to ask the geocoder.
 *
 * The suggestion list under the route box is driven by the *contents* of the
 * two fields — and the code writes to those fields as often as the person does.
 * A tap on open ground puts `Selected Location` in the destination, a tap on a
 * labelled place puts that place's name there, and Resume puts the stored
 * destination label there. Each of those already knows its own coordinate.
 *
 * Treating them as searches is how a tap on a side street in Dhaka produced a
 * suggestion reading *"A location selected by Seoul for its scenic views,
 * Jeungsan-ro 17-gil, Eunpyeong-gu, Seoul, South Korea"*. Nothing was wrong with
 * the geocode: Nominatim was handed the words "Selected Location" and found the
 * closest thing in the world to them. The fault was asking.
 *
 * So the rule is about provenance, not about the text. Blocking the particular
 * string `Selected Location` would have hidden this one and left the POI tap
 * (searching "Star Kabab" and offering a different Star Kabab) and Resume
 * (searching a whole stored address) intact.
 */

/** Which field the suggestions belong to, or none. */
export type ActiveSearch = 'source' | 'destination' | null;

/**
 * Shortest text worth sending. Two characters match half of Dhaka, and the
 * answer arrives after the third keystroke has already made it wrong.
 */
export const MIN_QUERY_LENGTH = 3;

/**
 * `My Location` is the source field's own word for "wherever I am", filled in by
 * the app and resolved from the GPS, never from the geocoder.
 */
export const NOT_A_PLACE = 'My Location';

/**
 * Does this field name a place it has not actually chosen?
 *
 * The start field holds two things that look identical on screen and mean
 * opposite things: text a person typed, and a place they picked from the list.
 * Only the second carries a coordinate. `null` is the start field's way of
 * saying *"use the GPS"*, which is correct while the field reads `My Location`
 * and a lie the moment someone types over it.
 *
 * That lie had a cost. `calculateRouteTo` fell back to `currentLocation`
 * whenever no coordinate was bound, so typing `Gulshan 2` and then picking a
 * destination routed from **wherever the phone actually was**, drew it, scored
 * it, and showed `Gulshan 2` in the box throughout. Nothing failed; the answer
 * was simply to a different question. On a demo it reads as the router being
 * broken, and in use it is worse than an error, because an error can be seen.
 *
 * So the fallback is now conditional on this predicate rather than on the
 * coordinate alone: no coordinate *and* no typed text means the GPS, and no
 * coordinate *with* typed text means nothing has been chosen yet.
 */
export function isUnboundPlace(args: {
  query: string;
  location: unknown | null;
}): boolean {
  if (args.location) return false;
  const trimmed = args.query.trim();
  return trimmed.length > 0 && trimmed !== NOT_A_PLACE;
}

export function shouldSuggest(args: {
  /** True only if the last change to this field came from a keystroke. */
  typed: boolean;
  active: ActiveSearch;
  query: string;
}): boolean {
  const { typed, active, query } = args;
  if (!typed || !active) return false;
  const trimmed = query.trim();
  return trimmed.length >= MIN_QUERY_LENGTH && trimmed !== NOT_A_PLACE;
}
