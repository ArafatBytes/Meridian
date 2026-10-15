"""
The Python contract and its hand-written TypeScript mirror must not drift. B2 / S03.

**The failure this exists for is silent on both sides.** The backend serves
`source_count`; somebody renames it to `sources_count`; the client's wire
interface still says `source_count`, so TypeScript compiles, the request
succeeds, and `wire.source_count` is `undefined`. On the zone sheet that is a
blank line where "3 sources" should be. On a crime pin it is a marker with no
colour, which is exactly defect 3 — invisible because a `Record` lookup returns
`undefined` rather than throwing. Nothing in `tsc`, `ruff`, `mypy`, `pytest` or
`jest` catches it, because each half is internally consistent.

## What is compared, and against what

Not the camelCase types in `frontend/src/types/contracts/`. Those are the
client's *domain* model and are deliberately allowed to differ -- `NewsCrimeIncident`
carries `latitude`/`longitude` on the wire and `lat`/`lon` in the app, mapped in
`toNewsCrimeIncident` with a comment saying so.

The mirrors are the **`*Wire` interfaces** in `frontend/src/services/`, which
exist precisely to name the wire shape. Those are what drift against Python, and
they are what this file reads.

## The asymmetry is deliberate

* **A client wire field with no server field is a failure.** It can only ever
  read `undefined`.
* **A server field the client does not mirror is allowed** -- the client is
  entitled to ignore `snippet` -- but it must be named in `UNMIRRORED` with a
  reason. Otherwise "the client has not caught up yet" and "the server renamed
  it and the client is now reading nothing" look identical, and the second one
  is a defect.

## Where this runs

In the `api` container, because that is where this project runs its tests.
`docker-compose.yml` mounts the client files read-only at the paths they have on
the host -- the same arrangement
`test_alert_channels_match_the_client.py` introduced for B6a, and for the same
reason: a cross-codebase test that skips on every machine is worse than no test,
because the suite still counts it as passing.
`test_the_drift_contract_is_enforced_somewhere` is what stops a missing mount
from turning this whole file into a silent no-op.

## Known gap

`IngestionStatusWire` is not checked. Its `documents_read` / `flags_published`
come out of an agent's `metrics: dict[str, float]`, so there is no Pydantic model
to compare a field list against -- the shape is asserted by the agent's own
tests instead. Worth knowing rather than worth faking: a registry entry that
compared nothing would read like coverage.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel

from app.contracts.agents import AgentHealthReport, AgentHealthState, FleetStatus
from app.contracts.community import ClusterStatusWire, CommunityCluster
from app.contracts.news_crime import CrimeCategoryWire, NewsCrimeIncident, NewsCrimeStatusWire
from app.contracts.risk import (
    FlagStatus,
    GeoResolution,
    IncidentKind,
    MobilityImpact,
    RiskFlag,
    SourceRef,
)

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent

RISK_SERVICE = Path("frontend") / "src" / "services" / "risk.service.ts"
GEO_SERVICE = Path("frontend") / "src" / "services" / "geo.service.ts"
AGENTS_SERVICE = Path("frontend") / "src" / "services" / "agents.service.ts"
TS_CONTRACTS = Path("frontend") / "src" / "types" / "contracts"


def _find_client(relative: Path) -> Path | None:
    """
    Locate a client file, or report that this environment has no frontend.

    Two environments run this suite: the repository root (`scripts/check.sh` on
    the host) and the `api` container, where `/app` is the backend and the client
    files are mounted at `/frontend/...`. `Path("/")` in the search list is what
    makes the container case work, and the mount uses the host's own path so this
    lookup is the same code in both.
    """
    for root in (BACKEND.parent, Path("/"), Path.cwd(), *Path.cwd().parents):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def _find_client_dir(relative: Path) -> Path | None:
    for root in (BACKEND.parent, Path("/"), Path.cwd(), *Path.cwd().parents):
        candidate = root / relative
        if candidate.is_dir():
            return candidate
    return None


CLIENT_RISK = _find_client(RISK_SERVICE)
CLIENT_GEO = _find_client(GEO_SERVICE)
CLIENT_AGENTS = _find_client(AGENTS_SERVICE)
CLIENT_TS_DIR = _find_client_dir(TS_CONTRACTS)

needs_services = pytest.mark.skipif(
    CLIENT_RISK is None or CLIENT_GEO is None or CLIENT_AGENTS is None,
    reason=(
        "no frontend services in this environment (expected inside the api "
        "container via docker-compose.yml's read-only mounts)"
    ),
)
needs_ts_contracts = pytest.mark.skipif(
    CLIENT_TS_DIR is None,
    reason="no frontend/src/types/contracts in this environment",
)


# ---------------------------------------------------------------------------
# Reading TypeScript, crudely and on purpose
# ---------------------------------------------------------------------------
#
# A real TS parser is not available to a pytest run and would be a dependency
# for one job. These regexes handle the two shapes the client actually uses and
# would *fail loudly* on anything else, because an interface that cannot be
# found raises rather than returning an empty set -- the one behaviour that
# matters, since a silently empty field list would turn every comparison below
# into a pass.

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_FIELD = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<optional>\?)?\s*:\s*(?P<type>.+?)[;,]?\s*$")


def _strip_comments(source: str) -> str:
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))


def _interface_body(source: str, name: str) -> str:
    """The text between the braces of `interface <name> { ... }`, brace-matched."""
    match = re.search(rf"\binterface\s+{re.escape(name)}\s*\{{", source)
    if match is None:
        raise AssertionError(
            f"no `interface {name}` found. If it was renamed, update this file's "
            "registry -- a wire interface that cannot be located is drift too."
        )
    depth = 0
    start = match.end() - 1
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1 : index]
    raise AssertionError(f"unbalanced braces reading `interface {name}`")


def _ts_fields(source: str, name: str) -> dict[str, str]:
    """
    Top-level field name -> declared type, for one interface.

    Depth-aware, so `sources: { source_id: string; ... }[]` contributes
    `sources` and not its inner fields. Nested shapes are not compared
    structurally; that is a real limit, written down rather than hidden.
    """
    body = _interface_body(_strip_comments(source), name)
    fields: dict[str, str] = {}
    depth = 0
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if depth == 0:
            match = _FIELD.match(line)
            if match:
                fields[match.group("name")] = (
                    match.group("type") + ("|undefined" if match.group("optional") else "")
                )
        depth += line.count("{") - line.count("}")
    return fields


def _ts_vocabulary(source: str, name: str) -> set[str]:
    """
    The string literals of `type X = 'a' | 'b'` or `const X = ['a','b'] as const`.

    Reads to the first `;`, which both shapes end with.
    """
    match = re.search(rf"\b(?:type|const)\s+{re.escape(name)}\b", _strip_comments(source))
    if match is None:
        raise AssertionError(f"no `type` or `const` named {name} in the client")
    tail = _strip_comments(source)[match.end() :]
    declaration = tail.split(";", 1)[0]
    return set(re.findall(r"'([^']+)'", declaration))


# ---------------------------------------------------------------------------
# Reading Pydantic
# ---------------------------------------------------------------------------


def _python_fields(model: type[BaseModel]) -> dict[str, Any]:
    return dict(model.model_fields)


def _is_nullable(annotation: Any) -> bool:
    return type(None) in get_args(annotation)


def _literal_values(annotation: Any) -> set[str]:
    if get_origin(annotation) is Literal:
        return {str(value) for value in get_args(annotation)}
    raise AssertionError(f"{annotation!r} is not a Literal")


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------
#
# Explicit pairs, never name-matching. A convention that guesses which
# TypeScript interface mirrors which model would silently cover nothing the day
# somebody renames one.


def _service_source(where: str) -> str:
    """
    The client file a registry row names.

    A lookup rather than the `risk if ... else geo` ternary this used to be,
    repeated at four call sites. B9 added a third service and the ternary would
    have silently sent `"agents"` to the geo file — comparing a contract against
    an unrelated interface, which fails with a message about the wrong thing.
    Adding a fourth service is now one line here.
    """
    files = {"risk": CLIENT_RISK, "geo": CLIENT_GEO, "agents": CLIENT_AGENTS}
    path = files.get(where)
    assert path is not None, (
        f"MODEL_PAIRS names the client file `{where}`, which is not one of "
        f"{sorted(files)}. Add it to `_service_source`, to the path constants "
        "above, and to docker-compose.yml's read-only mounts."
    )
    return path.read_text(encoding="utf-8")


def _ts_contract_source(filename: str) -> str:
    assert CLIENT_TS_DIR is not None
    return (CLIENT_TS_DIR / filename).read_text(encoding="utf-8")


# (python model, wire interface, which client file, server fields the client
#  may omit and why)
MODEL_PAIRS: tuple[tuple[type[BaseModel], str, str, dict[str, str]], ...] = (
    (RiskFlag, "RiskFlagWire", "risk", {}),
    (CommunityCluster, "CommunityClusterWire", "risk", {}),
    (NewsCrimeIncident, "NewsCrimeIncidentWire", "risk", {}),
    (
        SourceRef,
        "NewsCrimeSourceWire",
        "risk",
        {
            "snippet": (
                "the news-crime card links out rather than quoting; "
                "RiskFlagWire's inline source shape does carry it"
            )
        },
    ),
    (GeoResolution, "GeoResolutionWire", "geo", {}),
    # B9. The fleet-status pair. Worth this check even though the screen is
    # small: it renders a *state*, so a renamed field does not show as a blank
    # number — `state` reading `undefined` would land on no entry in
    # `STATE_LABELS`, and the card would say nothing about whether the system is
    # working while looking exactly like a card that does.
    (AgentHealthReport, "AgentHealthWire", "agents", {}),
    (FleetStatus, "FleetStatusWire", "agents", {}),
)

VOCABULARY_PAIRS: tuple[tuple[str, set[str], str, str], ...] = (
    ("FlagStatus", set(get_args(FlagStatus)), "risk.ts", "FlagStatus"),
    ("IncidentKind", {member.value for member in IncidentKind}, "risk.ts", "INCIDENT_KINDS"),
    (
        "MobilityImpact",
        {member.value for member in MobilityImpact},
        "risk.ts",
        "MOBILITY_IMPACTS",
    ),
    ("ClusterStatusWire", set(get_args(ClusterStatusWire)), "community.ts", "ClusterStatus"),
    (
        "NewsCrimeStatusWire",
        set(get_args(NewsCrimeStatusWire)),
        "newsCrime.ts",
        "NewsCrimeStatus",
    ),
    ("CrimeCategoryWire", set(get_args(CrimeCategoryWire)), "crime.ts", "CRIME_CATEGORIES"),
)


# ---------------------------------------------------------------------------
# A. a client field with no server field can only read `undefined`
# ---------------------------------------------------------------------------


@needs_services
@pytest.mark.parametrize(
    ("model", "interface", "where"),
    [(model, interface, where) for model, interface, where, _ in MODEL_PAIRS],
    ids=[interface for _, interface, _, _ in MODEL_PAIRS],
)
def test_every_client_wire_field_exists_on_the_server(
    model: type[BaseModel], interface: str, where: str
) -> None:
    source = _service_source(where)
    client = set(_ts_fields(source, interface))
    server = set(_python_fields(model))

    phantom = client - server
    assert not phantom, (
        f"{interface} declares {sorted(phantom)}, which {model.__name__} does not "
        "serve. TypeScript will compile and the request will succeed; the value "
        "will be `undefined` at runtime, and the screen will render a blank where "
        "a number or a sentence belongs. Either the server field was renamed and "
        "the client was not updated, or the client invented a field."
    )


# ---------------------------------------------------------------------------
# B. a server field the client ignores must be an explicit decision
# ---------------------------------------------------------------------------


@needs_services
@pytest.mark.parametrize(
    ("model", "interface", "where", "unmirrored"),
    list(MODEL_PAIRS),
    ids=[interface for _, interface, _, _ in MODEL_PAIRS],
)
def test_server_fields_are_mirrored_or_explicitly_waived(
    model: type[BaseModel], interface: str, where: str, unmirrored: dict[str, str]
) -> None:
    """
    The looser direction, with teeth.

    Ignoring a server field is legitimate -- but it has to be *stated*, because
    otherwise "the client has not caught up" is indistinguishable from "the
    server renamed this and the client now reads nothing".
    """
    source = _service_source(where)
    client = set(_ts_fields(source, interface))
    server = set(_python_fields(model))

    missing = server - client - set(unmirrored)
    assert not missing, (
        f"{model.__name__} serves {sorted(missing)} and {interface} does not "
        "mirror them. If the client genuinely does not need a field, add it to "
        "this pair's waiver in MODEL_PAIRS with the reason. If it does need it, "
        "this is the drift."
    )


@needs_services
@pytest.mark.parametrize(
    ("model", "interface", "where", "unmirrored"),
    list(MODEL_PAIRS),
    ids=[interface for _, interface, _, _ in MODEL_PAIRS],
)
def test_no_waiver_outlives_the_field_it_waives(
    model: type[BaseModel], interface: str, where: str, unmirrored: dict[str, str]
) -> None:
    """
    A waiver for a field that no longer exists is stale documentation that reads
    like a live decision. It also hides the opposite drift: if the server drops
    `snippet`, the waiver would keep claiming the client is ignoring it on
    purpose.
    """
    server = set(_python_fields(model))
    stale = set(unmirrored) - server
    assert not stale, (
        f"MODEL_PAIRS waives {sorted(stale)} for {model.__name__}, which no "
        "longer has those fields. Remove the waiver."
    )


# ---------------------------------------------------------------------------
# C. nullability
# ---------------------------------------------------------------------------


@needs_services
@pytest.mark.parametrize(
    ("model", "interface", "where"),
    [(model, interface, where) for model, interface, where, _ in MODEL_PAIRS],
    ids=[interface for _, interface, _, _ in MODEL_PAIRS],
)
def test_nullability_agrees_on_both_sides(
    model: type[BaseModel], interface: str, where: str
) -> None:
    """
    `null` arriving where the client's type promises a value is the other silent
    failure: `severity_now.toFixed(1)` throws, or worse, renders "null".

    Only fields present on both sides are compared -- the two tests above own
    the question of which fields exist.
    """
    source = _service_source(where)
    client = _ts_fields(source, interface)
    server = _python_fields(model)

    disagreements: list[str] = []
    for name in sorted(set(client) & set(server)):
        server_nullable = _is_nullable(server[name].annotation)
        client_nullable = "null" in client[name] or "undefined" in client[name]
        if server_nullable != client_nullable:
            disagreements.append(
                f"{name}: server nullable={server_nullable}, "
                f"client declares `{client[name]}`"
            )

    assert not disagreements, (
        f"{interface} and {model.__name__} disagree about what can be null:\n  "
        + "\n  ".join(disagreements)
    )


# ---------------------------------------------------------------------------
# D. vocabularies -- the defect 3 class of failure
# ---------------------------------------------------------------------------


@needs_ts_contracts
@pytest.mark.parametrize(
    ("label", "server_values", "filename", "ts_name"),
    list(VOCABULARY_PAIRS),
    ids=[label for label, _, _, _ in VOCABULARY_PAIRS],
)
def test_vocabularies_match_exactly(
    label: str, server_values: set[str], filename: str, ts_name: str
) -> None:
    """
    A value the server can send and the client has no entry for is defect 3:
    the colour lookup returns `undefined`, the pin draws with no fill, and
    nothing anywhere reports an error.

    Exact equality, both directions. A client value the server cannot send is
    dead UI code that will be maintained for ever on the belief it is reachable.
    """
    client_values = _ts_vocabulary(_ts_contract_source(filename), ts_name)

    assert client_values == server_values, (
        f"{label} and {filename}'s {ts_name} have drifted.\n"
        f"  server can send, client cannot render: {sorted(server_values - client_values)}\n"
        f"  client renders, server cannot send:   {sorted(client_values - server_values)}"
    )


@needs_ts_contracts
def test_the_geo_method_vocabulary_matches() -> None:
    """
    `GeoResolution.method` is an inline `Literal`, not a named alias, so it
    cannot go in VOCABULARY_PAIRS with the others -- and an inline literal is
    the easiest kind to extend without telling anybody.
    """
    server_values = _literal_values(GeoResolution.model_fields["method"].annotation)
    client_values = _ts_vocabulary(_ts_contract_source("geo.ts"), "GeoMethod")
    assert client_values == server_values, (
        "GeoResolution.method and geo.ts's GeoMethod have drifted: "
        f"server-only {sorted(server_values - client_values)}, "
        f"client-only {sorted(client_values - server_values)}"
    )


# ---------------------------------------------------------------------------
# E. the guard against this whole file quietly doing nothing
# ---------------------------------------------------------------------------


def test_the_drift_contract_is_enforced_somewhere() -> None:
    """
    The one test here with no `skipif`.

    Every other test in this file is skipped when the frontend is not visible,
    which is correct for a checkout without one and a trap everywhere else: a
    suite of twenty passing skips reports green. This fails instead, and names
    the mount that is missing.

    `scripts/check.sh` from the repo root and CI's `invariants` job both see the
    real tree; the `api` container sees the read-only mounts in
    `docker-compose.yml`. If none of those is true, something has been taken
    away.
    """
    missing = [
        str(relative)
        for relative, found in (
            (RISK_SERVICE, CLIENT_RISK),
            (GEO_SERVICE, CLIENT_GEO),
            (TS_CONTRACTS, CLIENT_TS_DIR),
        )
        if found is None
    ]
    assert not missing, (
        "the contract-drift check cannot see the client half, so every other "
        f"test in this file just skipped: {missing}. Inside the api container "
        "these come from docker-compose.yml's read-only mounts under "
        "`/frontend/src` — check they are still declared. On the host, run from "
        "the repository root."
    )


def test_the_registry_is_not_empty() -> None:
    """
    The other way this file could pass while checking nothing: an empty
    registry. Parametrized tests over an empty list collect zero cases and
    report success.
    """
    assert len(MODEL_PAIRS) >= 5
    assert len(VOCABULARY_PAIRS) >= 6


@needs_services
@pytest.mark.parametrize(
    ("model", "interface", "where"),
    [(model, interface, where) for model, interface, where, _ in MODEL_PAIRS],
    ids=[interface for _, interface, _, _ in MODEL_PAIRS],
)
def test_the_parser_actually_found_fields(
    model: type[BaseModel], interface: str, where: str
) -> None:
    """
    The third way to pass while checking nothing, and the likeliest: the regexes
    above stop matching -- Prettier reformats a declaration onto two lines, a
    field gains a generic with a comma in it -- and every set comparison becomes
    `set() == set()`, which is true.

    So assert the floor. These numbers are what the contracts hold today; they
    are a tripwire, not a specification, and a *shrinking* count is the signal.
    """
    source = _service_source(where)
    client = _ts_fields(source, interface)
    server = _python_fields(model)

    # The floor is the model's own size, capped at four. A flat 4 was right while
    # every contract here was wide, and B9 added `FleetStatus`, which genuinely
    # has three fields (`mode`, `checked_at`, `agents`) — a real envelope, not a
    # parse failure. Measuring against the server keeps the tripwire sharp for the
    # wide contracts and honest for the narrow one: a regex that broke and parsed
    # two out of three still trips.
    floor = min(4, len(server))
    assert len(client) >= floor, (
        f"only parsed {sorted(client)} out of {interface}, against "
        f"{len(server)} fields on {model.__name__}. The field regex has probably "
        "stopped matching the file's formatting, which would make every "
        "comparison in this file vacuously true."
    )
    assert len(server) >= 3, f"only found {sorted(server)} on {model.__name__}"


# ---------------------------------------------------------------------------
# F. the mechanism, proved against synthetic drift
# ---------------------------------------------------------------------------
#
# Everything above passes because the two halves agree today. That says nothing
# about whether the check *can* fail. These two feed it known-broken input, so
# the day somebody weakens a comparison into a tautology, these are what notice.


class _Probe(BaseModel):
    source_count: int
    statement: str
    title: str | None = None
    lat: float


def test_a_renamed_server_field_would_be_caught() -> None:
    """The real failure: the server renames, the client reads `undefined`."""
    drifted = """
    interface ProbeWire {
      sources_count: number;
      statement: string;
      title: string | null;
      lat: number;
    }
    """
    client = set(_ts_fields(drifted, "ProbeWire"))
    server = set(_python_fields(_Probe))

    assert client - server == {"sources_count"}, "the phantom-field check is broken"
    assert server - client == {"source_count"}, "the unmirrored-field check is broken"


def test_a_nullability_flip_would_be_caught() -> None:
    """`null` where the client promised a value: `.toFixed()` on null throws."""
    drifted = """
    interface ProbeWire {
      source_count: number;
      statement: string | null;
      title: string;
      lat: number;
    }
    """
    client = _ts_fields(drifted, "ProbeWire")
    server = _python_fields(_Probe)

    flipped = {
        name
        for name in set(client) & set(server)
        if _is_nullable(server[name].annotation) != ("null" in client[name])
    }
    assert flipped == {"statement", "title"}, (
        "the nullability comparison no longer detects a flip in either direction"
    )


def test_a_dropped_vocabulary_value_would_be_caught() -> None:
    """Defect 3's shape: a category the server sends and the client cannot colour."""
    client_values = _ts_vocabulary(
        "export type Probe = 'theft' | 'assault';", "Probe"
    )
    assert {"theft", "assault", "robbery"} - client_values == {"robbery"}
    assert client_values - {"theft"} == {"assault"}


def test_a_missing_interface_raises_rather_than_returning_nothing() -> None:
    """
    An interface that cannot be found must be an error, not an empty dict. An
    empty dict would make the comparisons pass, which is how a renamed wire
    interface could remove its own coverage.
    """
    with pytest.raises(AssertionError, match="no `interface GoneWire`"):
        _ts_fields("interface SomethingElse { a: string; }", "GoneWire")

    with pytest.raises(AssertionError, match="no `type` or `const` named Gone"):
        _ts_vocabulary("export type Other = 'a';", "Gone")


# ---------------------------------------------------------------------------
# F. B9's state vocabulary, which lives in a service rather than in contracts/
# ---------------------------------------------------------------------------


@needs_services
def test_the_fleet_state_vocabulary_matches_the_client() -> None:
    """
    `AgentHealthState` against `agents.service.ts`'s `AgentState`.

    Its own test rather than a `VOCABULARY_PAIRS` row, because every row in that
    table reads from `types/contracts/`, and this union is declared in the
    service beside the wire interfaces it belongs to. Adding a "it might be in
    either place" branch to the shared test would make the common case harder to
    read for one exception.

    The drift this catches is worse here than for a colour lookup. A state the
    server can send and the client has no label for lands on no entry in
    `STATE_LABELS`, and the System Status card then renders without saying
    anything about whether that part of the system is working — while looking
    exactly like a card that does. The screen falls back to `unknown` rather
    than crashing, which is the right behaviour at runtime and is also why this
    needs a test: nothing would be visibly broken.
    """
    server_values = set(get_args(AgentHealthState))
    client_values = _ts_vocabulary(_service_source("agents"), "AgentState")

    assert client_values == server_values, (
        "AgentHealthState and agents.service.ts's AgentState have drifted.\n"
        f"  server can send, client cannot label: {sorted(server_values - client_values)}\n"
        f"  client labels, server cannot send:   {sorted(client_values - server_values)}\n"
        "A new state also needs a row in `features/status/agentCatalogue.ts`'s "
        "STATE_LABELS, which `agentCatalogue.test.ts` pins at five."
    )
