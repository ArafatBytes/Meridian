-- ============================================================================
-- 20261008120000__raw_documents_extracted_at
-- ============================================================================
-- When the Live Risk Agent (D04) finished reading a document. Null means it has
-- been fetched and stored but not yet read by the extraction model.
--
-- Needed because extraction is allowed to find nothing. An article about the
-- budget produces zero `extracted_incidents` rows, so "has this document been
-- read?" cannot be answered from that table — and without a marker every run
-- would send the same irrelevant articles to the model again, spending a
-- free-tier quota of a few hundred requests a day on work already done.
--
-- It doubles as the retry queue: a document fetched while the model was rate
-- limited keeps `extracted_at` null and is picked up by the next run.
-- ============================================================================

alter table public.raw_documents
    add column if not exists extracted_at timestamptz;

create index if not exists idx_raw_documents_unextracted
    on public.raw_documents (fetched_at desc)
    where extracted_at is null;

comment on column public.raw_documents.extracted_at is
    'When the Live Risk Agent read this document. Null = not yet read (the retry queue).';

notify pgrst, 'reload schema';
