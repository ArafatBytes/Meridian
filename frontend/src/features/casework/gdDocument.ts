/**
 * The printed General Diary application. D08, ADR 0007.
 *
 * Built from the official DMP form — `docs/reference/dmp-gd-form.pdf`,
 * transcribed in `docs/reference/gd-formats.md`. The form is a frame around one
 * blank space: identity above, a fixed closing below, and the narrative in the
 * middle. Everything here except the narrative is a constant.
 *
 * **The Bengali-font trap, avoided rather than solved.** The usual way to lose a
 * day on this task is to generate the PDF server-side, discover the base PDF
 * fonts have no Bengali glyphs, and spend the evening embedding one and fighting
 * conjunct shaping. We print through `expo-print`, which renders this HTML with
 * Android's own text stack — the same one already drawing Bangla everywhere else
 * in the app. No font to embed, no shaping engine, no server dependency.
 * The one thing it does assume is a device with Bengali fonts, which any phone
 * in Bangladesh has.
 *
 * Spelling note: the form writes সাধারণ ডাইরী and ডাইরীভূক্ত. News coverage and
 * our own UI use ডায়েরি. The form's spelling wins on the form.
 */
import type { GdDraft, GdProfile } from '../../services/casework.service';

/*
 * A note on `ঃ`.
 *
 * It is visarga (U+0983), a *combining* mark, not a colon. Written with a space
 * in front — `তারিখ ঃ` — it has no base character to attach to, and the font
 * draws a dotted circle placeholder in front of it to say so. The scanned DMP
 * form appears to have the space because it was typed on a machine that did not
 * care; correct Bangla joins it to the preceding letter.
 *
 * The form itself mostly solves this by using no visarga at all —
 * `ঠিকানা (স্থায়ী)`, `নাম`, `মোবাইল` are bare labels followed by a dotted
 * line. We follow the form. Where it does use one — `বিষয়`, `পিতা`, `মাতা` —
 * it attaches directly to the letter.
 */

/** A blank the user fills in by hand, rather than something we invented. */
const BLANK = '<span class="blank">&nbsp;</span>';

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function field(value: string | null | undefined): string {
  const text = (value ?? '').trim();
  return text ? escapeHtml(text) : BLANK;
}

function banglaDate(date: Date): string {
  const digits = '০১২৩৪৫৬৭৮৯';
  const dd = String(date.getDate()).padStart(2, '0');
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const yyyy = String(date.getFullYear());
  return `${dd}/${mm}/${yyyy}`.replace(/\d/g, d => digits[Number(d)]);
}

/**
 * District names in Bangla, for the line the application is addressed on.
 *
 * `police_stations.csv` holds English only. Station names stay as they are —
 * inventing Bangla spellings for 606 of them is the same unverified-data
 * mistake that had Motijheel 14 km from Motijheel — but the district is one
 * word per application and worth getting right, because it is the line a duty
 * officer reads first. Anything not listed falls back to the English name,
 * which is legible and is not wrong.
 */
const DISTRICT_BN: Record<string, string> = {
  Dhaka: 'ঢাকা',
  Gazipur: 'গাজীপুর',
  Narayanganj: 'নারায়ণগঞ্জ',
  Chattogram: 'চট্টগ্রাম',
  Chittagong: 'চট্টগ্রাম',
  Khulna: 'খুলনা',
  Rajshahi: 'রাজশাহী',
  Sylhet: 'সিলেট',
  Barishal: 'বরিশাল',
  Barisal: 'বরিশাল',
  Rangpur: 'রংপুর',
  Mymensingh: 'ময়মনসিংহ',
};

export interface GdDocumentInput {
  draft: GdDraft;
  profile: GdProfile;
}

export function buildGdHtml({ draft, profile }: GdDocumentInput): string {
  const narrative = escapeHtml(draft.narrative_bn).replace(/\n/g, '<br/>');
  const thana = field(draft.thana_name.replace(/\s*Police Station\s*$/i, ''));
  const districtEn = (draft.thana_district ?? '').trim();
  const district = districtEn
    ? escapeHtml(DISTRICT_BN[districtEn] ?? districtEn)
    : BLANK;

  return `<!doctype html>
<html lang="bn">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>সাধারণ ডাইরী করার আবেদন</title>
<style>
  @page { size: A4; margin: 15mm 15mm 14mm; }

  /* Bengali needs the generous line box; 1.75 is as tight as this script
     goes before matras start touching the line above. The whole reason the
     first version ran to two pages for a three-line statement was 2.0 here
     plus a 150pt reserved block below. */
  body {
    font-family: 'Noto Sans Bengali', 'SolaimanLipi', 'Kalpurush', 'Nirmala UI', sans-serif;
    font-size: 12.5pt; line-height: 1.75; color: #000; margin: 0;
  }

  .masthead { text-align: center; margin-bottom: 14pt; }
  .masthead .force { font-size: 15pt; font-weight: 700; letter-spacing: 0.5pt; }
  .masthead .rule { border-bottom: 1.2pt solid #000; width: 46%; margin: 5pt auto 0; }

  .row { margin-bottom: 6pt; }
  .indent { margin-left: 26pt; }
  .addressee { margin-bottom: 10pt; }

  .subject { margin: 12pt 0; }
  .subject b { font-weight: 700; }

  /* The identity block. A definition-list grid keeps the labels in a column
     and stops a long address shunting the next label onto its own line, which
     is what made the printed copy look broken. */
  /* The form runs the identity details as one sentence — name, NID, father,
     mother — and puts each address on its own line. Keep that: a label column
     reads like a database record, and this is a letter. */
  .ident { margin: 0 0 4pt 26pt; }
  .ident .flow { margin: 0; text-align: justify; overflow-wrap: anywhere; }
  .addr { margin-bottom: 4pt; overflow-wrap: anywhere; }

  .blank {
    display: inline-block; min-width: 120pt;
    border-bottom: 1px dotted #000; vertical-align: baseline;
  }

  .lead { margin: 12pt 0 6pt; }
  .narrative {
    text-align: justify; text-justify: inter-word;
    min-height: 90pt; margin-bottom: 16pt;
  }

  /* Closing, signature and note travel together. Splitting a signature block
     across a page break is the one thing that makes a printed application look
     like it was produced by accident. */
  .tail { page-break-inside: avoid; break-inside: avoid; }
  .closing { margin: 0 0 14pt 26pt; }

  .signoff { width: 100%; border-collapse: collapse; }
  .signoff td { vertical-align: top; padding: 0; }
  .signoff .left { width: 42%; white-space: nowrap; }
  .signoff .right { width: 58%; }
  .signoff .right .line { display: flex; gap: 5pt; margin-bottom: 4pt; }
  .signoff .right .k { white-space: nowrap; }
  .signoff .right .v { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .heading { font-weight: 700; margin-bottom: 8pt; }
  .sigline {
    display: inline-block; min-width: 140pt;
    border-bottom: 1px solid #000; height: 16pt;
  }

  .note { margin-top: 14pt; font-size: 10pt; }
  .footer {
    margin-top: 12pt; padding-top: 5pt; border-top: 0.6pt solid #bbb;
    font-size: 8pt; color: #555; line-height: 1.45;
  }
</style>
</head>
<body>

<div class="masthead">
  <div class="force">বাংলাদেশ পুলিশ</div>
  <div class="rule"></div>
</div>

<div class="addressee">
  <div class="row">বরাবর</div>
  <div class="row indent">অফিসার ইনচার্জ</div>
  <div class="row indent">${thana} থানা, ${district}।</div>
</div>

<div class="subject"><b>বিষয়ঃ</b> সাধারণ ডাইরী করার আবেদন প্রসঙ্গে।</div>

<div class="row">জনাব</div>

<div class="ident">
  <p class="flow">
    আমি নিম্নস্বাক্ষরকারী (নাম) ${field(profile.full_name)},
    জাতীয় পরিচয় পত্র নং ${field(profile.gd_nid)},
    পিতাঃ ${field(profile.gd_father_name)},
    মাতাঃ ${field(profile.gd_mother_name)}।
  </p>
</div>

<div class="row addr">ঠিকানা (স্থায়ী) ${field(profile.gd_permanent_address)}</div>
<div class="row addr">ঠিকানা (বর্তমান) ${field(profile.gd_present_address)}</div>

<div class="lead">আমি এই মর্মে জানাচ্ছি যে,</div>

<div class="narrative">${narrative}</div>

<div class="tail">
  <div class="closing">
    অতএব, মহোদয় উপরোক্ত বিষয়টি আপনার থানায় সাধারণ ডাইরীভূক্ত করতে মর্জি হয়।
  </div>

  <table class="signoff">
    <tr>
      <td class="left">তারিখঃ ${banglaDate(new Date())}</td>
      <td class="right">
        <div class="heading">বিনীত নিবেদক</div>
        <div class="line"><span class="k">স্বাক্ষর</span><span class="v"><span class="sigline">&nbsp;</span></span></div>
        <div class="line"><span class="k">নাম</span><span class="v">${field(profile.full_name)}</span></div>
        <div class="line"><span class="k">মোবাইল</span><span class="v">${field(profile.phone)}</span></div>
        <div class="line"><span class="k">ই-মেইল (যদি থাকে)</span><span class="v">${field(profile.email)}</span></div>
      </td>
    </tr>
  </table>

  <div class="note">(বিঃদ্রঃ প্রয়োজনে অতিরিক্ত পাতা ব্যবহার করা যেতে পারে)</div>

  <div class="footer">
    খসড়াটি Meridian অ্যাপের সহায়তায় প্রস্তুত এবং আবেদনকারী কর্তৃক পঠিত ও অনুমোদিত।
    আবেদনকারীর স্বাক্ষর ব্যতীত এই আবেদন গ্রহণযোগ্য নয়।
  </div>
</div>

</body>
</html>`;
}

/**
 * What goes on the clipboard for the police's own app.
 *
 * The narrative alone, unchanged. The Online GD path
 * `অন্যান্য আবেদন → সাধারন ডায়রী করার আবেদন` has exactly two fields: the type,
 * which the user picks, and one `বিবরণ` box, which takes this.
 */
export function narrativeForOnlineGd(draft: GdDraft): string {
  return draft.narrative_bn.trim();
}
