/**
 * Mirror of `backend/app/contracts/news_crime.py`.
 *
 * HAND-MIRRORED, like `risk.ts` and `community.ts`, and for the same reason: the
 * backend is the source of truth and there is no generator. A change to
 * `app/contracts/news_crime.py` and a change to this file go in the same commit.
 *
 * ## The third surface, and why a screen must know which one it is holding
 *
 * | | `RiskFlag` | `CommunityCluster` | `NewsCrimeIncident` |
 * |---|---|---|---|
 * | source | edited news, police stats | app users' reports | one named masthead |
 * | claims | a road is blocked | several people reported something | a publisher reported a crime |
 * | text written by | `policy/framing.py` | `policy/community.py` | `policy/attribution.py` |
 * | names the offence | never | never | **yes** |
 * | best confidence | 1.0 | 0.6 | 0.7 |
 *
 * `Defect 54` is the log of what happens when a surface forgets a distinction like
 * this: the map drew reports and flags as the same pin, *"which makes them look
 * interchangeable"*. Three kinds of claim now share a map, so rendering them
 * differently is not decoration — it is the only thing stopping the screen from
 * asserting more than the data does.
 *
 * ## Why this one may name the offence when the other two may not
 *
 * Because it names its source in the same breath. *"Robbery reported by Prothom
 * Alo, 2 days ago"* is a checkable fact about a published article, and `sources`
 * carries the link so the reader can check it. A cluster withholds the category
 * because its trustworthiness comes from anonymous accounts agreeing, and
 * attaching "robbery" to an anonymous aggregate would be the product
 * characterising a place.
 *
 * **The practical consequence for any screen rendering this: show `statement` as
 * given.** Do not compose your own sentence from `category` — a sentence without
 * the attribution is the product asserting that a crime happened, which it has no
 * standing to do, and it is the one thing the backend's database CHECK exists to
 * make impossible server-side.
 */

import type { CrimeCategory } from './crime';

/**
 * The two tiers a client can be served.
 *
 * - `published`: one publisher. Weighted at 0.35.
 * - `corroborated`: two or more *independent* publishers, where independence
 *   collapses two mastheads of one house into one owner. Weighted at 0.7.
 *
 * `expired` and `removed` exist in the database and are never served, so there is
 * no branch for them here.
 *
 * Note this is **derived on read** from the publisher count rather than stored, so
 * it reflects today's independence policy rather than the policy in force on the
 * day the row was written.
 */
export type NewsCrimeStatus = 'published' | 'corroborated';

/**
 * One citation. The substance of this surface, not decoration: an attributed
 * claim the reader cannot check is just a claim.
 */
export interface NewsCrimeSource {
  /** Stable publisher id, e.g. `prothom_alo`. */
  sourceId: string;
  /** The article. Open it externally; never render it inline. */
  url: string;
  publishedAt: string | null;
  title: string | null;
}

/**
 * `NewsCrimeIncident` in Python. A decaying, located, attributed crime report.
 *
 * Field names are camelCase here and snake_case on the wire; `risk.service.ts`
 * converts in one place so no screen sees `source_count`.
 */
export interface NewsCrimeIncident {
  incidentId: string;

  /**
   * The same eight values a user picks when filing their own report, so the map
   * legend, the filter chips and the marker colours are shared rather than
   * duplicated.
   *
   * Use it for **colour and iconography only**. The sentence is `statement`.
   */
  category: CrimeCategory;

  status: NewsCrimeStatus;

  lat: number;
  lon: number;
  radiusM: number;

  /**
   * Severity decayed to the instant of the request, 0-100.
   *
   * The undecayed value never leaves the backend. A five-day half-life puts an
   * incident below the serve threshold about eighteen days after it was reported,
   * which is what stops this layer becoming a permanent judgement on a street.
   */
  severityNow: number;

  /** When the reported incident happened, as the article dates it. */
  observedAt: string;

  /**
   * The published sentence, from `app/policy/attribution.py`. Names the publisher
   * and the recency: *"Robbery reported by Prothom Alo, 2 days ago"*.
   *
   * **Render as-is.** See the note at the top of this file — rebuilding it from
   * `category` drops the attribution, which is the entire basis on which this
   * surface is allowed to use crime vocabulary.
   */
  statement: string;

  /** Independent publishers. 1 means `published`, 2+ means `corroborated`. */
  sourceCount: number;

  /** The citations, so the reader can check the claim. */
  sources: NewsCrimeSource[];
}
