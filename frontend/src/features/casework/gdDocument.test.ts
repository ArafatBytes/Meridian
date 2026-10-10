/**
 * The printed application. D08, ADR 0007.
 *
 * This is the only artefact a police station actually sees, so the things
 * worth pinning are the ones that would be embarrassing on a counter: a
 * missing detail silently rendered as nothing, the signature block split
 * across a page break, or a user's own text interpreted as markup.
 */
import { buildGdHtml, narrativeForOnlineGd } from './gdDocument';
import type { GdDraft, GdProfile } from '../../services/casework.service';

const draft: GdDraft = {
  id: 'd1',
  report_id: 'r1',
  state: 'ready_to_file',
  narrative_bn: 'বিনীত নিবেদন এই যে, গত ০৯ অক্টোবর ২০২৬ তারিখ রাত ০৯:৪০ ঘটিকায়…',
  narrative_sha256: 'a'.repeat(64),
  summary_en: 'Assaulted while walking home.',
  missing_details: [],
  thana_name: 'Sher-e-Bangla Nagar Police Station',
  thana_district: 'Dhaka',
  engine: 'gemini',
  approved_at: '2026-10-10T00:00:00Z',
  gd_number: null,
  gd_filed_at: null,
  created_at: '2026-10-10T00:00:00Z',
};

const profile: GdProfile = {
  full_name: 'নাকিব সালেহ',
  phone: '01613391990',
  gd_nid: '1234567890',
  gd_father_name: 'মহসিন রেজা',
  gd_mother_name: 'নাসরিন জাহান',
  gd_permanent_address: 'সিরাজগঞ্জ',
  gd_present_address: 'আগারগাঁও, ঢাকা',
  email: 'nakib@example.com',
  is_complete: true,
  missing_fields: [],
};

describe('buildGdHtml', () => {
  it('addresses the officer-in-charge of the named thana', () => {
    const html = buildGdHtml({ draft, profile });
    expect(html).toContain('অফিসার ইনচার্জ');
    expect(html).toContain('Sher-e-Bangla Nagar থানা');
  });

  it('writes the district in Bangla where we know it', () => {
    expect(buildGdHtml({ draft, profile })).toContain('থানা, ঢাকা।');
  });

  it('falls back to the English district rather than guessing', () => {
    const html = buildGdHtml({
      draft: { ...draft, thana_district: 'Netrokona' },
      profile,
    });
    expect(html).toContain('থানা, Netrokona।');
  });

  it('keeps the two fixed lines of the form around the narrative', () => {
    const html = buildGdHtml({ draft, profile });
    expect(html).toContain('আমি এই মর্মে জানাচ্ছি যে,');
    expect(html).toContain('সাধারণ ডাইরীভূক্ত করতে মর্জি হয়');
    expect(html).toContain(draft.narrative_bn);
  });

  it('leaves the signature line blank — we never sign for anyone', () => {
    const html = buildGdHtml({ draft, profile });
    expect(html).toContain('sigline');
    expect(html).toContain('স্বাক্ষর');
  });

  it('keeps the closing, signature and note on one page', () => {
    const html = buildGdHtml({ draft, profile });
    expect(html).toContain('page-break-inside: avoid');
  });

  it('shows a dotted blank for a detail we do not have, never an empty space', () => {
    const html = buildGdHtml({
      draft,
      profile: { ...profile, gd_nid: null, gd_father_name: '   ' },
    });
    // Two blanks for the two absent fields, plus nothing silently omitted.
    expect(html.match(/class="blank"/g)?.length).toBeGreaterThanOrEqual(2);
    expect(html).toContain('জাতীয় পরিচয় পত্র নং');
  });

  it("keeps the form's own identity sentence rather than a label column", () => {
    const html = buildGdHtml({ draft, profile });
    expect(html).toContain('আমি নিম্নস্বাক্ষরকারী (নাম)');
    expect(html).toContain('ঠিকানা (স্থায়ী)');
    expect(html).toContain('ঠিকানা (বর্তমান)');
    expect(html).toContain('ই-মেইল (যদি থাকে)');
  });

  it('never leaves a visarga without a letter to attach to', () => {
    // `ঃ` is a combining mark, not a colon. After a space or a bracket it has
    // no base, and the font draws a dotted-circle placeholder in front of it —
    // which is what `তারিখ ঃ` printed as. Labels must end in a Bengali letter.
    const html = buildGdHtml({ draft, profile });
    const body = html.slice(html.indexOf('<body>'));
    const orphaned = body.match(/[\s)\]>][ঃ]/g);
    expect(orphaned).toBeNull();
  });

  it("treats the user's own text as text, not markup", () => {
    const html = buildGdHtml({
      draft: { ...draft, narrative_bn: 'he said <b>"go"</b> & left' },
      profile,
    });
    expect(html).toContain('&lt;b&gt;');
    expect(html).not.toContain('<b>"go"</b>');
  });

  it('turns newlines in the narrative into line breaks', () => {
    const html = buildGdHtml({
      draft: { ...draft, narrative_bn: 'এক\nদুই' },
      profile,
    });
    expect(html).toContain('এক<br/>দুই');
  });
});

describe('narrativeForOnlineGd', () => {
  it('is the narrative alone, with nothing to delete before pasting', () => {
    const text = narrativeForOnlineGd({ ...draft, narrative_bn: '  বিবরণ  ' });
    expect(text).toBe('বিবরণ');
    expect(text).not.toContain('বরাবর');
    expect(text).not.toContain('বিনীত নিবেদক');
  });
});
