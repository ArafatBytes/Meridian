import {
  MIN_QUERY_LENGTH,
  NOT_A_PLACE,
  isUnboundPlace,
  shouldSuggest,
} from './suggest';

const typed = (query: string) =>
  shouldSuggest({ typed: true, active: 'destination', query });

const written = (query: string) =>
  shouldSuggest({ typed: false, active: 'destination', query });

describe('shouldSuggest', () => {
  it('asks the geocoder about text a person typed', () => {
    expect(typed('dhanmondi')).toBe(true);
  });

  it('never asks about text the code put in the field', () => {
    // The regression. A tap on open ground writes this label, and asking the
    // geocoder for it returned a viewpoint in Eunpyeong-gu, Seoul.
    expect(written('Selected Location')).toBe(false);
  });

  it('never asks about a place name that came from a map tap', () => {
    // A POI tap already carries the coordinate. Searching the name offers a
    // different branch of the same restaurant, somewhere else in the city.
    expect(written('Star Kabab')).toBe(false);
  });

  it('never asks about a destination label restored by Resume', () => {
    expect(written('National Museum of Science and Technology')).toBe(false);
  });

  it('is about where the text came from, not what it says', () => {
    // Somebody may genuinely want to search for these words. Typing them is a
    // question; having them written into the field is not.
    expect(typed('Selected Location')).toBe(true);
  });

  it('stays quiet when no field is active', () => {
    expect(shouldSuggest({ typed: true, active: null, query: 'dhanmondi' })).toBe(false);
  });

  it('waits for enough letters to be worth asking about', () => {
    expect(typed('dh')).toBe(false);
    expect(typed('dha')).toBe(true);
    expect('dha'.length).toBe(MIN_QUERY_LENGTH);
  });

  it('ignores whitespace on both counts', () => {
    expect(typed('   ')).toBe(false);
    expect(typed(`  ${NOT_A_PLACE}  `)).toBe(false);
  });

  it('does not geocode the source field’s word for the GPS', () => {
    expect(shouldSuggest({ typed: true, active: 'source', query: NOT_A_PLACE })).toBe(false);
    expect(shouldSuggest({ typed: true, active: 'source', query: 'Gulshan 2' })).toBe(true);
  });
});

describe('isUnboundPlace', () => {
  /*
   * The start field holds two things that look the same and mean opposite
   * things: text someone typed, and a place they picked. Only the second has a
   * coordinate. `null` means "use the GPS" while the field reads `My Location`,
   * and means "nothing chosen yet" the moment it is typed over -- and the router
   * used to treat both as the GPS, so typing a start and picking a destination
   * routed from wherever the phone was while the box showed the typed place.
   */
  it('a picked place is bound, whatever the text says', () => {
    expect(
      isUnboundPlace({ query: 'Gulshan 2', location: { latitude: 23.79, longitude: 90.41 } }),
    ).toBe(false);
  });

  it('`My Location` is not unbound — null there means the GPS, deliberately', () => {
    expect(isUnboundPlace({ query: NOT_A_PLACE, location: null })).toBe(false);
  });

  it('an empty field is not unbound either', () => {
    expect(isUnboundPlace({ query: '', location: null })).toBe(false);
    expect(isUnboundPlace({ query: '   ', location: null })).toBe(false);
  });

  it('typed text with no coordinate IS unbound — the case that was invisible', () => {
    expect(isUnboundPlace({ query: 'Gulshan 2', location: null })).toBe(true);
  });

  it('is unbound mid-keystroke, so the stale route goes as soon as editing starts', () => {
    expect(isUnboundPlace({ query: 'G', location: null })).toBe(true);
  });

  it('ignores surrounding whitespace when deciding', () => {
    expect(isUnboundPlace({ query: `  ${NOT_A_PLACE}  `, location: null })).toBe(false);
  });
});
