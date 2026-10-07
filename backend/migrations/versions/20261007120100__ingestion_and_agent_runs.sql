-- ============================================================================
-- 20261007120100__ingestion_and_agent_runs
-- ============================================================================
-- Storage for the ingestion pipeline (D04) and for agent observability.
--
-- Created in D01, written in D04. That is deliberate: the schema is the cheap
-- part, and having it in place means D04 is a sprint about scrapers rather than
-- a sprint about scrapers *and* migrations.
--
-- Contracts: app/contracts/risk.py :: RawDocument, ExtractedIncident
--            app/contracts/agents.py :: AgentResult
-- ============================================================================


-- ============================================================================
-- raw_documents — what was fetched, before anything interpreted it
-- ============================================================================
-- Kept for three reasons, in order of how much they matter on 24 October:
--
--   1. The demo must be able to replay a known-good ingestion run with the
--      venue network unplugged. This table IS that cache. D04's gate requires
--      a successful offline run.
--   2. Re-extraction without re-fetching, when a prompt improves.
--   3. Provenance. A flag that cites a source should be traceable to the text
--      that produced it, not just to a URL that may since have changed.

create table if not exists public.raw_documents (
    -- sha256 of the canonical URL. A natural key, so re-fetching the same
    -- article is an upsert rather than a duplicate.
    doc_id       text        primary key,

    source_id    text        not null,   -- stable publisher id, e.g. 'prothom_alo'
    url          text        not null unique,
    fetched_at   timestamptz not null default now(),
    published_at timestamptz,

    language     text        not null,
    title        text        not null,
    body         text        not null,

    -- sha256 of the normalised body. Two different URLs carrying identical
    -- syndicated copy are the same document for corroboration purposes, and
    -- counting them twice is exactly the failure Rumour Guard exists to prevent.
    --
    -- Indexed, NOT unique: a unique constraint here would make a legitimate
    -- duplicate crash an ingestion run instead of being skipped. The dedup
    -- decision belongs in the agent, which can log it.
    content_hash text,

    raw_ref      text,                   -- object-store key; never inline HTML

    created_at   timestamptz not null default now(),

    constraint raw_documents_language_check
        check (language in ('bn', 'en', 'mixed'))
);

create index if not exists idx_raw_documents_source_id
    on public.raw_documents (source_id);
create index if not exists idx_raw_documents_fetched_at
    on public.raw_documents (fetched_at desc);
create index if not exists idx_raw_documents_published_at
    on public.raw_documents (published_at desc);
create index if not exists idx_raw_documents_content_hash
    on public.raw_documents (content_hash);


-- ============================================================================
-- extracted_incidents — what an LLM read out of one document
-- ============================================================================
-- One row per (document, incident). An article about three accidents produces
-- three rows. Deliberately kept separate from risk_flags: extraction is a claim
-- about a document, a flag is a published claim about the world, and the step
-- between them (geolocation, then corroboration) is allowed to reject.

create table if not exists public.extracted_incidents (
    incident_id           uuid        primary key default gen_random_uuid(),

    doc_id                text        not null
                              references public.raw_documents (doc_id) on delete cascade,

    kind                  text        not null,
    summary_en            text        not null,
    summary_bn            text,

    -- The place name exactly as the article wrote it: "মিরপুর ১০ গোলচত্বর",
    -- "Jatrabari chourasta". Stored unmodified because the Geolocation Agent's
    -- accuracy number (D03) is only meaningful against real inputs.
    location_text         text        not null,

    occurred_at           timestamptz,
    severity_hint         text,
    mobility_impact       text        not null,
    extraction_confidence double precision not null,

    source                jsonb       not null,   -- SourceRef

    -- Set once this incident has produced a flag. Null means it was extracted
    -- but not published — unresolvable location, or rejected by Rumour Guard.
    -- The null rows are the audit trail for "discarded, never guessed".
    flag_id               uuid        references public.risk_flags (flag_id) on delete set null,

    -- Why it was not published, when flag_id is null. One of a small set the
    -- agent writes: 'unresolved_location', 'duplicate', 'rejected', 'low_confidence'.
    discarded_reason      text,

    created_at            timestamptz not null default now(),

    constraint extracted_incidents_kind_check
        check (kind in (
            'road_accident', 'fire', 'clash', 'blockade', 'procession',
            'waterlogging', 'construction', 'utility_outage', 'chronic', 'other'
        )),

    constraint extracted_incidents_severity_hint_check
        check (severity_hint is null or severity_hint in ('low', 'medium', 'high')),

    constraint extracted_incidents_mobility_impact_check
        check (mobility_impact in (
            'road_blocked', 'heavy_crowd', 'delay_likely',
            'lane_closed', 'impassable', 'none'
        )),

    constraint extracted_incidents_confidence_range
        check (extraction_confidence >= 0 and extraction_confidence <= 1),

    constraint extracted_incidents_discarded_reason_check
        check (discarded_reason is null or discarded_reason in (
            'unresolved_location', 'duplicate', 'rejected', 'low_confidence'
        )),

    -- A published incident cannot also carry a discard reason. The reverse is
    -- deliberately allowed: flag_id null with no reason means "extracted, not
    -- yet decided", which is a real state between the extraction pass and the
    -- geolocation pass.
    constraint extracted_incidents_not_both_published_and_discarded
        check (flag_id is null or discarded_reason is null)
);

create index if not exists idx_extracted_incidents_doc_id
    on public.extracted_incidents (doc_id);
create index if not exists idx_extracted_incidents_flag_id
    on public.extracted_incidents (flag_id);
create index if not exists idx_extracted_incidents_created_at
    on public.extracted_incidents (created_at desc);

-- The "extracted but not published" query, which is both the discard audit and
-- the retry queue.
create index if not exists idx_extracted_incidents_unpublished
    on public.extracted_incidents (created_at desc)
    where flag_id is null;


-- ============================================================================
-- agent_runs — one row per execution of one agent
-- ============================================================================
-- Exactly app/contracts/agents.py :: AgentResult, persisted. Eight agents on
-- schedules cannot be operated without this, and it is also where the demo's
-- "time from incident to alert" number (D10 Q&A) comes from.

create table if not exists public.agent_runs (
    run_id      uuid        primary key,

    agent       text        not null,
    started_at  timestamptz not null,
    finished_at timestamptz,
    status      text        not null,

    items_in    integer     not null default 0,
    items_out   integer     not null default 0,

    errors      jsonb       not null default '[]'::jsonb,
    metrics     jsonb       not null default '{}'::jsonb,

    dry_run     boolean     not null default false,

    created_at  timestamptz not null default now(),

    -- 'running' is not in AgentResult because that contract describes a finished
    -- run. The row is written when the agent starts, so the table needs a value
    -- for the window in between — and a run stuck in 'running' is precisely what
    -- Track B's fleet health view needs to surface.
    constraint agent_runs_status_check
        check (status in ('running', 'ok', 'partial', 'failed')),

    constraint agent_runs_counts_non_negative
        check (items_in >= 0 and items_out >= 0),

    constraint agent_runs_finished_after_started
        check (finished_at is null or finished_at >= started_at),

    constraint agent_runs_finished_unless_running
        check (status = 'running' or finished_at is not null)
);

create index if not exists idx_agent_runs_agent_started
    on public.agent_runs (agent, started_at desc);
create index if not exists idx_agent_runs_status
    on public.agent_runs (status);


-- ============================================================================
-- Row Level Security
-- ============================================================================
-- All three are backend-only. Nothing here is user-owned data and nothing here
-- is reached through PostgREST.

alter table public.raw_documents       enable row level security;
alter table public.extracted_incidents enable row level security;
alter table public.agent_runs          enable row level security;

revoke all on public.raw_documents       from anon, authenticated;
revoke all on public.extracted_incidents from anon, authenticated;
revoke all on public.agent_runs          from anon, authenticated;


comment on table public.raw_documents is
    'Fetched source documents, deduplicated on URL and content hash. '
    'Also the replay cache that makes an offline demo possible (D04).';

comment on table public.extracted_incidents is
    'One LLM extraction per row. flag_id null + discarded_reason is the audit '
    'trail for incidents that were read but deliberately not published.';

comment on table public.agent_runs is
    'app/contracts/agents.py :: AgentResult, persisted. One row per agent run.';


notify pgrst, 'reload schema';
