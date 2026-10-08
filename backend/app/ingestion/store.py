"""
`raw_documents` — what was fetched, before anything interpreted it. S09.

Three jobs, all through the table migration `20261007120100` created in D01:

* **Deduplication.** `doc_id` is the sha256 of the canonical URL, so re-listing an
  article is a no-op. `content_hash` catches the same text under a second URL
  (syndication); that copy is skipped, because for D05's corroboration count two
  URLs carrying one report are one source, not two.
* **The retry queue.** `extracted_at` is null until the Live Risk Agent has read
  the document (migration `20261008120000`). A run that hit the model's rate limit
  leaves documents unread and the next run picks them up.
* **Provenance.** A flag's source strip links to the URL stored here.

Raw SQL through the request's `AsyncSession`, like `app/scoring/surface_db.py`, and
for the same reason: the ORM has no model for these tables and does not need one.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.risk import RawDocument
from app.ingestion.fetcher import request_url

_WHITESPACE: Final = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    """The URL a document is identified by: encoded path, no query, no fragment."""
    return request_url(url).split("?", 1)[0]


def doc_id_for(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()


def content_hash(body: str) -> str:
    """sha256 of the body with whitespace collapsed — layout changes are not new text."""
    return hashlib.sha256(_WHITESPACE.sub(" ", body).strip().encode()).hexdigest()


async def known_urls(db: AsyncSession, urls: Iterable[str]) -> set[str]:
    """Which of these (canonical) URLs are already stored. One query, not one per URL."""
    wanted = list(urls)
    if not wanted:
        return set()
    result = await db.execute(
        text("select url from public.raw_documents where url = any(:urls)"),
        {"urls": wanted},
    )
    return {row.url for row in result}


async def save(db: AsyncSession, doc: RawDocument) -> bool:
    """
    Store one document. Returns False if it was already there, by URL or by content.

    Does not commit: the caller commits per source, so one publisher's failure
    cannot roll back another's documents.
    """
    digest = content_hash(doc.body)
    duplicate = await db.execute(
        text("select 1 from public.raw_documents where content_hash = :h limit 1"),
        {"h": digest},
    )
    if duplicate.first() is not None:
        return False

    result = await db.execute(
        text(
            """
            insert into public.raw_documents
                (doc_id, source_id, url, fetched_at, published_at, language, title, body,
                 content_hash)
            values
                (:doc_id, :source_id, :url, :fetched_at, :published_at, :language, :title,
                 :body, :content_hash)
            on conflict do nothing
            """
        ),
        {
            "doc_id": doc.doc_id,
            "source_id": doc.source_id,
            "url": doc.url,
            "fetched_at": doc.fetched_at,
            "published_at": doc.published_at,
            "language": doc.language,
            "title": doc.title,
            "body": doc.body,
            "content_hash": digest,
        },
    )
    return bool(getattr(result, "rowcount", 0))


async def unextracted(db: AsyncSession, *, since: datetime, limit: int) -> list[RawDocument]:
    """Stored documents the model has not read yet, newest first: the retry queue."""
    result = await db.execute(
        text(
            """
            select doc_id, source_id, url, fetched_at, published_at, language, title, body
            from public.raw_documents
            where extracted_at is null and fetched_at >= :since
            order by fetched_at desc
            limit :limit
            """
        ),
        {"since": since, "limit": limit},
    )
    return [
        RawDocument(
            doc_id=row.doc_id,
            source_id=row.source_id,
            url=row.url,
            fetched_at=row.fetched_at,
            published_at=row.published_at,
            language=row.language,
            title=row.title,
            body=row.body,
        )
        for row in result
    ]


async def mark_extracted(db: AsyncSession, doc_id: str, at: datetime) -> None:
    await db.execute(
        text("update public.raw_documents set extracted_at = :at where doc_id = :doc_id"),
        {"at": at, "doc_id": doc_id},
    )
