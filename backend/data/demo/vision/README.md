# Staged demo photos — D07

The photos used in **demo beat 6**. Put them here, then capture them:

    docker exec meridian-api python -m app.agents export-vision-replay

That writes `data/fixtures/crime_vision_replay.json`, which the `replay` tier of
`LLM_CHAIN_CRIME` serves. With the network off, these exact photos then return the
exact answers that were checked in rehearsal.

**Run the capture after the final rehearsal, not before.** It freezes whatever the
models say at that moment, so an early capture preserves an answer nobody has
signed off on.

This is **not** the eval set. `data/eval/crime_vision/` measures how good the
pipeline is; this directory rehearses three specific photos. Keeping them apart
matters: capturing the eval set would let the replay tier answer its own exam.

A replayed answer carries `engine: replay` on the response and the card shows it.
