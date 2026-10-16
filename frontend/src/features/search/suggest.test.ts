import { MIN_QUERY_LENGTH, NOT_A_PLACE, shouldSuggest } from './suggest';

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
