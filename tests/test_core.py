from edison_sri.catalogue import DEFAULT_ASSESSMENT, SERVICES
from edison_sri.optimiser import best_package, pareto_front, upgrade_cost
from edison_sri.scoring import sri_class, sri_score

LEVELS = DEFAULT_ASSESSMENT["levels"]
AREA = 5000


def test_score_bounds():
    assert sri_score({s.code: 0 for s in SERVICES}) == 0
    assert sri_score({s.code: s.max_level for s in SERVICES}) == 100


def test_class():
    assert sri_class(91) == "A" and sri_class(50) == "D" and sri_class(5) == "G"


def test_no_upgrade_costs_nothing():
    assert upgrade_cost(LEVELS, LEVELS, AREA) == 0


def test_pareto_is_monotonic():
    front = pareto_front(LEVELS, AREA)
    assert front[0]["cost"] == 0
    assert all(b["cost"] >= a["cost"] and b["sri"] > a["sri"] for a, b in zip(front, front[1:]))


def test_target_and_budget_modes():
    p = best_package(LEVELS, AREA, "target", target_class="D")
    assert p is not None and p["sri"] >= 50
    q = best_package(LEVELS, AREA, "budget", budget_nok=p["cost"])
    assert q["sri"] >= p["sri"] and q["cost"] <= p["cost"]
