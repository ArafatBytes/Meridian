"""
A registered route must do something. ADR 0001, and the lesson of defect 56.

## Why this is an invariant and not a tidiness preference

`endpoints/auth.py` carried `# TODO: Implement login logic` for months and read
as a harmless placeholder. It was not a placeholder: `/auth/login` returned a
**signed, accepted** access token for any email, with `verify_password` imported
and never called, and every endpoint behind `get_current_user` was therefore
reachable without credentials. Nobody looked, because a stub is boring.

The three that went with it — `/users`, `/crimes`, `/tracking` — were boring in
the literal sense: every handler was a bare `pass`. That is still not harmless
in a registered route. `pass` returns `None`, and `None` against a non-optional
`response_model` raises a `ResponseValidationError`, so the API advertised
`POST /api/v1/crimes/report` and answered **500** — a failure shaped like the
caller's bug rather than ours. ADR 0001 ruled them out on top of that: every
operation they named is user-owned CRUD, which belongs on the Supabase-direct
plane under RLS, and which the client had been doing directly all along.

So the rule this file enforces is: **if it is registered, it has a body.** An
endpoint worth keeping is worth implementing, and one that is not should be
deleted rather than left advertising itself in the OpenAPI schema.

A named-files check would only ever catch the four already dealt with. This
parses every handler in `app/api/v1/endpoints/` instead, so it catches the next
one — which is the only kind of check that would have caught these.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.api.v1.api import api_router

pytestmark = pytest.mark.invariant

ENDPOINTS = Path(__file__).resolve().parent.parent.parent / "app" / "api" / "v1" / "endpoints"

# Prefixes ADR 0001 puts on the Supabase-direct plane. A router under any of
# these means the data-plane rule has been reversed without reversing the ADR.
_FORBIDDEN_PREFIXES = ("/auth", "/users", "/crimes", "/tracking")


def _is_route_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Decorated with `@router.<verb>(...)`."""
    for decorator in node.decorator_list:
        call = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(call, ast.Attribute)
            and isinstance(call.value, ast.Name)
            and call.value.id == "router"
        ):
            return True
    return False


def _body_is_empty(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """
    True when the body is nothing but a docstring and/or `pass`/`...`.

    `raise NotImplementedError` and `raise HTTPException(501)` are *not* empty:
    they are a deliberate, honest answer that a client can handle. The failure
    this file is about is a handler that silently returns nothing.
    """
    statements = list(node.body)
    if statements and isinstance(statements[0], ast.Expr):
        value = statements[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            statements = statements[1:]  # drop the docstring

    if not statements:
        return True
    return all(
        isinstance(statement, ast.Pass)
        or (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is Ellipsis
        )
        for statement in statements
    )


def _handlers() -> list[tuple[str, str, bool]]:
    """`(file, function, is_empty)` for every route handler under endpoints/."""
    found: list[tuple[str, str, bool]] = []
    for path in sorted(ENDPOINTS.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_route_handler(
                node
            ):
                found.append((path.name, node.name, _body_is_empty(node)))
    return found


def test_no_registered_endpoint_has_an_empty_body() -> None:
    stubs = [f"{file}::{name}" for file, name, empty in _handlers() if empty]
    assert stubs == [], (
        f"these handlers are registered and do nothing: {stubs}. A `pass` body "
        "returns None, which against a non-optional response_model is a 500. "
        "Implement it, answer with an explicit 501, or delete the route — see "
        "ADR 0001 and defect 56. Four endpoints of exactly this shape were "
        "deleted on 15 Oct, and one of them was handing out credentials."
    )


def test_the_parser_found_handlers_at_all() -> None:
    """
    The way this file could pass while checking nothing: the decorator shape
    changes (`@api_router.get`, a shared dependency wrapper) and `_handlers()`
    quietly returns an empty list, making the assertion above vacuous.
    """
    handlers = _handlers()
    assert len(handlers) >= 20, (
        f"only found {len(handlers)} route handlers, which is too few to be "
        "right — `_is_route_handler` has probably stopped matching the "
        "decorator spelling used in endpoints/."
    )
    assert len({file for file, _, _ in handlers}) >= 5


def test_no_router_is_mounted_on_a_supabase_direct_prefix() -> None:
    """
    ADR 0001 assigns user-owned CRUD to the client under RLS. A FastAPI router
    on one of these prefixes is that decision being reversed in code rather
    than in the ADR — and `/auth` specifically is defect 56's door.
    """
    offenders = sorted(
        {
            prefix
            for route in api_router.routes
            for prefix in _FORBIDDEN_PREFIXES
            if getattr(route, "path", "").startswith(prefix)
        }
    )
    assert offenders == [], (
        f"routers are mounted on {offenders}, which ADR 0001 puts on the "
        "Supabase-direct plane. If RLS is genuinely insufficient for one of "
        "them, that changes the ADR first."
    )


def test_the_detector_catches_the_shapes_it_is_meant_to() -> None:
    """
    Proof that the check can fail, fed the four shapes that matter.

    Everything above passes because the endpoints are clean today, which says
    nothing about whether `_body_is_empty` still works. These are the real
    bodies: `crimes.py`'s was a docstring plus `pass`, and `auth.py`'s was a
    docstring, a comment and `pass`.
    """
    module = ast.parse(
        '''
@router.get("/a")
async def bare_pass():
    pass

@router.post("/b")
async def docstring_then_pass():
    """Register a new user"""
    # TODO: Implement user registration logic
    pass

@router.get("/c")
async def ellipsis_body():
    ...

@router.get("/d")
async def real_work():
    """This one answers."""
    return {"ok": True}

@router.get("/e")
async def honest_refusal():
    raise NotImplementedError

def not_a_handler():
    pass
'''
    )
    results = {
        node.name: _body_is_empty(node)
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_route_handler(node)
    }

    assert results == {
        "bare_pass": True,
        "docstring_then_pass": True,
        "ellipsis_body": True,
        "real_work": False,
        # An explicit raise is a deliberate answer, not a silent nothing.
        "honest_refusal": False,
    }, f"the stub detector no longer classifies these correctly: {results}"

    # And the decorator test must not sweep up ordinary functions.
    assert "not_a_handler" not in results


def test_the_deleted_endpoint_and_schema_modules_stay_deleted() -> None:
    """
    Named explicitly, because re-adding one of these files is how the rule gets
    reversed by accident — each was a plausible-looking file with a plausible
    name, and three of them were pure dead weight.
    """
    schemas = ENDPOINTS.parent.parent.parent / "schemas"
    for path in (
        ENDPOINTS / "auth.py",
        ENDPOINTS / "users.py",
        ENDPOINTS / "crimes.py",
        ENDPOINTS / "tracking.py",
        schemas / "auth.py",
        schemas / "user.py",
        schemas / "crime.py",
        schemas / "tracking.py",
    ):
        assert not path.exists(), (
            f"{path.name} is back. Deleted 15 Oct under ADR 0001 (and ADR 0002 "
            "for the auth pair). A schema describing an endpoint that does not "
            "exist is the template for recreating it."
        )
