/**
 * Instruction phrasing.
 *
 * The bug this file is mostly guarding against is "Turn left onto" followed by
 * nothing. OSM has no `name` tag for a large share of Dhaka's lanes, service roads
 * and residential streets, so an unnamed step is the common case rather than the
 * edge case — and a sentence that trails off is worse than the plainer one that
 * does not mention a road at all.
 */

import {
  currentRoadName,
  instructionFor,
  stepInstruction,
  turnInstruction,
} from './instructions';
import type { NavStep, StepHint, TurnHint } from './progress';

function step(partial: Partial<NavStep>): NavStep {
  return {
    name: '',
    maneuver_type: 'turn',
    modifier: 'left',
    distance_m: 200,
    start_m: 0,
    ...partial,
  };
}

function hint(next: Partial<NavStep> | null, distanceM = 120, current?: Partial<NavStep>): StepHint {
  return {
    current: current ? step(current) : step({ name: 'Current Road' }),
    next: next ? step(next) : null,
    distanceM,
  };
}

describe('a named manoeuvre', () => {
  it('names the road', () => {
    expect(stepInstruction(hint({ name: 'Mirpur Road', modifier: 'left' }))).toBe(
      'Turn left onto Mirpur Road in 120 m',
    );
  });

  it('names the road on a right turn', () => {
    expect(stepInstruction(hint({ name: 'Satmasjid Road', modifier: 'right' }, 350))).toBe(
      'Turn right onto Satmasjid Road in 350 m',
    );
  });

  it('keeps a Bangla name verbatim', () => {
    // OSM tags plenty of Dhaka roads in Bangla, and that is the name the street
    // sign carries. Transliterating it here would be inventing a name.
    expect(stepInstruction(hint({ name: 'মিরপুর রোড', modifier: 'left' }, 80))).toBe(
      'Turn left onto মিরপুর রোড in 80 m',
    );
  });
});

describe('an unnamed manoeuvre', () => {
  it('never says "onto" with nothing after it', () => {
    const instruction = stepInstruction(hint({ name: '', modifier: 'left' }));
    expect(instruction).toBe('Turn left in 120 m');
    expect(instruction).not.toContain('onto');
  });

  it('is still a complete sentence for every manoeuvre type', () => {
    const types = [
      'turn',
      'new name',
      'continue',
      'fork',
      'merge',
      'end of road',
      'roundabout',
      'on ramp',
      'off ramp',
      'depart',
    ];
    for (const maneuver_type of types) {
      const instruction = stepInstruction(hint({ name: '', maneuver_type, modifier: 'left' }));
      expect(instruction).toBeTruthy();
      expect(instruction).not.toContain('onto');
      expect(instruction).not.toMatch(/\s{2,}/);
      expect(instruction!.trim()).toBe(instruction);
    }
  });

  it('never leaves a dangling modifier when there is none', () => {
    for (const maneuver_type of ['turn', 'fork', 'merge', 'roundabout', 'end of road']) {
      const instruction = stepInstruction(hint({ name: '', maneuver_type, modifier: '' }));
      expect(instruction).toBeTruthy();
      expect(instruction).not.toMatch(/\s{2,}/);
    }
  });
});

describe('manoeuvre vocabulary', () => {
  it('spells out a U-turn rather than saying "turn uturn"', () => {
    expect(stepInstruction(hint({ modifier: 'uturn', name: '' }))).toBe(
      'Make a U-turn in 120 m',
    );
  });

  it('does not say "turn straight"', () => {
    const instruction = stepInstruction(hint({ modifier: 'straight', name: 'Airport Road' }));
    expect(instruction).not.toContain('straight');
    expect(instruction).toBe('Continue onto Airport Road in 120 m');
  });

  it('phrases a fork as keeping to a side', () => {
    expect(stepInstruction(hint({ maneuver_type: 'fork', modifier: 'right', name: '' }, 200))).toBe(
      'Keep right in 200 m',
    );
  });

  it('phrases the end of a road as such', () => {
    expect(
      stepInstruction(hint({ maneuver_type: 'end of road', modifier: 'left', name: '' }, 90)),
    ).toBe('At the end of the road, turn left in 90 m');
  });

  it('phrases a roundabout', () => {
    expect(
      stepInstruction(hint({ maneuver_type: 'roundabout', modifier: 'left', name: '' }, 150)),
    ).toBe('At the roundabout, go left in 150 m');
  });

  it('handles a manoeuvre type it has never seen', () => {
    // OSRM's vocabulary is larger than the table, and an unlisted type must still
    // produce a usable sentence rather than the raw token.
    const instruction = stepInstruction(
      hint({ maneuver_type: 'notification', modifier: 'right', name: 'Gulshan Avenue' }),
    );
    expect(instruction).toBe('Turn right onto Gulshan Avenue in 120 m');
    expect(instruction).not.toContain('notification');
  });
});

describe('arrival', () => {
  it('says arrive, with a distance, while still away', () => {
    expect(stepInstruction(hint({ maneuver_type: 'arrive', modifier: '', name: '' }, 180))).toBe(
      'Arrive in 180 m',
    );
  });

  it('drops the distance at the destination', () => {
    expect(stepInstruction(hint({ maneuver_type: 'arrive', modifier: '', name: '' }, 8))).toBe(
      'Arrive at your destination',
    );
  });

  it('never says "onto" on arrival, even if the final way is named', () => {
    const instruction = stepInstruction(
      hint({ maneuver_type: 'arrive', modifier: '', name: 'Dhanmondi 27' }, 150),
    );
    expect(instruction).not.toContain('onto');
  });
});

describe('close manoeuvres', () => {
  it('says "now" rather than a distance inside the GPS error', () => {
    // "Turn left in 10 m" while standing at the corner is false precision.
    expect(stepInstruction(hint({ name: 'Green Road', modifier: 'left' }, 12))).toBe(
      'Turn left onto Green Road now',
    );
  });

  it('still gives a distance at 20 m and beyond', () => {
    expect(stepInstruction(hint({ name: '', modifier: 'left' }, 25))).toBe(
      'Turn left in 30 m',
    );
  });
});

describe('the geometric fallback', () => {
  const turn = (partial: Partial<TurnHint>): TurnHint => ({
    direction: 'left',
    distanceM: 120,
    bearing: 0,
    ...partial,
  });

  it('says continue when no turn is in range', () => {
    expect(turnInstruction(turn({ direction: 'straight', distanceM: 1200 }))).toBe(
      'Continue for 1.2 km',
    );
  });

  it('never claims a road name', () => {
    expect(turnInstruction(turn({ direction: 'right' }))).toBe('Right in 120 m');
    expect(turnInstruction(turn({ direction: 'right' }))).not.toContain('onto');
  });

  it('has something to say with no turn at all', () => {
    expect(turnInstruction(null)).toBe('Following your route');
  });
});

describe('choosing a source', () => {
  const turn: TurnHint = { direction: 'right', distanceM: 300, bearing: 90 };

  it('prefers the step when one exists', () => {
    const chosen = instructionFor(hint({ name: 'Kemal Ataturk Avenue', modifier: 'left' }), turn);
    expect(chosen).toContain('Kemal Ataturk Avenue');
  });

  it('falls back to the geometry when there are no steps', () => {
    // The straight-line estimate has no steps at all, and a route whose steps came
    // back empty is the same case.
    expect(instructionFor(null, turn)).toBe('Right in 300 m');
  });

  it('falls back when the step hint has neither a next nor a current step', () => {
    const empty: StepHint = { current: null, next: null, distanceM: 400 };
    expect(instructionFor(empty, turn)).toBe('Right in 300 m');
  });
});

describe('the current road', () => {
  it('reports a named road', () => {
    expect(currentRoadName(hint(null, 100, { name: 'New Elephant Road' }))).toBe(
      'New Elephant Road',
    );
  });

  it('reports nothing for an unnamed lane rather than an empty string', () => {
    expect(currentRoadName(hint(null, 100, { name: '' }))).toBe(null);
  });

  it('reports nothing when there are no steps', () => {
    expect(currentRoadName(null)).toBe(null);
  });
});
