/**
 * The headlines behind the map. D09.
 *
 * Every flag read out of the news carries its sources — outlet, headline,
 * publication time, url — and until now those were visible only one tap deep, in
 * the sheet of whichever pin you happened to press. This turns them the other way
 * round: one card per article, newest first, so the question "what did the system
 * read today?" has a screen rather than an archaeology exercise.
 *
 * **It is also the diagnostic surface for ingestion.** Live ingestion is currently
 * thin — most of what the map serves is seeded sample data — and the fix for that
 * is next phase. A page that silently mixed 22 sample headlines in with the real
 * ones would make it impossible to tell whether a day's ingestion had worked, so
 * `isSample` is carried on every entry and the screen says so out loud.
 *
 * Pure, and imports nothing from React, so it is testable: screens that pull in
 * `react-native-maps` are not.
 */
import type { RiskFlag, SourceRef } from '../../types/contracts/risk';
import { isScheduledFlag } from './scheduled';

export interface NewsEntry {
  /** Stable across refreshes, so React keys do not churn. */
  key: string;
  outletId: string;
  title: string;
  url: string;
  publishedAt: string | null;
  /**
   * Fixture sources use a `sample:` scheme and resolve nowhere. Marked rather
   * than hidden: hiding them would make the page look like successful ingestion
   * on a day when nothing was ingested.
   */
  isSample: boolean;
  /** What the article produced on the map. */
  flag: RiskFlag;
}

/** Only real web links open. Fixture sources use a `sample:` scheme. */
export const isWebLink = (url: string): boolean => /^https?:\/\//.test(url);

/**
 * A generated fixture placeholder, which is not an article and must not be listed
 * as one.
 *
 * `fixture.py::_generated_sources` invents a reference for every seeded flag that
 * did not spell its own sources out — about 250 of them — so that `source_count`
 * has something behind it. Its comment says the titles are *deliberately* not
 * plausible headlines, "and the point of the `sample_` marking is that nobody —
 * including us, at midnight on the 23rd — can mistake it for one."
 *
 * Respecting that is what keeps this page readable: without the filter the Today
 * tab is 274 cards, 272 of which read `Sample report — Mirpur 10`, and the two real
 * articles are lost in them. The hand-written sample headlines in the first 22
 * fixture entries are kept — those read like reporting and are marked as sample.
 *
 * Matched on the title prefix, which is a literal shared with the generator. That
 * coupling is deliberate and cheap: the alternative was adding a field to
 * `SourceRef`, and D09 is not changing the contract to tidy a fixture.
 */
export const isGeneratedPlaceholder = (source: SourceRef): boolean =>
  !isWebLink(source.url) && (source.title ?? '').startsWith('Sample report');

/*
 * Why the chronic layer is skipped, even though it has a real https source.
 *
 * `chronic.py` cites `police.gov.bd/.../crime_statistic_comparative_statement` on
 * every derived chronic flag — a genuine link to published Bangladesh Police unit
 * statistics. Deduplicated it is one card, titled "Reported crime statistics".
 *
 * It was counted as a real article, which made the header read `1 real of 30` on a
 * day when **no news article had been ingested at all**. That is the one number
 * this page exists to report honestly, and a permanent +1 from a statistics table
 * makes it unreadable: is "1 real" an article, or is it the statistics page again?
 *
 * A statistics table is not news. The citation still appears where it belongs, on
 * the chronic flag's own sheet, as that layer's provenance.
 */

/**
 * Publisher ids to the names a reader recognises.
 *
 * Mirrors `OUTLET_NAMES` in `RiskFlagSheet`, which mirrors
 * `backend/app/ingestion/sources/__init__.py`. An id not listed here falls
 * through to the id itself, which is ugly but never wrong — and a new source
 * appearing as `somokal` on screen is a visible prompt to add it, where a
 * silently blank outlet would not be.
 */
const OUTLET_NAMES: Record<string, string> = {
  prothom_alo: 'Prothom Alo',
  the_daily_star: 'The Daily Star',
  bdnews24: 'bdnews24',
  jugantor: 'Jugantor',
  channel24: 'Channel 24',
  ekattor_tv: 'Ekattor TV',
  independent_tv: 'Independent TV',
  somoy_tv: 'Somoy TV',
  demo_second_source: 'Demo second source',
};

export function outletName(sourceId: string): string {
  const base = sourceId.replace(/^sample_/, '');
  const known = OUTLET_NAMES[base];
  // The `sample_` prefix is deliberately not hidden here — `isSample` carries
  // that, and the screen is what decides how loudly to say it.
  return known ?? base;
}

/**
 * Flags to news cards: one per article, newest first.
 *
 * Deduplicated by url. A flag that Rumour Guard merged carries one source per
 * publisher, and two different flags can cite the same article when one piece
 * reports two incidents — the first occurrence wins, because the alternative is
 * the same headline twice on one screen with no way for a reader to tell why.
 *
 * Three things are skipped: flags with no sources, generated fixture placeholders
 * (see `isGeneratedPlaceholder`), and the **chronic layer** (see below). This page
 * is about what was read in the news, not about everything on the map.
 */
export function newsFromFlags(flags: RiskFlag[]): NewsEntry[] {
  const seen = new Set<string>();
  const entries: NewsEntry[] = [];

  for (const flag of flags) {
    if (flag.kind === 'chronic') continue;
    for (const source of flag.sources as SourceRef[]) {
      if (!source.url || seen.has(source.url)) continue;
      if (isGeneratedPlaceholder(source)) continue;
      seen.add(source.url);
      entries.push({
        key: source.url,
        outletId: source.sourceId,
        // An outlet that gave us no headline still gets a card, because the fact
        // that it was read is the information. The flag's own statement stands in.
        title: source.title?.trim() || flag.mobilityStatement,
        url: source.url,
        publishedAt: source.publishedAt,
        isSample: !isWebLink(source.url),
        flag,
      });
    }
  }

  return entries.sort((a, b) => {
    // Undated sources sort last rather than first: a null is "we do not know
    // when", which is not the same claim as "just now".
    if (!a.publishedAt) return b.publishedAt ? 1 : 0;
    if (!b.publishedAt) return -1;
    return Date.parse(b.publishedAt) - Date.parse(a.publishedAt);
  });
}

/** Today's articles and tomorrow's announcements, split for the two tabs. */
export function splitByTense(entries: NewsEntry[]): {
  live: NewsEntry[];
  scheduled: NewsEntry[];
} {
  return {
    live: entries.filter(e => !isScheduledFlag(e.flag)),
    scheduled: entries.filter(e => isScheduledFlag(e.flag)),
  };
}

/**
 * How many of these came from real reporting.
 *
 * The number the page exists to make visible day to day. `0 of 24` on a Tuesday
 * means ingestion did nothing on Tuesday, and that should take one glance to
 * establish rather than a database session.
 */
export function realCount(entries: NewsEntry[]): number {
  return entries.filter(e => !e.isSample).length;
}
