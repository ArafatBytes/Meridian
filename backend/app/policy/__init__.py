"""
Policy — the rules that are not allowed to be a matter of judgment at the call
site.

Right now this is one module, `framing`, which owns every word of user-facing
flag text. More will arrive (the retention registry is Track B). The pattern is
the same each time: if a rule is stated in the concept document as an ethical
commitment, it lives here as code and has a test in `tests/invariants/`, rather
than living in a reviewer's memory.
"""
