/**
 * The client half of the attribution invariant. S30.
 *
 * The backend guarantees that `statement` names its publisher — `policy/
 * attribution.py` is its only writer and a database CHECK refuses anything else.
 * That guarantee is worth nothing if a screen then renders its own sentence from
 * `category`, which is the cheapest-looking way to make a crime pin "read better"
 * and which would quietly drop the attribution that licenses the whole surface.
 *
 * So this file asserts two things:
 *
 * 1. the client vocabulary matches the server's, so a category cannot arrive
 *    without a colour or a label — the Defect 3 failure, which was invisible
 *    because `Record` lookups return `undefined` rather than throwing;
 * 2. **no component composes crime text from `category`.** A source scan, which is
 *    crude and is the only check that catches the failure that actually happens.
 */

import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';

import {
  CRIME_CATEGORIES,
  CRIME_COLORS,
  crimeCategoryLabel,
  crimeColor,
} from './crime';
import type { NewsCrimeIncident } from './newsCrime';

const SRC = join(__dirname, '..', '..');

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap(entry => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full);
    return /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [full] : [];
  });
}

describe('the crime vocabulary is shared, not duplicated', () => {
  it('matches the eight values news_crime_incidents.category accepts', () => {
    // The server's CHECK constraint, verbatim. These two lists drifting is how a
    // published incident arrives with a category the map cannot colour.
    expect([...CRIME_CATEGORIES].sort()).toEqual(
      [
        'assault',
        'burglary',
        'fraud',
        'harassment',
        'other',
        'robbery',
        'theft',
        'vandalism',
      ].sort(),
    );
  });

  it('gives every category a colour and a label', () => {
    for (const category of CRIME_CATEGORIES) {
      expect(CRIME_COLORS[category]).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(crimeCategoryLabel(category).length).toBeGreaterThan(0);
    }
  });

  it('falls back to grey rather than undefined for an unknown category', () => {
    // Defect 3's actual symptom: a Record lookup that misses returns undefined,
    // which renders as no colour at all rather than as an error.
    expect(crimeColor('not-a-category')).toBe('#9E9E9E');
  });

  it('defines the colours in exactly one place', () => {
    // Moved out of MapScreen in S30, when NewsCrimeMarker became the second
    // drawer of crime markers. A second literal map is the drift that Defect 3 is.
    const offenders = walk(SRC).filter(file => {
      if (file.endsWith(join('types', 'contracts', 'crime.ts'))) return false;
      const source = readFileSync(file, 'utf8');
      return /CRIME_COLORS\s*(:|=)\s*\{/.test(source);
    });
    expect(offenders).toEqual([]);
  });
});

describe('attribution survives the trip to the screen', () => {
  const incident: NewsCrimeIncident = {
    incidentId: 'a',
    category: 'robbery',
    status: 'published',
    lat: 23.75,
    lon: 90.4,
    radiusM: 250,
    severityNow: 42,
    observedAt: '2026-10-12T10:00:00Z',
    statement: 'Robbery reported by Prothom Alo, 2 days ago',
    sourceCount: 1,
    sources: [
      {
        sourceId: 'prothom_alo',
        url: 'https://www.prothomalo.com/x',
        publishedAt: '2026-10-12T10:00:00Z',
        title: 'Robbery at Mirpur 10',
      },
    ],
  };

  it('carries a statement that names a publisher', () => {
    // The shape the server guarantees. A client that received anything else is
    // looking at a backend whose CHECK has been removed.
    expect(incident.statement).toContain(' reported by ');
  });

  it('carries a checkable source for every claim', () => {
    // An attributed claim the reader cannot check is just a claim.
    expect(incident.sources.length).toBeGreaterThan(0);
    for (const source of incident.sources) {
      expect(source.url).toMatch(/^https?:\/\//);
    }
  });

  it('never has a component build crime text out of the category', () => {
    // The real check. Any template literal or concatenation that puts a category
    // next to crime wording is a sentence the attribution guard never saw.
    //
    // Narrow by design: it looks for `category` interpolated into a string in the
    // files that draw this surface. Rendering `{incident.statement}` or
    // `crimeCategoryLabel(category)` inside a badge is fine — a label is not a
    // sentence — so the pattern targets interpolation into longer prose.
    const drawers = walk(SRC).filter(file => {
      const source = readFileSync(file, 'utf8');
      return source.includes('NewsCrimeIncident') || source.includes('RouteNewsCrime');
    });
    expect(drawers.length).toBeGreaterThan(0);

    const banned = /`[^`]*\$\{[^}]*\bcategory\b[^}]*\}[^`]*\b(reported|happened|occurred|took place|was)\b/i;
    const offenders = drawers.filter(file => banned.test(readFileSync(file, 'utf8')));

    expect(offenders).toEqual([]);
  });
});
