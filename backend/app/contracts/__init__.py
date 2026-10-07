"""
Shared contracts — the shapes every subsystem agrees on.

These modules are the narrowest part of the hourglass: agents, routing, the API
layer and the TypeScript client all describe the same objects, and they describe
them here. IMPLEMENTATION_PLAN.md §6 is the specification; this is that
specification in code.

Rules:

* **No I/O, no settings, no database, no HTTP.** A contract that imports a
  service cannot be imported by that service's tests.
* **Mirrored by hand in `frontend/src/types/contracts/`.** Change a shape here
  and you change it there, in the same commit.
* `mypy --strict` clean. Enforced by `backend/pyproject.toml`.
"""
