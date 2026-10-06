# Meridian
## Agentic Safety Navigation for Bangladesh

**Concept Document**
Hack for Humanity 2026 — The AI Collective Bangladesh
Track 3: Smart Society & Public Services

*Version 1.0 — 30 September 2026*

---

## 1. Executive Summary

Navigation in Bangladesh answers one question: what is the fastest route? It has never answered the one that matters more: is this road safe right now?

Meridian is a safety navigation platform that closes that gap. At its core is a layer of autonomous agents that continuously read the city, drawing on newspaper archives, live news, social media and published announcements, and convert scattered public information into a live, decaying risk surface that travellers can act on before they choose a turn. On top of that surface sit safety-weighted routing, AI-assisted incident reporting, live journey monitoring and emergency SOS.

The platform then closes the loop that no navigation product addresses. After an incident, an agent drafts the formal Bangla General Diary, so incidents that would otherwise vanish become recorded data, which in turn improves the safety map for the next traveller.

**The core insight:** the information needed to keep people safe is already public. Nobody reads the city fast enough to warn anyone in time. Agents can.

---

## 2. Problem Statement

### 2.1 The decision is made blind

Every navigation app in Bangladesh optimises for speed. None surfaces risk. So millions of daily routing decisions are made with no safety information at all.

A student takes a shortcut because it saves four minutes, not knowing three muggings were reported on that road this year. A rider turns onto a street that has been on fire for twenty minutes. A family drives toward a junction blocked by a procession since morning. A woman walks home from her shift through an area where a clash broke out an hour ago.

None of them had any way to know.

### 2.2 The information already exists, but not in usable form

This is what makes the problem solvable, and what makes its persistence unacceptable.

- The muggings on that road were **reported in the newspaper**.
- The fire was **posted on social media half an hour ago**.
- The procession was **announced yesterday**.
- The clash is **being discussed right now** by people standing in it.

Every input is public. None of it is on a map. It sits scattered across archives, feeds and posts, in a form no traveller can consume in the sixty seconds before choosing a turn.

**The gap is not data availability. It is that nobody reads the city fast enough to warn anyone in time.**

### 2.3 The second failure: incidents are never recorded

When something does happen, almost nobody reports it.

Filing a General Diary requires a thana visit, hours of lost time, and a form written in formal Bangla that most citizens cannot draft unassisted. It frequently produces no visible outcome. The rational response is silence.

This creates a self-reinforcing failure:

> Incidents go unreported, so official crime data barely exists. Because the data does not exist, no safety map can be built from it. So the next traveller knows exactly as little as the last one, and the next incident goes unreported too.

Breaking this cycle requires making reporting nearly frictionless, which is an agentic problem rather than a policy one.

### 2.4 The third failure: SOS assumes capability

Existing emergency features require the victim to unlock a phone, locate an app and press a button. The circumstances in which that is impossible are precisely the circumstances that matter most.

### 2.5 Who is affected

Students, daily commuters, women travelling alone, delivery and ride-share riders and drivers, and parents sending children to school, across Dhaka, Chattogram and every district town. Tens of millions of daily journeys, currently made on guesswork.

---

## 3. Solution Overview

Meridian operates on a single principle: **public information should reach the person who needs it, before they need it.**

The system has four functions:

| Function | What it does |
|---|---|
| **Read** | Agents continuously ingest newspaper archives, live news, social media and published announcements |
| **Score** | Extracted incidents become geolocated risk flags that decay over time and vary by hour of day |
| **Route** | Routing weighs safety alongside distance, producing genuine alternatives rather than a single fastest path |
| **Act** | Live trip monitoring, emergency escalation, and assisted General Diary filing after an incident |

The result is a map that breathes. Risk appears, ages and disappears on realistic timescales rather than accumulating into a permanently red, permanently ignored overlay.

---

## 4. Methodology

![Meridian methodology: from public information to safer journeys through autonomous agents](assets/methodology.png)

---

## 5. Agent Architecture

Eight agents across three layers. Each has its own inputs, its own cadence, its own output contract, and can fail without breaking the others.

### Layer 1: Perception (reads the world)

**1. Chronic Risk Agent** *(nightly)*
Mines Bangla newspaper archives for incidents with location references. Identifies roads and junctions where crashes, muggings and assaults repeat over months. Output: persistent blackspots forming the baseline safety layer.

**2. Live Risk Agent** *(every 10–15 minutes)*
Monitors news sites and public social media pages for incidents in progress: fires, road blockades, clashes and major accidents. Short-lived, high-urgency flags.

**3. Scheduled Risk Agent** *(daily, forward-looking)*
Reads announcements of upcoming events, including processions, planned shutdowns, exam days and large gatherings. Most disruption in Bangladesh is declared before it happens, and this agent converts those announcements into tomorrow's risk map. No competing product looks forward.

**4. Geolocation Agent** *(supporting)*
Converts colloquial Bangla location references such as "Mirpur 10 golchattar", "Jatrabari chourasta" and "Shahbagh mor" into coordinates. Standard geocoders fail entirely on these. Combines an LLM with a purpose-built gazetteer of local landmark names.

### Layer 2: Verification and Scoring (decides what is true and what it means)

**5. Rumour Guard Agent**
Gatekeeps every flag. Requires multiple independent sources before a location is marked risky. Where sources are insufficient, the flag is published as unconfirmed at reduced weight, or verification is requested from users physically nearby. Uses semantic deduplication so four outlets reporting one fire collapse into a single event rather than four corroborations.

**6. Risk Scoring Engine**
Assigns each flag a severity, a spatial radius and a **decay half-life**, and modulates score by hour of day.

| Event type | Risk persistence |
|---|---|
| Road accident | ~1 hour |
| Fire | ~3–4 hours |
| Clash or disturbance | ~6–12 hours |
| Announced event | Duration of event |
| Chronic blackspot | Months |

Decay is not a detail. It is what keeps the map trustworthy. Without it, flags accumulate and users stop believing the overlay within a week.

### Layer 3: Action (does something for the user)

**7. Journey Guardian Agent**
Follows an active trip. If something looks anomalous, it first checks context such as live traffic and the user's own route history before acting. Where the anomaly persists, it sends a low-friction check-in. **Escalation occurs only when the user does not respond**, and proceeds in graded steps: repeat prompt, then notify emergency contacts with last known location, then full SOS. This design assumes the common case is harmless, such as a jam, a detour or a dead battery, while covering the case where the user cannot reach their phone.

**8. Casework Agent**
After an incident, drafts the formal General Diary in proper Bangla, attaches the report, evidence and geolocation, and identifies the correct thana. Converts a multi-hour bureaucratic process into a reviewed-and-submitted document.

---

## 6. Worked Example

A single incident, from the first post to automatic expiry.

| Time | What happens |
|---|---|
| **14:20** | A fire breaks out near Bangshal. A local news page posts about it. |
| **14:26** | Live Risk Agent detects the post. Rumour Guard finds only one source and holds the flag as unconfirmed. |
| **14:31** | Two further outlets report it. Semantic deduplication confirms these are the same event from independent sources. The flag is promoted to confirmed. |
| **14:32** | Geolocation Agent resolves "Bangshal er kachhe" to coordinates. Risk Scoring Engine assigns high severity, a 400m radius and a 3-hour half-life. |
| **14:33** | A user requesting a route through that corridor receives an alternative, with a plain-language explanation: *fire reported near Bangshal, roads likely blocked, three sources.* |
| **17:45** | Severity has decayed below threshold. The flag disappears automatically. No manual cleanup, no stale red zone. |

---

## 7. Technology Stack

**Mobile:** React Native (Expo), TypeScript, Zustand, react-native-maps, Firebase Cloud Messaging

**Backend:** FastAPI, Python 3.11+, PostgreSQL 16 with PostGIS, Redis, Celery for agent scheduling, SQLAlchemy

**AI and ML:** PyTorch; YOLOv9c, MediaPipe and CLIP for on-image crime analysis; Claude and open-source LLMs for news extraction, Bangla landmark geocoding and General Diary drafting; sentence-transformers for cross-source event deduplication

**Ingestion:** BeautifulSoup and Playwright for newspaper and social media collection

**Routing and maps:** OSRM or GraphHopper over OpenStreetMap

**Messaging:** CloudWaveBD SMS gateway (primary), Twilio (fallback)

**Infrastructure:** Docker, GitHub Actions, Supabase and Firebase Storage, Sentry

---

## 8. Data Sources

| Source | Used for | Access |
|---|---|---|
| Bangla newspaper archives | Chronic blackspot detection | Public |
| Live news sites | In-progress incidents | Public |
| Public social media pages | Breaking incidents, early signal | Public |
| Published event announcements | Forward-looking risk | Public |
| OpenStreetMap | Base map, routing graph | Open |
| User-submitted reports | Ground truth, verification | First-party |

Every external input is publicly available at no licensing cost, a material factor in the platform's viability at national scale.

---

## 9. Safety, Privacy and Ethical Design

These constraints are design requirements, not afterthoughts.

**Mobility framing, not judgment.** Events involving gatherings or processions are surfaced as mobility facts such as "road blocked", "heavy crowd" or "expect delay", never as safety or political characterisations. This preserves usefulness while avoiding both political bias and the stigmatisation of neighbourhoods.

**Verification before publication.** No single unverified post produces a flag. Falsely marking a road as dangerous is itself a harm to residents, to local businesses and to user trust.

**Decay by default.** Risk information expires. Permanent labelling of areas is explicitly rejected.

**Graded escalation.** The Journey Guardian assumes benign explanations first and escalates only on non-response, in steps.

**Data minimisation.** Location history is retained only as long as operationally necessary, local storage is encrypted, and all API communication is over HTTPS with JWT authentication.

---

## 10. Impact

**For travellers:** routing decisions become informed rather than blind, with a plain-language explanation of why a route is flagged rather than an opaque score.

**For emergency response:** the Journey Guardian covers the case a manual SOS button cannot, where the user is unable to trigger it themselves.

**For public data:** every assisted General Diary filing converts an invisible incident into a recorded one. At scale, this begins to address Bangladesh's structural absence of granular incident data.

**For institutions:** aggregated, anonymised risk patterns offer traffic authorities, city corporations and police an evidence base for identifying blackspots, derived from information that currently reaches no one.

**Suggested success metrics:**

- Time from incident occurrence to user alert (target: under 15 minutes for live events)
- Flag precision, the proportion of confirmed flags corresponding to verified real events (target: above 90%)
- False check-in rate per user per week (target: below 1)
- General Diary drafts completed and submitted
- Proportion of journeys where an alternative route was accepted

---

## 11. Implementation Roadmap

### Round 2: Prototype (1–14 October 2026)

| Dates | Deliverable |
|---|---|
| Oct 1–3 | Ingestion pipeline for newspaper and social media sources; corpus collection |
| Oct 4–7 | Geolocation Agent and Bangla landmark gazetteer *(highest technical risk)* |
| Oct 8–10 | Live Risk Agent, Rumour Guard, Risk Scoring Engine with decay |
| Oct 11–12 | Safety-weighted routing over the risk surface; map interface; explanation generation |
| Oct 13–14 | Casework Agent for General Diary drafting; demo build; submission |

**Deferred to roadmap:** Chronic Risk Agent (archive mining at scale), Journey Guardian, crowd verification loop.

### Round 3: Finale (24 October 2026)

Live demonstration, impact presentation, judges' Q&A.

### Post-hackathon

Pilot deployment in a single Dhaka zone, institutional engagement with traffic and city authorities, and expansion to Chattogram and district towns.

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| **Bangla landmark geocoding fails** (primary technical risk) | Purpose-built gazetteer seeded manually for the pilot zone; LLM fallback; unresolvable references discarded rather than misplaced |
| **False flags from rumour or misinformation** | Multi-source requirement; semantic deduplication; unconfirmed tier; crowd verification |
| **Social media access restrictions** | Ingestion abstracted behind a source-agnostic interface; news sites and user reports remain viable independently |
| **Stale risk accumulation** | Mandatory decay on every flag; no permanent labels |
| **Political or communal misreading of flags** | Mobility-only framing; no characterisation of groups or neighbourhoods |
| **Alert fatigue** | Severity thresholds tuned conservatively; explanation attached to every alert |

---

## 13. Differentiation

| Capability | Google Maps | Community crime apps | **Meridian** |
|---|---|---|---|
| Fastest route | Yes | No | Yes |
| Safety-weighted routing | No | Partial | Yes |
| Live incident ingestion from public sources | No | No | Yes |
| Forward-looking scheduled risk | No | No | Yes |
| Risk decay and time-of-day scoring | No | No | Yes |
| Source verification before flagging | No | No | Yes |
| Non-response emergency escalation | No | No | Yes |
| Assisted official incident reporting | No | No | Yes |
| Built for Bangla and local place names | No | No | Yes |

The decisive differentiator is the **closed loop**. Meridian is the only system that both consumes public incident information and generates new official records, with each filed report improving the map for the next traveller.

---

## Appendix A: Agent Summary

| # | Agent | Layer | Cadence | AI required |
|---|---|---|---|---|
| 1 | Chronic Risk | Perception | Nightly | LLM extraction |
| 2 | Live Risk | Perception | 10–15 min | LLM extraction |
| 3 | Scheduled Risk | Perception | Daily | LLM extraction |
| 4 | Geolocation | Perception | On demand | LLM and gazetteer |
| 5 | Rumour Guard | Verification | Per event | Embeddings and policy |
| 6 | Risk Scoring | Verification | Continuous | Policy engine |
| 7 | Journey Guardian | Action | Per trip | Anomaly detection |
| 8 | Casework | Action | On incident | LLM generation |
