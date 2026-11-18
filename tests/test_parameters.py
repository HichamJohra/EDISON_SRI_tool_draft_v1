import base64

import pytest

from edison_sri.parameters import (BY_ID, CRITERIA, ParameterError, defaults, export_bytes, from_grid, grid_rows,
                                   import_upload, validate)


def _params():
    p = defaults()
    p["mode"], p["floor_area_m2"] = "budget", 5000
    p["criteria"]["investment_budget"] = {"active": True, "value": 750000}
    p["criteria"]["kf3_min"] = {"active": True, "value": 80}
    p["criteria"]["services_excluded"] = {"active": True, "value": "EV-15; MC-25"}
    p["criteria"]["open_protocols"] = {"active": True, "value": "no"}
    return validate(p)[0]


def _upload(content: bytes) -> str:
    return "data:application/octet-stream;base64," + base64.b64encode(content).decode()


@pytest.mark.parametrize("fmt", ["json", "yaml", "xlsx"])
def test_export_then_import_round_trip(fmt):
    p = _params()
    content, name = export_bytes(p, fmt)
    back, warnings = import_upload(_upload(content), name)
    assert back == p and warnings == []
    assert back["budget_nok"] == 750000 and back["target_class"] == "D"  # derived keys for the draft optimiser


def test_grid_round_trip_and_ids_unique():
    assert len(BY_ID) == len(CRITERIA)
    p = _params()
    assert validate({**p, "criteria": from_grid(grid_rows(p))})[0] == p


def test_validation_and_legacy_format():
    p, w = validate({"mode": "TARGET", "target_class": "b", "budget_nok": "2 000 000", "extra": 1})  # format 0.1
    assert p["mode"] == "target" and p["target_class"] == "B" and p["budget_nok"] == 2_000_000
    assert any("extra" in x for x in w)
    for bad in ({"mode": "fast"}, {"criteria": {"sri_class_min": {"value": "Z"}}},
                {"criteria": {"kf1_min": {"value": 120}}}, {"criteria": {"investment_budget": {"value": "lots"}}},
                {"criteria": {"reuse_existing": {"value": "maybe"}}}, {"cost_db": "statsbygg"},
                {"floor_area_m2": 0}):
        with pytest.raises(ParameterError):
            validate(bad)


def test_rejects_unknown_file_type():
    with pytest.raises(ParameterError):
        import_upload(_upload(b"x"), "params.txt")
