"""
python -m app.agents run live_risk            one real run, recorded in agent_runs
python -m app.agents run live_risk --dry-run  fetch and extract, write nothing
python -m app.agents export-replay            capture the offline demo's news flags
python -m app.agents promote-demo             D05: scripted promotion, for the stage
python -m app.agents promote-demo --reset     put it back, to rehearse again
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import sys
from datetime import UTC, datetime

from app.agents.live_risk import export_replay
from app.agents.promote_demo import promote_one, reset
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
        if args.command == "promote-demo":
            async with AsyncSessionLocal() as db:
                if args.reset:
                    keys = await reset(db)
                    if not keys:
                        sys.stdout.write("nothing to reset: no flag carries the demo source\n")
                        return 0
                    for key in keys:
                        sys.stdout.write(f"reset {key} to unconfirmed\n")
                    return 0

                outcome = await promote_one(db, datetime.now(UTC), dry_run=args.dry_run)

            if outcome is None:
                sys.stdout.write(
                    "no unconfirmed flag to promote. Every served flag is already "
                    "confirmed or already carries the demo source -- "
                    "`promote-demo --reset` puts one back.\n"
                )
                return 1

            verb = "would promote" if args.dry_run else (
                "PROMOTED" if outcome.promoted else "merged into"
            )
            sys.stdout.write(
                f"{verb} {outcome.event_key} -> {outcome.status} "
                f"on {outcome.source_count} independent source(s)\n"
            )
            if not args.dry_run and outcome.promoted:
                # The flag sheet is where a judge looks; say where to look.
                sys.stdout.write(
                    "Refresh the map and tap the flag: the badge is now "
                    "`Confirmed - 2 sources`, and the source strip lists "
                    "`demo_second_source` alongside the real outlet. The synthetic "
                    "source is labelled on purpose -- say so on stage.\n"
                )
            return 0

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
    promote = sub.add_parser(
        "promote-demo",
        help="D05: add a labelled synthetic second source to one unconfirmed flag, "
        "through the real Rumour Guard, so demo beat 2's promotion is repeatable",
    )
    promote.add_argument("--dry-run", action="store_true", help="say what it would do")
    promote.add_argument(
        "--reset",
        action="store_true",
        help="remove the synthetic source and return the flag to unconfirmed",
    )
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
