/**
 * The news page's data shaping. D09.
 *
 * Two of these matter more than the rest. **Sample data must stay countable**,
 * because the page's day-to-day job is to answer "did ingestion work today?" and
 * it cannot do that if 22 fixture headlines are indistinguishable from real ones.
 * And **one article must produce one card**, because a merged flag carries a source
 * per publisher and two flags can cite the same piece.
 */
import {
  newsFromFlags,
  splitByTense,
  realCount,
  outletName,
  isWebLink,
  isGeneratedPlaceholder,
} from './news';
import type { RiskFlag } from '../../types/contracts/risk';

function flag(overrides: Partial<RiskFlag> = {}): RiskFlag {
  return {
    flagId: 'f1',
    eventKey: 'live-abc-0',
    kind: 'fire',
    status: 'unconfirmed',
    lat: 23.71,
    lon: 90.4,
    radiusM: 400,
    severity0: 70,
    severityNow: 50,
    halfLifeHours: 3.5,
    observedAt: '2026-10-10T10:00:00Z',
    expiresAt: '2026-10-10T20:00:00Z',
    validFrom: null,
    validTo: null,
    sourceCount: 1,
    sources: [],
    mobilityStatement: 'Road blocked near Bangshal.',
    timeProfile: null,
    confirmedAt: null,
    confidence: 0.6,
    ...overrides,
  } as RiskFlag;
}

const source = (over: Partial<any> = {}) => ({
  sourceId: 'prothom_alo',
  url: 'https://example.test/a',
  publishedAt: '2026-10-10T09:00:00Z',
  title: 'Fire in Bangshal, traffic diverted',
  snippet: null,
  ...over,
});

describe('newsFromFlags', () => {
  it('makes one card per article', () => {
    const entries = newsFromFlags([
      flag({ sources: [source(), source({ url: 'https://example.test/b' })] as any }),
    ]);
    expect(entries).toHaveLength(2);
  });

  it('does not show the same article twice when two flags cite it', () => {
    const shared = source();
    const entries = newsFromFlags([
      flag({ flagId: 'f1', sources: [shared] as any }),
      flag({ flagId: 'f2', sources: [shared] as any }),
    ]);
    expect(entries).toHaveLength(1);
  });

  it('skips flags with no article behind them', () => {
    expect(newsFromFlags([flag({ kind: 'other', sources: [] as any })])).toEqual([]);
  });

  it('skips the chronic layer even though it cites a real statistics page', () => {
    /*
     * `chronic.py` puts a genuine police.gov.bd link on every derived chronic flag.
     * Counting it made the header read "1 real of 30" on a day when no news article
     * had been ingested at all — and that counter is the whole reason this screen
     * exists. A statistics table is not news.
     */
    const stats = {
      sourceId: 'bd_police_statistics',
      url: 'https://www.police.gov.bd/en/crime_statistic_comparative_statement',
      publishedAt: null,
      title: 'Reported crime statistics — DMP',
      snippet: null,
    };
    expect(newsFromFlags([flag({ kind: 'chronic', sources: [stats] as any })])).toEqual([]);
  });

  it('does not let the statistics page inflate the real count', () => {
    const stats = {
      sourceId: 'bd_police_statistics',
      url: 'https://www.police.gov.bd/en/crime_statistic_comparative_statement',
      publishedAt: null,
      title: 'Reported crime statistics — DMP',
      snippet: null,
    };
    const entries = newsFromFlags([
      flag({ kind: 'chronic', sources: [stats] as any }),
      flag({ sources: [source({ url: 'sample:prothom_alo/seed/x' })] as any }),
    ]);
    expect(entries).toHaveLength(1);
    expect(realCount(entries)).toBe(0);
  });

  it('puts the newest article first', () => {
    const entries = newsFromFlags([
      flag({
        sources: [
          source({ url: 'https://example.test/old', publishedAt: '2026-10-10T06:00:00Z' }),
          source({ url: 'https://example.test/new', publishedAt: '2026-10-10T11:00:00Z' }),
        ] as any,
      }),
    ]);
    expect(entries.map(e => e.url)).toEqual([
      'https://example.test/new',
      'https://example.test/old',
    ]);
  });

  it('sorts an undated article last, because null is not "just now"', () => {
    const entries = newsFromFlags([
      flag({
        sources: [
          source({ url: 'https://example.test/undated', publishedAt: null }),
          source({ url: 'https://example.test/dated' }),
        ] as any,
      }),
    ]);
    expect(entries[entries.length - 1].url).toBe('https://example.test/undated');
  });

  it('still shows an article that came with no headline', () => {
    const entries = newsFromFlags([flag({ sources: [source({ title: null })] as any })]);
    // The fact that it was read is the information; the flag's statement stands in.
    expect(entries[0].title).toBe('Road blocked near Bangshal.');
  });

  it('carries the flag, so a card can show what the article produced', () => {
    const entries = newsFromFlags([flag({ sources: [source()] as any })]);
    expect(entries[0].flag.mobilityStatement).toBe('Road blocked near Bangshal.');
  });
});

describe('sample data stays countable', () => {
  const fixture = flag({
    sources: [source({ url: 'sample:prothom_alo/seed/bangshal-fire' })] as any,
  });
  const real = flag({ sources: [source({ url: 'https://prothomalo.com/x' })] as any });

  it('marks a fixture source as sample', () => {
    expect(newsFromFlags([fixture])[0].isSample).toBe(true);
  });

  it('does not mark a real article as sample', () => {
    expect(newsFromFlags([real])[0].isSample).toBe(false);
  });

  it('counts only the real ones, which is the number the page exists for', () => {
    const entries = newsFromFlags([fixture, real]);
    expect(entries).toHaveLength(2);
    expect(realCount(entries)).toBe(1);
  });

  it('does not hide sample data — an empty page and a seeded page differ', () => {
    // Hiding fixtures would make a day with no ingestion look identical to a day
    // with plenty, which is exactly the question this screen answers.
    expect(newsFromFlags([fixture])).toHaveLength(1);
  });
});

describe('generated fixture placeholders are not articles', () => {
  /*
   * `fixture.py::_generated_sources` invents one reference per seeded flag that did
   * not spell its own out, titled "Sample report — <place>", and its comment says
   * the titles are deliberately implausible so nobody mistakes the fixture for a
   * news archive. Measured against the real seeded surface: without this filter the
   * Today tab is 274 cards, 272 of them placeholders, and the two real articles are
   * invisible among them.
   */
  const placeholder = {
    sourceId: 'sample_the_daily_star',
    url: 'sample:sample_the_daily_star/seed-mirpur10-accident',
    publishedAt: '2026-10-10T09:00:00Z',
    title: 'Sample report — Mirpur 10',
    snippet: null,
  };

  it('recognises one', () => {
    expect(isGeneratedPlaceholder(placeholder as any)).toBe(true);
  });

  it('leaves them off the page entirely', () => {
    expect(newsFromFlags([flag({ sources: [placeholder] as any })])).toEqual([]);
  });

  it('keeps a hand-written sample headline, which does read like reporting', () => {
    const written = source({
      url: 'sample:prothom_alo/seed/bangshal-fire',
      title: 'Fire service responds in Bangshal, traffic diverted',
    });
    expect(isGeneratedPlaceholder(written as any)).toBe(false);
    const entries = newsFromFlags([flag({ sources: [written] as any })]);
    expect(entries).toHaveLength(1);
    expect(entries[0].isSample).toBe(true);
  });

  it('never discards a real article, whatever it is called', () => {
    const real = source({
      url: 'https://prothomalo.com/x',
      title: 'Sample report — this is a real url',
    });
    expect(isGeneratedPlaceholder(real as any)).toBe(false);
    expect(newsFromFlags([flag({ sources: [real] as any })])).toHaveLength(1);
  });
});

describe('splitByTense', () => {
  it('separates announcements from what has already happened', () => {
    const entries = newsFromFlags([
      flag({ sources: [source()] as any }),
      flag({
        validFrom: '2026-10-11T04:00:00Z',
        validTo: '2026-10-11T10:00:00Z',
        sources: [source({ url: 'https://example.test/tomorrow' })] as any,
      }),
    ]);
    const { live, scheduled } = splitByTense(entries);
    expect(live).toHaveLength(1);
    expect(scheduled).toHaveLength(1);
    expect(scheduled[0].url).toContain('tomorrow');
  });
});

describe('outletName', () => {
  it('names a publisher a reader recognises', () => {
    expect(outletName('prothom_alo')).toBe('Prothom Alo');
  });

  it('names the real outlet behind a sample source', () => {
    expect(outletName('sample_the_daily_star')).toBe('The Daily Star');
  });

  it('falls through to the id rather than showing nothing', () => {
    // Ugly on screen, and that is the point: it prompts someone to add the name.
    expect(outletName('somokal')).toBe('somokal');
  });
});

describe('isWebLink', () => {
  it('accepts a real article', () => {
    expect(isWebLink('https://prothomalo.com/x')).toBe(true);
  });

  it('rejects the fixture scheme, which resolves nowhere', () => {
    expect(isWebLink('sample:prothom_alo/seed/x')).toBe(false);
  });
});
