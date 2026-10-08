"""
Ingestion — fetching public news before anything interprets it. D04, source sprint S09.

    fetcher.py        the only code that touches a publisher's server
    store.py          raw_documents: what was fetched, deduplicated, and the retry queue
    sources/          one module per publisher format; SOURCES lists the live ones

Nothing downstream fetches directly. The Live Risk Agent (`app/agents/live_risk.py`)
asks a `Source` for recent articles, and the `Source` asks the `Fetcher`.
"""
