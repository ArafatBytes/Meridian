-- ===========================================================================
-- D07 — the evidence photo, and what was seen in it
-- ===========================================================================
-- Report photos were analysed and then thrown away. `crime_reports` has had no
-- image column at all, so nothing survived the request that produced it. D08
-- needs these photos as General Diary attachments, which makes this a
-- dependency rather than a nicety (defect 13).
--
-- Two columns, not three. `vision_engine` was tempting as its own column, but
-- it is one field of the analysis and splitting it would let the two disagree.
--
-- Both nullable, for reasons that are all normal rather than exceptional:
--   * a report filed without a photo, which is most of them;
--   * a photo stored while every analysis tier was exhausted -- the photo is
--     still evidence, and the endpoint says so and stores it anyway;
--   * rows that predate this migration. Nothing is back-filled: there is
--     nothing to back-fill it with, because the images are gone.
--
-- No foreign key to storage. Supabase Storage objects live in a schema we do
-- not own, and a hard reference would make a bucket cleanup break report rows.
-- A missing object renders as "photo unavailable", which is the truth.
-- ===========================================================================

alter table public.crime_reports
    add column if not exists evidence_photo_path text,
    add column if not exists vision_analysis jsonb;

comment on column public.crime_reports.evidence_photo_path is
    'Object path inside the private `report-evidence` storage bucket, e.g. '
    '<user_id>/<sha256>.jpg. Null when the report has no photo. The bucket is '
    'private; the API hands out short-lived signed URLs rather than public ones, '
    'because an evidence photo of a real incident is not public data.';

comment on column public.crime_reports.vision_analysis is
    'What D07 read out of the photo: the model''s cue answers and description, '
    'the category our own code proposed from them, which tier answered '
    '(`engine`), and whether the report text corroborated it. Kept verbatim so '
    'a filed category can always be checked against what the machine actually '
    'said -- including the cases where the reporter overrode it. Null when there '
    'was no photo, or when every tier was unavailable.';


-- The only query that needs an index here is D08's: find the reports that have a
-- photo to attach. Partial, because the rows without one are the majority and
-- indexing them would be dead weight.
create index if not exists idx_crime_reports_with_evidence
    on public.crime_reports (user_id, created_at desc)
    where evidence_photo_path is not null;
