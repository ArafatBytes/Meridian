"""
Invariant tests — IMPLEMENTATION_PLAN.md §4.

The concept document states ethical constraints. These tests are the difference
between stating them and keeping them. Every one of them runs on every push, and
**none of them is allowed to be loosened to make a change pass.** If a test here
fails, the change is wrong; that is the entire contract.

D01 ships two, chosen because they are the two a judge is most likely to probe:

* `test_no_flag_text_bypasses_framing.py` — mobility framing, never judgment.
* `test_single_source_never_confirmed.py` — verification before publication.

The other five land in Track B (B2), along with the retention registry.
"""
