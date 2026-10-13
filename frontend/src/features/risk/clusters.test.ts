/**
 * Invariants for the community-cluster layer, read out of the source tree.
 *
 * These check how the code is *written*, so there is nothing to import — the same
 * approach `theme/theme.ui.test.ts` and `features/alerts/channels.test.ts` take.
 *
 * All five guard a regression that would look completely fine on screen:
 *
 * 1. the map must never query another user's reports again;
 * 2. a cluster must not be coloured by a severity band;
 * 3. the published statement must be rendered, never rebuilt;
 * 4. clusters and flags must never be counted as one number;
 * 5. the retired `verified` column must not come back.
 *
 * The first is the one worth the file on its own. Before B13, `MapScreen` ran
 * `.from('crime_reports').select(...)` with no filter at all: every report ever
 * filed by anyone, unbounded in time and space, drawn as a pin. RLS now refuses
 * that query, so the bug cannot leak data any more — but a client that asks for it
 * would simply render an empty layer, and "the reports stopped showing up" is a
 * confusing way to discover that someone reintroduced the old call.
 */

import fs from 'fs';
import path from 'path';

const SRC = path.join(__dirname, '..', '..');

function read(...segments: string[]): string {
  return fs.readFileSync(path.join(SRC, ...segments), 'utf8');
}

/**
 * Source with comments removed.
 *
 * Load-bearing, and the first version of this file was wrong without it. Every
 * rule below is explained in a comment *at the site it governs* -- the cluster
 * marker's header says in prose that it must not use `riskBand`, and
 * `crime.service.ts` records that `verified: false` used to be written there. A
 * scanner that reads comments therefore fails on the documentation of the very
 * rule it is checking, which is the most confusing kind of false positive: the
 * fix looks like deleting the explanation.
 *
 * JSX comments (`{/* ... *\/}`) are block comments to this, which is what we want.
 * Strings are left alone: a banned term inside a string literal is a real finding.
 */
function codeOnly(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^[ 	]*\/\/.*$/gm, '');
}

/** Every .ts/.tsx under src/, so a new screen is covered without being listed. */
function sourceFiles(dir: string = SRC): string[] {
  const found: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...sourceFiles(full));
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
      found.push(full);
    }
  }
  return found;
}

describe('the map only ever asks for the signed-in user’s own reports', () => {
  const mapScreen = codeOnly(read('screens', 'Map', 'MapScreen.tsx'));

  it('filters the report query by user_id', () => {
    const query = mapScreen.split("from('crime_reports')")[1] ?? '';
    expect(query).toContain(".eq('user_id', user.id)");
  });

  it('bounds the report query in time', () => {
    const query = mapScreen.split("from('crime_reports')")[1] ?? '';
    expect(query).toContain("gte('incident_date_time'");
  });

  it('leaves out reports the author has withdrawn or that were removed', () => {
    const query = mapScreen.split("from('crime_reports')")[1] ?? '';
    // Excluding the retired states, not requiring 'filed'. A row written before
    // the B13 migration still says 'pending', and an `.eq('status', 'filed')`
    // would return nothing at all against an unmigrated database.
    expect(query).toContain(".not('status', 'in'");
    expect(query).toContain('withdrawn');
    expect(query).toContain('removed');
    expect(query).not.toContain(".eq('status', 'filed')");
  });

  it('is the only place in the app that reads the reports table unscoped', () => {
    // Every other reader goes through `crime.service.ts`, which scopes by user or
    // by report id. A new `from('crime_reports')` anywhere else is the thing to
    // notice.
    const readers = sourceFiles()
      .filter(file => fs.readFileSync(file, 'utf8').includes("from('crime_reports')"))
      .map(file => path.relative(SRC, file).split(path.sep).join('/'));
    expect(readers.sort()).toEqual([
      'screens/Map/MapScreen.tsx',
      'services/crime.service.ts',
    ]);
  });

  it('draws the user’s own history behind a toggle that starts off', () => {
    // Their reports are historical records, not live hazards. The layer that is on
    // by default is the one that decays.
    expect(mapScreen).toContain('useState(false)');
    expect(mapScreen).toContain('showMyReports && crimeReports.map');
  });
});

describe('a cluster is not graded for severity', () => {
  const marker = codeOnly(read('components', 'CommunityClusterMarker.tsx'));

  it('never colours itself from a risk band', () => {
    // `riskBand(severityNow)` is how flags are coloured. Using it here would imply
    // the app has graded how bad a place is from a handful of reports, which it has
    // not -- `severity_for` derives severity from the reporter count alone and caps
    // it well below a live event precisely so it cannot be read as a measurement.
    expect(marker).not.toContain('riskBand');
  });

  it('uses the accent colour, not a danger colour', () => {
    expect(marker).toContain('t.accent');
    expect(marker).not.toContain('t.danger');
  });

  it('shows the reporter count, not the report count', () => {
    // The reporter count is what decided the tier, and the only one that is
    // evidence about the place rather than about how much one person typed.
    // Bounded to the <Text> element. Slicing to the end of the file would also
    // pick up the memo comparator, which legitimately compares both counts.
    const pin = (marker.split('allowFontScaling={false}')[1] ?? '').split('</Text>')[0];
    expect(pin).toContain('cluster.reporterCount');
    expect(pin).not.toContain('cluster.reportCount');
  });

  it('keeps the same solid-versus-dashed grammar the flag marker uses', () => {
    // One rule across both layers: solid means corroborated. A second visual
    // language for the same distinction would be the real inconsistency.
    const flagMarker = codeOnly(read('components', 'RiskFlagMarker.tsx'));
    for (const source of [marker, flagMarker]) {
      expect(source).toContain("borderStyle:");
      expect(source).toContain("'dashed'");
    }
  });
});

describe('the published statement is rendered, never rebuilt', () => {
  it('is used verbatim everywhere it appears', () => {
    // `to_cluster_statement` is the only producer and it passes the framing guard.
    // A client composing its own sentence from `reporterCount` and `firstReportAt`
    // would be free to call a place dangerous, which is exactly what that guard
    // exists to prevent.
    const offenders: string[] = [];
    for (const file of sourceFiles()) {
      const source = codeOnly(fs.readFileSync(file, 'utf8'));
      if (!source.includes('cluster')) continue;
      // The shape of a hand-built claim: a sentence fragment next to a count.
      if (/within \$\{|reports within|in the last \$\{/.test(source)) {
        offenders.push(path.relative(SRC, file).split(path.sep).join('/'));
      }
    }
    expect(offenders).toEqual([]);
  });

  it('never puts a judgement word next to a cluster', () => {
    const forbidden = /\b(dangerous|unsafe|avoid this area|high crime)\b/i;
    for (const file of sourceFiles()) {
      const source = codeOnly(fs.readFileSync(file, 'utf8'));
      if (!/cluster/i.test(source)) continue;
      expect(source).not.toMatch(forbidden);
    }
  });
});

describe('clusters and flags are counted separately', () => {
  const mapScreen = codeOnly(read('screens', 'Map', 'MapScreen.tsx'));

  it('never sums the two into one total', () => {
    // "14 things on the map" is the number that hides exactly the distinction this
    // layer exists to make.
    expect(mapScreen).not.toMatch(/riskFlags\.length\s*\+\s*clusters\.length/);
    expect(mapScreen).not.toMatch(/clusters\.length\s*\+\s*riskFlags\.length/);
  });

  it('labels the cluster count as report areas rather than flags', () => {
    expect(mapScreen).toContain('report areas');
  });

  it('keeps them in separate lists on the route card', () => {
    const card = codeOnly(read('components', 'RouteComparisonCard.tsx'));
    expect(card).toContain('route.flags.map');
    expect(card).toContain('clusters.map');
    expect(card).toContain('Community reports');
  });
});

describe('the retired verified column stays retired', () => {
  it('is not read anywhere in the app', () => {
    const offenders: string[] = [];
    for (const file of sourceFiles()) {
      const source = codeOnly(fs.readFileSync(file, 'utf8'));
      // Any mention at all, once the comments are gone: `report.verified` as a
      // property read, and the bare column name inside a Supabase select list.
      //
      // The left-hand boundary is what keeps `is_verified` out of this -- that is a
      // column on `users`, it is a real and unrelated thing, and a scanner that
      // flagged it would be unfixable.
      if (/(?<![_\w])verified\b/.test(source)) {
        offenders.push(path.relative(SRC, file).split(path.sep).join('/'));
      }
    }
    expect(offenders).toEqual([]);
  });

  it('is not written on insert', () => {
    const service = codeOnly(read('services', 'crime.service.ts'));
    expect(service).not.toContain('verified: false');
    expect(service).not.toContain('verified: true');
    // And the status it does write is the new vocabulary.
    expect(service).toContain("status: 'filed'");
    expect(service).not.toContain("status: 'pending'");
  });
});
