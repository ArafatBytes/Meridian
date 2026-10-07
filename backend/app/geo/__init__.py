"""
Geo — turning what a person types into a place on the map.

    gazetteer.py   the Dhaka-central gazetteer: load, normalise, match.
    agent.py       GeolocationAgent — gazetteer, then LLM, then discard.

**Deliberately empty of imports**, for the reason spelled out in
`app/scoring/__init__.py`: `agent.py` reaches `app.core.config`, and
re-exporting from here would make importing the package require a discoverable
`.env`. Import from the module you want.
"""
