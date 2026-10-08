"""
The only code that fetches from a publisher. IMPLEMENTATION_PLAN.md S09.

    async with Fetcher() as fetcher:
        html = await fetcher.text("https://ekattor.tv/news-sitemap.xml")
        html = await fetcher.rendered(url, wait_for="div.details-content-items p")

Politeness is not optional here, and the reason is selfish as much as courteous:
being blocked by a publisher mid-rehearsal is a self-inflicted wound (DEMO_PLAN.md
D04). So every request goes through four rules:

* **An honest User-Agent** that names the project, rather than a browser string.
* **robots.txt is obeyed.** Fetched once per host per run. A 401/403 on robots.txt
  itself is read as "disallow everything", which is how Jamuna TV answers it and how
  Python's own `urllib.robotparser` treats it; any other 4xx means no rules.
* **One request at a time per host, at least `MIN_INTERVAL_S` apart**, or the
  host's own `Crawl-delay` if that is longer.
* **Bounded retries** with exponential backoff on 429, 5xx and network errors. A
  4xx is the publisher's answer and is not retried.

Playwright is imported lazily, inside `rendered()`, so the API process never pays for
it unless a JavaScript-rendered source is actually read.
"""

from __future__ import annotations

import asyncio
import logging
import time
from types import TracebackType
from typing import Any, Final
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

USER_AGENT: Final = (
    "MeridianBot/0.1 (+https://github.com/ArafatBytes/Meridian; "
    "public-safety navigation research, Dhaka)"
)

MIN_INTERVAL_S: Final = 3.0
"""Seconds between two requests to one host. Longer if robots.txt asks for it."""

TIMEOUT_S: Final = 20.0
RETRIES: Final = 3
RENDER_TIMEOUT_MS: Final = 30_000

_DISALLOW_ALL: Final = ("User-agent: *", "Disallow: /")


class FetchRefused(RuntimeError):
    """robots.txt disallows this URL. Not retried, and not worked around."""


def request_url(url: str) -> str:
    """
    `url` with its path percent-encoded and its fragment dropped.

    Channel 24's sitemap carries raw Bangla in the path (and a trailing space);
    Ekattor's is already encoded. `%` is kept safe so an encoded path is not encoded
    twice — both forms then come out identical, which is what `store.canonical_url`
    relies on for deduplication.
    """
    parts = urlsplit(url.strip())
    return urlunsplit(parts._replace(path=quote(parts.path, safe="/%-._~"), fragment=""))


class Fetcher:
    def __init__(self, *, min_interval_s: float = MIN_INTERVAL_S) -> None:
        self._min_interval_s = min_interval_s
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_S,
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: dict[str, float] = {}
        self._playwright: Any = None
        self._browser: Any = None

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    # -- politeness ------------------------------------------------------------

    async def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        host = parts.netloc
        if host in self._robots:
            return self._robots[host]

        parser = RobotFileParser()
        robots_url = f"{parts.scheme}://{host}/robots.txt"
        await self._wait_turn(host)
        try:
            response = await self._client.get(robots_url)
        except httpx.HTTPError as problem:
            # Unreachable robots.txt means the site is unreachable too; refusing is
            # the conservative reading and the page fetch would fail anyway.
            logger.warning(
                "robots.txt for %s unreachable (%s) — treating as disallow", host, problem
            )
            parser.parse(_DISALLOW_ALL)
        else:
            if response.status_code in (401, 403):
                parser.parse(_DISALLOW_ALL)
            elif response.status_code >= 400:
                parser.parse([])  # no robots.txt: no rules, everything allowed
            else:
                parser.parse(response.text.splitlines())
        self._robots[host] = parser
        return parser

    async def _wait_turn(self, host: str) -> None:
        """Sleep until this host's interval has passed since its last request."""
        interval = self._min_interval_s
        robots = self._robots.get(host)
        if robots is not None:
            delay = robots.crawl_delay(USER_AGENT)
            if delay:
                interval = max(interval, float(delay))
        wait = self._last_request.get(host, 0.0) + interval - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request[host] = time.monotonic()

    async def _permitted(self, url: str) -> str:
        """The encoded URL, after checking robots.txt and waiting this host's turn."""
        target = request_url(url)
        robots = await self._robots_for(target)
        if not robots.can_fetch(USER_AGENT, target):
            raise FetchRefused(f"robots.txt disallows {target}")
        await self._wait_turn(urlsplit(target).netloc)
        return target

    # -- fetching --------------------------------------------------------------

    async def text(self, url: str) -> str:
        """A page or feed as text. Raises on refusal, a 4xx, or exhausted retries."""
        target = await self._permitted(url)
        for attempt in range(1, RETRIES + 1):
            try:
                response = await self._client.get(target)
            except httpx.TransportError as problem:
                if attempt == RETRIES:
                    raise
                logger.info("fetch %s failed (%s), retry %d", target, problem, attempt)
            else:
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable or attempt == RETRIES:
                    response.raise_for_status()
                    return response.text
                logger.info("fetch %s got %d, retry %d", target, response.status_code, attempt)
            await asyncio.sleep(2.0**attempt)
            await self._wait_turn(urlsplit(target).netloc)
        raise RuntimeError("unreachable")  # the loop always returns or raises

    async def rendered(self, url: str, *, wait_for: str) -> str:
        """
        A page's HTML after its JavaScript has run, for sites that render the body
        client-side (Channel 24). Waits for `wait_for` to appear, so a page that never
        renders its article raises rather than returning an empty shell.

        One browser per `Fetcher`, started on first use. Same robots.txt and interval
        rules as `text()`; no retries, because a render is slow and the caller has a
        static fallback.
        """
        target = await self._permitted(url)
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch()
        page = await self._browser.new_page(user_agent=USER_AGENT)
        try:
            await page.goto(target, wait_until="domcontentloaded", timeout=RENDER_TIMEOUT_MS)
            await page.wait_for_selector(wait_for, timeout=RENDER_TIMEOUT_MS)
            return str(await page.content())
        finally:
            await page.close()
