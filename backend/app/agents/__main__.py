"""
python -m app.agents run live_risk            one real run, recorded in agent_runs
python -m app.agents run live_risk --dry-run  fetch and extract, write nothing
python -m app.agents export-replay            capture the offline demo's news flags
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
from datetime import UTC, datetime

from app.agents.live_risk import export_replay
from app.agents.registry import agents, run_agent
from app.core.database import AsyncSessionLocal, engine


async def _main(args: argparse.Namespace) -> int:
    try:
        if args.command == "run":
            result = await run_agent(args.agent, dry_run=args.dry_run)
            if result is None:
                sys.stdout.write(f"{args.agent} is already running; nothing started\n")
                return 1
            sys.stdout.write(result.model_dump_json(indent=1) + "\n")
            return 0 if result.status != "failed" else 1
        async with AsyncSessionLocal() as db:
            count = await export_replay(db, datetime.now(UTC))
        sys.stdout.write(f"exported {count} live flag(s) to the replay fixture\n")
        return 0 if count else 1
    finally:
        await engine.dispose()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")  # Bangla headlines on a cp1252 console
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m app.agents")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one agent once")
    run.add_argument("agent", choices=sorted(agents()))
    run.add_argument("--dry-run", action="store_true", help="write nothing, not even agent_runs")
    sub.add_parser("export-replay", help="write the live flags to data/fixtures/live_replay.json")
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
