# GD formats — what D08 generates into

**Collected:** 10 October 2026 · **For:** D08, the Casework Agent

**Status:** both routes confirmed. Route 1 from the official DMP form, transcribed below. Route 2
from the live portal plus screenshots taken on the device on 10 Oct 2026. See **Gaps** at the
bottom for the few things still unverified; none of them block the build.

Meridian produces a **draft**. A person reviews, approves and files it. We never file on anyone's
behalf, and nothing here requires a police partnership, an API, or anyone's credentials.

---

## Route 1 — the written application handed to the duty officer

This is the legally primary route and the one our PDF export must satisfy.

**Why it is open to us.** The Police Act 1861 obliges every officer-in-charge to keep a general
diary and record complaints. No law prescribes a format for the *application* — a 2008 Daily Star
legal Q&A states it may be in any form, "including a computer-composed one." DMP issued a standard
form in 2016 precisely because there was none and citizens were being charged Tk 200–250 for a
blank sheet. Filing is free.

**The transaction.** Two copies, both signed by the applicant. The duty officer enters it in the
register, signs and returns one copy with the GD number. That returned copy is the receipt and the
thing worth keeping — it is what our "GD number (if filed)" field should capture.

### The official DMP form, transcribed

Source: `docs/reference/dmp-gd-form.pdf` (dmp.gov.bd, 2016). A scanned image with no text layer;
transcribed by reading the render. **Spellings are the form's own** — it writes সাধারণ ডাইরী and
ডাইরীভূক্ত, not the ডায়েরি spelling used in news coverage. Keep the form's spelling in the PDF
export and the news spelling in our own UI copy.

```
                         [ DMP crest ]
                     ঢাকা মেট্রোপলিটন পুলিশ

বরাবর
        অফিসার ইনচার্জ
        ........................ থানা, ঢাকা মেট্রোপলিটন পুলিশ, ঢাকা।

বিষয় ঃ  সাধারণ ডাইরী করার আবেদন প্রসঙ্গে।

জনাব
        আমি নিম্নস্বাক্ষরকারী (নাম)..................... জাতীয় পরিচয় পত্র নং.........
        ..................... পিতা ঃ .....................................
মাতা ঃ .....................................
ঠিকানা (স্থায়ী) .................................................
        .................................................
ঠিকানা (বর্তমান) ...............................................
        .................................................

আমি এই মর্মে জানাচ্ছি যে,

        << the narrative — roughly two thirds of the page is blank here >>

        অতএব, মহোদয় উপরোক্ত বিষয়টি আপনার থানায় সাধারণ ডাইরীভূক্ত করতে মর্জি হয়।

তারিখ ঃ                                  বিনীত নিবেদক
                                         স্বাক্ষর.............................
                                         নাম .................................
                                         মোবাইল..............................
                                         ই- মেইল (যদি থাকে)..................

        (বিঃদ্রঃ প্রয়োজনে অতিরিক্ত পাতা ব্যবহার করা যেতে পারে)
```

### What this tells D08

- **The form is a frame, not a questionnaire.** Everything above `আমি এই মর্মে জানাচ্ছি যে,` is
  identity; everything below is the closing. The entire incident is one free-text narrative in the
  middle. **That blank middle is the whole product.** Thana routing fills one line at the top, the
  LLM fills the middle, and the rest is constants.
- **Fields we must collect and do not have today:** জাতীয় পরিচয় পত্র নং (NID), পিতা, মাতা, and
  ঠিকানা (স্থায়ী) and ঠিকানা (বর্তমান) as two separate addresses. Our user profile has none of
  these. They are *not* ours to guess — they belong in a one-time "GD profile" the user fills in.
- **`তারিখ` is the filing date, not the incident date.** The incident date goes in the narrative.
- **The narrative must carry its own date, time and place** — the frame has no field for them.
- `(বিঃদ্রঃ প্রয়োজনে অতিরিক্ত পাতা ব্যবহার করা যেতে পারে)` — extra pages are explicitly allowed,
  so the PDF may run to two pages without looking irregular.
- **The signature line is handwritten.** Our export leaves it blank; the user signs the print.

### The narrative's stock phrasing

Consistent across the lawyer-written samples, and what a native reviewer will check for:

- Open with `বিনীত নিবেদন এই যে,` then the applicant's name, father's name and address.
- Then the incident: date, time, place, what happened, in plain declarative order.
- **Named suspects:** name, father's name and full address. **Unknown suspects:** a description
  sufficient to identify them. This is the one place a wrong detail does real damage — it must be
  the user's words, never the model's inference.
- Close with `অতএব, জনাবের নিকট বিনীত নিবেদন`, or the DMP form's own
  `অতএব, মহোদয় উপরোক্ত বিষয়টি আপনার থানায় সাধারণ ডাইরীভূক্ত করতে মর্জি হয়।`
- Sign-off label `নিবেদক` or `বিনীত নিবেদক`.

### A direct bearing on D07's output

A GD application is a statement by a citizen, and a false complaint is punishable. **Nothing the
vision model proposed may enter the narrative as fact.** The category the user confirmed in D07 may
select the template; the cue outputs may not become sentences. If the photo is attached, it is
attached as an attachment, described as a photograph the complainant took.

---

## Route 2 — the Online GD app and portal

`gd.police.gov.bd` and the **Online GD** Android app (`com.opus_bd.lostandfound`, built by Opus BD).
One account serves both. **No public API, no developer portal, no partner process** — the only API
mentioned anywhere is the internal one to CDMS++, the police records system. We integrate by
**giving the user text to paste**, and nothing more.

### Portal structure (read off the live site, 10 Oct 2026)

Menu: `হোম` · `যোগাযোগ` · `ব্যবহার নির্দেশিকা` (submenu: `ভিডিও নির্দেশিকা`, `পিডিএফ নির্দেশিকা`,
`অ্যাপস্‌ ডাইনলোড করুন`) · `প্রবেশ করুন(লগইন)` · `রেজিস্ট্রেশন` · `ENG`.

### Registration — once, and entirely the user's own

`জাতীয় পরিচয়পত্র নম্বর` plus date of birth · `বর্তমান ঠিকানা` · `লাইভ ছবি`, a live selfie taken in
the app · `সচল মোবাইল`, which becomes the username and **must be registered in the user's own name**
for the OTP to arrive · `ইমেল` (optional) · `পাসওয়ার্ড` · SMS OTP.

Then a one-time profile step: a **digital signature drawn with a finger**, and the mobile operator.

**We touch none of this.** No NID, no OTP, no credentials, ever.

### The path we use: `অন্যান্য আবেদন` → `সাধারন ডায়রী করার আবেদন`

**Confirmed from the app on 10 Oct 2026.** Under `অন্যান্য আবেদন` the first field is
`আবেদনের ধরণ *`, a dropdown with five options:

| Option | For |
|---|---|
| যানবাহন সড়ক দুর্ঘটনায় পতিত হইয়া ক্ষতিগ্রস্থ হওয়া সংক্রান্তে সাধারণ ডায়রীর আবেদন | road accident damage |
| অনলাইন বিজনেস সংক্রান্ত | online business |
| আগুন লেগে ক্ষতি হওয়া সংক্রান্তে সাধারণ ডাইরীর আবেদন | fire damage |
| প্রাকৃতিক দুর্যোগে ক্ষতি হওয়া সংক্রান্তে সাধারণ ডাইরী করার আবেদন | natural disaster damage |
| **সাধারন ডায়রী করার আবেদন** | **the catch-all — this is ours** |

Choosing the catch-all gives **exactly two fields**, then `পরবর্তী`:

- `আবেদনের ধরণ *` — already filled by the dropdown
- `বিবরণ *` — **one large free-text area.** Placeholder: `সাধারন ডায়রী আবেদন`

**This is the single most important finding for D08.** The online path wants the same thing the
paper form's blank middle wants: one formal Bangla narrative. **We generate one artefact, not two.**

The other four options and the lost-document flows open long structured forms which then build a GD
draft for you. **Out of scope** — those are document-replacement workflows, not incident reports,
and competing with a form the police already generate buys us nothing.

### The submission form (lost-and-found flow, for reference only)

Documented fields:

- `অভিযোগের ধরন` — complaint type
- `জেলা` / `থানা` — **district and police station. This is what our thana lookup feeds.**
- `ঘটনার সময় ও স্থান` — time and place, entered separately: district, upazila, union or ward, then
  the specific place
- a detailed free-text description of the incident
- `বর্তমান ঠিকানা`
- identity: full name, father's name, mobile number
- attachments: `অভিযোগ সম্পর্কিত কোন ডকুমেন্ট` — documents related to the complaint; in the app, a
  photo or a scan
- a red asterisk marks required fields
- `সাবমিট` / `এডিট`

Submission: a preview, then **Final Submit**, then an OTP to the registered mobile. **No editing
after submission.** A rejected GD must be refiled from scratch.

Returned: a reference number, a downloadable PDF (`Application Print` from the dashboard) and a QR
code for retrieving digital or printed copies later. Status shows under *Pending* or *Accepted*
applications, and police may follow up by phone or SMS.

### Documented categories elsewhere in the app

The published guides list the lost-and-found set: lost documents (NID, passport, driving licence,
certificates), lost mobile phone with IMEI, lost vehicle, and others such as SIM card and police
clearance. Each opens its own long structured form. We use none of them — see the
`অন্যান্য আবেদন` path above.

### Coverage is partial, and this matters for the demo

Online GD was lost-and-found only until a pilot at Sylhet Metropolitan and Chandpur district on
**15 April 2025**. Police HQ then reported all-types GD at **457 thanas** across the Dhaka,
Mymensingh, Sylhet, Chattogram, Rajshahi and Rangpur ranges plus their metropolitan units, with
Khulna and Barishal (122 thanas) following. **No source confirms complete national coverage.** DMP's
own commissioner said in 2024 that GDs which cannot be filed online are filed manually.

**Check which range the demo coordinates fall in before leaning on route 2.**

### The limit that decides the architecture

**A cognizable offence cannot be closed online.** Where the complaint needs a criminal case, the
applicant must appear at the thana with a printed copy or the complaint code. Cognizable covers
assault, robbery, theft and burglary — *every category D07's vision pipeline proposes*. So the
physical step exists no matter what we build, and **route 1 is the primary path, not the fallback.**

Help line for the portal: **01320001428**, 24/7.

---

## Route 3 — where else this report can go

Shown as a card keyed off the report category. Numbers from police.gov.bd unless noted.

| Channel | Number | For |
|---|---|---|
| National Emergency Service **999** | 999 | In progress, or anything needing a unit now. Toll-free, 24/7 |
| Violence against women and children | 109 | The national VAW&C helpline |
| Police Cyber Support for Women (PCSW) | 01320-000888 | Cyber-harassment, blackmail, image abuse. Verify on police.gov.bd before shipping it |
| CID Cyber Police Centre | 01320010148 | Cybercrime generally |
| Online GD help line | 01320001428 | Registration and submission problems |

**Station coordinates.** `dmp.gov.bd/find-your-local-police/` lists 49 DMP thanas with addresses
and contacts, and 42 of them carry a Google Maps embed. The embed's `pb` parameter holds only the
map *centre* — often just "Dhaka" at those zoom levels — but fetching the embed URL resolves the
place marker, which is the station. That is where `police_stations.csv`'s corrected Dhaka
coordinates came from; see ADR 0007, addendum 2.

`chr.police.gov.bd`, the Citizen Help Request portal, also handles non-urgent cases, reportedly
mostly in Dhaka, with categories including lost documents, snatching and tenant or servant
verification. Not yet inspected.

---

## Gaps

**Closed 10 Oct 2026 by screenshots from the device:** the `অন্যান্য আবেদন` path and its two
fields. That was the one gap that mattered.

Still open, none of them blocking:

1. **Attachment limits** — file types, size, count. Unstated everywhere, and the `অন্যান্য আবেদন`
   path shows **no attachment control at all**, which is why the evidence photo goes to the thana on
   paper rather than through route 2.
2. **The official PDF guide** behind `পিডিএফ নির্দেশিকা`. The link is on the portal but was not
   reachable from here.
3. **Whether the demo thana is covered** by the all-types rollout.
4. **District GD forms outside DMP.** We transcribed Dhaka Metropolitan's. A district thana's form
   may differ, though the lawyer guidance is that any written form is acceptable.
5. **What the police system's own Bangla looks like.** A submitted GD's `Application Print` PDF
   would be the ideal target for our wording. Not needed to build, useful to compare against.

If any of this is ever captured from a *real* filed GD, the PDF carries the filer's NID, address and
phone. **Cover those, or use a throwaway lost-item GD.**

---

## Sources

Official: [DMP GD form PDF](https://dmp.gov.bd/wp-content/uploads/2016/10/GD-Form.pdf) ·
[gd.police.gov.bd](https://gd.police.gov.bd/) ·
[Bangladesh Police hotlines](https://www.police.gov.bd/en/hot_line_number) ·
[PCSW](https://www.police.gov.bd/en/police_cyber_support_for_women)

Research and reporting:
[ecoi.net country research on GDs, 2023 to June 2025](https://www.ecoi.net/en/document/2128304.html) ·
[Daily Star, DMP launches new GD format](https://www.thedailystar.net/node/1259191) ·
[Daily Star 2008, no prescribed format](https://archive.thedailystar.net/law/2008/07/02/blues.htm) ·
[UNB, all-types online GD in Rajshahi and Rangpur](https://unb.com.bd/category/Bangladesh/online-gd-services-now-available-in-all-districts-of-rajshahi-and-rangpur-divisions/163843) ·
[Dhaka Tribune, Sylhet Range rollout](https://www.dhakatribune.com/bangladesh/government-affairs/382782/online-gd-service-launched-across-sylhet-range) ·
[TBS, DMP commissioner on app glitches](https://www.tbsnews.net/node/855241)

Guides, third-party and unofficial:
[lawhelpbd, GD with samples](https://bangla.lawhelpbd.com/ফৌজদারী-কার্যবিধি/জিডি/) ·
[policeclearanceonlinebd, 2026 walkthrough](https://policeclearanceonlinebd.com/how-to-file-online-gd-in-bangladesh/) ·
[totthoalo](https://www.totthoalo.com/gd-online-police/) ·
[tricksboss](https://tricksboss.com/gd-form-bangladesh/)
