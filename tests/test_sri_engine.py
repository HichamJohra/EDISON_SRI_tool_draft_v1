import pytest

from edison_sri.requirements import requirements_at, upgrade
from edison_sri.sri_assessment import load_example
from edison_sri.sri_engine import catalogue_by_code, compute, level_sensitivity


def test_parity_with_eu_calculation_sheet():
    """The engine reproduces the EU sheet v4.5 results for the ARV example."""
    a = load_example()
    r = compute(a)
    assert r["total"] == pytest.approx(a["results"]["total"], abs=1e-12)
    for got, ref in zip(r["impact_criteria"], a["results"]["impact_criteria"].values()):
        assert got == pytest.approx(ref, abs=1e-12)
    for k, ref in a["results"]["key_functionalities"].items():
        assert r["key_functionalities"][k] == pytest.approx(ref, abs=1e-12)


def test_sensitivity_passes_through_assessed_level():
    a = load_example()
    for s in a["services"]:
        sens = level_sensitivity(a, s["code"])
        if sens:
            at = next(p for p in sens if p["level"] == s["level"])
            assert at["total"] == pytest.approx(a["results"]["total"], abs=1e-12)


def test_catalogue_has_all_method_b_services():
    cat = catalogue_by_code()
    assert len(cat) == 54 and all(len(s["levels"]) >= 2 for s in cat.values())


def test_requirements_are_cumulative_and_priced_once():
    assert set(requirements_at("Heating", 1)) <= set(requirements_at("Heating", 3))
    assert upgrade("Heating", 2, 2, 1000)["cost"] == 0 and upgrade("Heating", 3, 1, 1000)["cost"] == 0
    up = upgrade("Heating", 1, 3, 1000)
    assert len(up["requirements"]) == len(set(up["requirements"])) and up["cost"] > 0


def test_domain_scores_match_sheet():
    a = load_example()
    r = compute(a)
    for d, ref in a["results"]["domains"].items():
        assert r["domains"][d] == pytest.approx(ref, abs=1e-12)
