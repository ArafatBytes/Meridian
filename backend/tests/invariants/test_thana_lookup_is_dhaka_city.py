"""
Invariant: **the thana lookup names a Dhaka city station or nothing at all.**

Defect 17. `police_stations.csv` covers all of Bangladesh -- 607 rows, 560 of
them labelled `legacy — unverified` by the file itself. Two things used to read
it: `casework/thana.py`, which names the station a General Diary is addressed
to, and `sos_service`, which would email stations near an incident.

Three separate failure shapes, all closed here:

**A thana name on a signed document.** Loading all 607 rows meant a bad
coordinate could put a Sherpur station on a Dhaka GD, and co-located spelling
variants (`Gandaria`/`Gendaria`, `Bhatara`/`Vatara`) resolved to whichever row
`csv.DictReader` happened to reach first -- stable only until someone
re-exported the file.

**Five Dhaka rows whose coordinates are wrong.** Checked against the file's own
trusted rows rather than against anyone's memory of Dhaka: the row labelled
`Turag` sits 1.7 km from Rampura, `Hatirjheel` 4.4 km from Pallabi. Both are
real thanas; neither is where the file says. They stay **nameable** -- somebody
filing in Turag must be able to pick it -- and are kept out of **ranking**.

**One email address behind a boolean.** Every row shares one contact, and with
`POLICE_ROUTING_ENABLED` flipped on, an SOS anywhere in Dhaka would have emailed
that single private inbox. The flag is off permanently (DEMO_PLAN 7.2), but a
flag is one edit from being on, so the refusal is now based on the data.
"""

from __future__ import annotations

import pytest

from app.casework.thana import (
    DHAKA_CITY_DISTRICT,
    MAX_PLAUSIBLE_KM,
    UNVERIFIED_COORDS,
    _dhaka_city_rows,
    _locatable,
    all_thana_names,
    nearest_thana,
)

pytestmark = pytest.mark.invariant

# Points inside Dhaka city, with the thana a person there would expect.
_IN_DHAKA: dict[str, tuple[float, float]] = {
    "Dhanmondi 27": (23.7465, 90.3760),
    "Jatrabari crossing": (23.7104, 90.4414),
    "Motijheel": (23.7330, 90.4172),
    "Mirpur 10": (23.8069, 90.3687),
    "Uttara sector 7": (23.8700, 90.3900),
    "Old Dhaka / Sadarghat": (23.7060, 90.4080),
}

# The five Dhaka rows the file labels as unverified. Named, never ranked.
_NAMEABLE_NOT_LOCATABLE = (
    "Cantonment Police Station",
    "Turag Police Station",
    "Uttarkhan Police Station",
    "Hatirjheel Police Station",
    "Bhashantek Police Station",
)


# ---------------------------------------------------------------------------
# 1. Dhaka city, and only Dhaka city
# ---------------------------------------------------------------------------


def test_only_dhaka_city_stations_are_loaded() -> None:
    districts = {district for _, district, _, _ in _locatable()}
    assert districts == {DHAKA_CITY_DISTRICT}, (
        f"non-Dhaka districts reached the thana lookup: {districts - {DHAKA_CITY_DISTRICT}}"
    )


def test_the_dhaka_district_column_really_is_dhaka_city() -> None:
    """
    The filter is `district == "Dhaka"`, which is only correct because that value
    holds **exactly** the DMP thanas. If a re-export starts filing Savar or
    Keraniganj under `Dhaka`, the filter silently stops meaning "Dhaka city" and
    this test is the only thing that would notice.
    """
    names = {(row.get("name") or "").strip() for row in _dhaka_city_rows()}
    upazilas = {
        "Savar Police Station",
        "Keraniganj Police Station",
        "Dhamrai Police Station",
        "Nawabganj Police Station",
        "Dohar Police Station",
    }
    assert not (names & upazilas), (
        f"Dhaka-district upazila stations are now inside the city filter: "
        f"{sorted(names & upazilas)}"
    )


def test_a_dhaka_point_gets_a_station_within_walking_distance_of_sense() -> None:
    for label, (lat, lon) in _IN_DHAKA.items():
        thana = nearest_thana(lat, lon)
        assert thana is not None, f"{label} is in Dhaka but got no thana"
        assert thana.district == DHAKA_CITY_DISTRICT
        assert thana.distance_km <= MAX_PLAUSIBLE_KM, (
            f"{label} resolved to {thana.name} at {thana.distance_km} km"
        )


# ---------------------------------------------------------------------------
# 2. Outside Dhaka it refuses rather than guessing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("place", "lat", "lon"),
    [
        ("Chattogram", 22.3569, 91.7832),
        ("Sylhet", 24.8949, 91.8687),
        ("Rajshahi", 24.3745, 88.6042),
        ("Khulna", 22.8456, 89.5403),
    ],
)
def test_outside_dhaka_names_no_thana(place: str, lat: float, lon: float) -> None:
    """
    **The regression this guard exists for.** Once the list is Dhaka-only, the
    nearest station to Chattogram is a DMP thana 200 km away, and the old code
    would have returned it with a confident name and no warning. A GD addressed
    to the wrong district is not a near miss.
    """
    assert nearest_thana(lat, lon) is None, (
        f"{place} was given a Dhaka city thana; it should get none"
    )


def test_a_failed_gps_fix_names_no_thana() -> None:
    assert nearest_thana(0.0, 0.0) is None
    assert nearest_thana(90.3760, 23.7465) is None  # lat/lon swapped


# ---------------------------------------------------------------------------
# 3. Nameable is a superset of locatable, on purpose
# ---------------------------------------------------------------------------


def test_the_unverified_five_can_be_named() -> None:
    names = set(all_thana_names())
    for station in _NAMEABLE_NOT_LOCATABLE:
        assert station in names, (
            f"{station} is a real DMP thana and vanished from the picker. Being "
            "unable to place a station is no reason to stop a user naming it."
        )


def test_the_unverified_five_are_never_ranked() -> None:
    locatable = {name for name, _, _, _ in _locatable()}
    for station in _NAMEABLE_NOT_LOCATABLE:
        assert station not in locatable, (
            f"{station} has a coordinate the CSV marks '{UNVERIFIED_COORDS}' and it "
            "reached the distance ranking. Its coordinate is kilometres into "
            "another thana's area."
        )


def test_every_ranked_station_has_a_trusted_coordinate() -> None:
    """Stated against the file rather than against the hardcoded five above."""
    untrusted = {
        (row.get("name") or "").strip()
        for row in _dhaka_city_rows()
        if (row.get("coord_source") or "").strip() == UNVERIFIED_COORDS
    }
    ranked = {name for name, _, _, _ in _locatable()}
    assert not (ranked & untrusted), f"unverified coordinates in ranking: {ranked & untrusted}"


def test_nameable_is_a_superset_of_locatable() -> None:
    assert {name for name, _, _, _ in _locatable()} <= set(all_thana_names())


# ---------------------------------------------------------------------------
# 4. Duplicates: deterministic ranking, both spellings still findable
# ---------------------------------------------------------------------------


def test_exact_duplicate_rows_are_dropped() -> None:
    ranked = [name for name, _, _, _ in _locatable()]
    assert len(ranked) == len(set(ranked)), (
        f"the same station is ranked twice: "
        f"{sorted({n for n in ranked if ranked.count(n) > 1})}"
    )


@pytest.mark.parametrize(
    "variants",
    [
        ("Gandaria Police Station", "Gendaria Police Station"),
        ("Bhatara Police Station", "Vatara Police Station"),
    ],
)
def test_both_spellings_stay_in_the_picker(variants: tuple[str, str]) -> None:
    """
    The picker is searched by the name the user knows. Dropping one spelling
    makes that thana unfindable for the people who spell it that way, which is a
    worse outcome than a list with two entries for one building.
    """
    names = set(all_thana_names())
    for variant in variants:
        assert variant in names, f"{variant} disappeared from the picker"


def test_co_located_variants_rank_deterministically() -> None:
    """
    A GD is signed. The same incident must not produce `Gandaria` on one run and
    `Gendaria` on the next, which is what an unsorted first-wins loop gives once
    the file is re-exported in a different order.
    """
    first = [nearest_thana(23.699555, 90.421029) for _ in range(5)]
    assert all(t is not None for t in first)
    assert len({t.name for t in first if t}) == 1

    ranked = [name for name, _, _, _ in _locatable()]
    assert ranked == sorted(ranked), "ranking order is not sorted, so it is not stable"


# ---------------------------------------------------------------------------
# 5. The contact columns cannot be used, flag or no flag
# ---------------------------------------------------------------------------


def test_the_thana_module_never_reads_a_contact() -> None:
    """
    `Thana` carries a name, a district and a distance. If an `email` or `phone`
    field ever appears on it, something is one template change away from putting
    an unverified number in front of somebody during an emergency.
    """
    from app.casework.thana import Thana

    fields = set(Thana.__dataclass_fields__)
    assert fields == {"name", "district", "distance_km"}, (
        f"Thana grew fields: {fields}. Contact columns are placeholder data "
        "(DEMO_PLAN 7.2) and must not travel with a station."
    )


def test_the_flag_off_means_no_station_is_emailed(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    `POLICE_ROUTING_ENABLED` is the only gate, so it has to be a real one.
    """
    from app.services import sos_service as module

    monkeypatch.setattr(module.settings, "POLICE_ROUTING_ENABLED", False)
    assert module.sos_service._nearest_police_station(23.7465, 90.3760) is None


def test_the_flag_on_routes_an_sos_to_the_nearest_dhaka_thana(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The feature itself: coordinates in, one thana out, with an address.

    Ramna's own coordinate is used, so the expected answer is not a judgement
    call -- the nearest station to a station is itself.
    """
    from app.casework.thana import nearest_thana
    from app.services import sos_service as module

    monkeypatch.setattr(module.settings, "POLICE_ROUTING_ENABLED", True)
    station = module.sos_service._nearest_police_station(23.736255, 90.408996)

    assert station is not None, (
        "an SOS from central Dhaka must reach a thana. If this fails, either the "
        "flag is not being read or no Dhaka row has an email."
    )
    assert station["name"] == "Ramna Police Station"
    assert "@" in station["email"]
    assert station["distance_km"] < 0.1

    # The emailed station and the station printed on the GD are the same object
    # of knowledge, not two lookups that happen to agree today.
    assert station["name"] == nearest_thana(23.736255, 90.408996).name


def test_an_sos_from_outside_dhaka_emails_no_station(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The station list is Dhaka city. Chattogram's nearest DMP thana is 200 km
    away, and emailing it would be worse than emailing nobody -- it tells a
    station with no jurisdiction that someone 200 km away is in danger.
    """
    from app.services import sos_service as module

    monkeypatch.setattr(module.settings, "POLICE_ROUTING_ENABLED", True)
    assert module.sos_service._nearest_police_station(22.3569, 91.7832) is None


def test_only_one_station_is_ever_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Central Dhaka has six or seven thanas inside 5 km, which is what the old
    radius version would have emailed. One incident has one officer-in-charge.
    """
    from app.services import sos_service as module

    monkeypatch.setattr(module.settings, "POLICE_ROUTING_ENABLED", True)
    station = module.sos_service._nearest_police_station(23.7465, 90.3760)
    assert station is not None
    assert isinstance(station["email"], str), "one address, not a list of them"


def test_the_email_map_is_built_from_dhaka_rows_only() -> None:
    """
    Station names repeat across districts -- there is a `Kotwali Police Station`
    in Dhaka, another in Chattogram, another in Rajshahi. `nearest_thana` only
    returns Dhaka names, so a map built from all 607 rows would silently hand
    back a different district's address under a name that looked correct.
    """
    from app.casework.thana import DHAKA_CITY_DISTRICT
    from app.services.sos_service import SOSService

    service = SOSService.__new__(SOSService)
    service.police_stations = [
        {"name": "Kotwali Police Station", "district": "Chattogram", "email": "ctg@x"},
        {"name": "Kotwali Police Station", "district": DHAKA_CITY_DISTRICT, "email": "dhk@x"},
        {"name": "Ramna Police Station", "district": DHAKA_CITY_DISTRICT, "email": "ramna@x"},
        {"name": "Kotwali Police Station", "district": "Rajshahi", "email": "raj@x"},
    ]
    emails = service._build_dhaka_email_map()

    assert emails == {"Kotwali Police Station": "dhk@x", "Ramna Police Station": "ramna@x"}


def test_a_shared_contact_column_is_detected_and_reported() -> None:
    """
    It no longer refuses -- the owner's own address in every row is how police
    routing gets tested at all, and a gate the data owner cannot open is a bug,
    not a safety feature. But it must still be *visible*, because defect 31's
    failure was a stranger's address in that column with routing silently on.
    """
    from app.services.sos_service import SOSService

    service = SOSService.__new__(SOSService)
    service.police_stations = [
        {"email": "oc.ramna@example.gov.bd"},
        {"email": "oc.motijheel@example.gov.bd"},
        {"email": "oc.gulshan@example.gov.bd"},
    ]
    assert service._check_contacts_are_per_station() is True

    service.police_stations = [{"email": "one@example.com"} for _ in range(50)]
    assert service._check_contacts_are_per_station() is False


def test_a_missing_address_is_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A Dhaka thana with no email in the CSV must mean "contacts only", not an
    exception thrown while someone is holding down an SOS button.
    """
    from app.services import sos_service as module

    monkeypatch.setattr(module.settings, "POLICE_ROUTING_ENABLED", True)
    monkeypatch.setattr(module.sos_service, "_dhaka_station_emails", {})
    assert module.sos_service._nearest_police_station(23.736255, 90.408996) is None
