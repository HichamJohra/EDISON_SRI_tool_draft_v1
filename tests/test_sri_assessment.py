from edison_sri.sri_assessment import IMPORT_METHODS, import_assessment, load_example


def test_example_is_complete():
    d = load_example()
    r = d["results"]
    assert 0.81 < r["total"] < 0.82  # ARV Voldsløkka, EU sheet v4.5
    assert len(r["impact_criteria"]) == 7 and len(r["key_functionalities"]) == 3 and len(r["domains"]) == 9
    assert len(d["services"]) == 54  # Method B
    assert all(0 <= s["level"] <= s["max_level"] for s in d["services"])


def test_every_method_loads_the_example():
    for m in IMPORT_METHODS:
        assert import_assessment(m)["results"]["total"] == load_example()["results"]["total"]
