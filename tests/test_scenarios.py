"""Scenario generation and optimisation (page 4)."""
import random

import pytest

from edison_sri import sri_engine
from edison_sri.parameters import defaults
from edison_sri.scenarios import (Problem, best_choice, dimensions, filters_from_objectives, frontier_2d, is_valid,
                                  optimise, pareto_3d)
from edison_sri.sri_assessment import load_example


@pytest.fixture(scope="module")
def problem():
    return Problem(load_example(), defaults())


def test_start_point_matches_engine(problem):
    m = problem.evaluate(problem.start_levels)
    assert m["sri"] == pytest.approx(81.83013051905721, abs=1e-9)
    assert m["capex"] == m["opex"] == m["lcc"] == 0 and m["reqs"] == 0


def test_incremental_evaluation_matches_engine(problem):
    rng = random.Random(1)
    assessment = load_example()
    for lv in problem.stochastic(5, rng):
        levels = dict(zip(problem.codes, lv))
        ref = 100 * sri_engine.compute(assessment, levels)["total"]
        assert problem.evaluate(lv)["sri"] == pytest.approx(ref, abs=1e-9)


def test_never_downgrade_and_bounds(problem):
    for lv in problem.stochastic(50, random.Random(2)):
        for s, v in zip(problem.services, lv):
            assert s.current <= v <= s.hi and v in s.levels


def test_more_upgrades_cost_more(problem):
    top = problem.evaluate([s.hi for s in problem.services])
    assert top["sri"] > 81.83 and top["capex"] > 0 and top["lcc"] == pytest.approx(top["capex"] + top["opex"]) and top["reqs"] > 0


def test_dimensions_order(problem):
    keys = [d["key"] for d in dimensions(problem)]
    assert keys[:5] == ["sri", "lcc", "capex", "opex", "reqs"]
    assert keys[-len(problem.services):] == [f"svc:{c}" for c in problem.codes]


def test_optimise_respects_filters(problem):
    params = defaults()
    params["mode"] = "budget"
    params["criteria"]["investment_budget"]["value"] = 500_000
    filters = filters_from_objectives(problem, params)
    assert filters["capex"] == [None, 500]
    front, method = optimise(problem, filters, random.Random(3))
    assert front and method.startswith("exact")
    dims = {d["key"]: d for d in dimensions(problem)}
    assert all(is_valid(m, dims, filters) for m in front)
    best = best_choice(front, params)
    assert best["capex"] <= 500 and best["sri"] == max(m["sri"] for m in front)


def test_pareto_helpers():
    ms = [{"sri": 1, "lcc": 1, "reqs": 1}, {"sri": 2, "lcc": 2, "reqs": 1}, {"sri": 1, "lcc": 2, "reqs": 2}]
    assert sorted(pareto_3d(ms)) == [0, 1]
    assert frontier_2d([(1, 1), (2, 2), (1, 2), (3, 5)]) == [(1, 1), (2, 2), (3, 5)]


def test_opex_and_requirement_list(problem):
    from edison_sri.requirements import annuity_factor
    assert annuity_factor(20, 0) == 20 and annuity_factor(20, 4) == pytest.approx(13.5903, abs=1e-4)
    lv = [s.hi for s in problem.services]
    m, items = problem.evaluate(lv), problem.new_requirements(lv)
    assert len(items) == m["reqs"]
    assert sum(i["capex"] for i in items) / 1e3 == pytest.approx(m["capex"])
    assert sum(i["opex_y"] for i in items) / 1e3 == pytest.approx(m["opex_y"])


def test_required_service_keeps_start_evaluable():
    params = defaults()
    params["criteria"]["services_required"].update(active=True, value="V-6")
    pr = Problem(load_example(), params)
    svc = next(s for s in pr.services if s.code == "V-6")
    assert svc.lo == svc.current + 1
    assert pr.evaluate(pr.start_levels)["sri"] == pytest.approx(81.83013051905721, abs=1e-9)


def test_upgrade_plan_and_exports():
    import io

    from openpyxl import load_workbook

    from edison_sri import plan as P
    params = defaults()
    params["criteria"]["investment_budget"]["active"] = True
    a = load_example()
    pr = Problem(a, params)
    lv = [s.hi for s in pr.services]
    sc = {"id": 3, **pr.evaluate(lv)}
    p = P.build_plan(a, params, pr, sc, "scenario #3")
    # costs allocated to the measures add up to the scenario totals
    assert sum(m["capex"] for m in p["measures"]) == pytest.approx(p["costs"]["capex"])
    assert sum(m["opex_y"] for m in p["measures"]) == pytest.approx(p["costs"]["opex_y"])
    assert p["cash_flow"][-1]["cumulative_cost"] == pytest.approx(p["costs"]["lcc"])
    budget = next(r for r in p["criteria"] if r["id"] == "investment_budget")
    assert budget["status"] == ("met" if p["costs"]["capex"] <= 1_500_000 else "not met")
    assert [m["priority"] for m in p["measures"]] == list(range(1, len(p["measures"]) + 1))
    wb = load_workbook(io.BytesIO(P.plan_xlsx(p)))
    assert wb.sheetnames[:3] == ["Summary", "Objectives & constraints", "Measures"]
    up = P.upgraded_assessment(a, dict(zip(pr.codes, lv)), "scenario #3", sc)
    assert 100 * up["results"]["total"] == pytest.approx(sc["sri"], abs=1e-9)
    assert set(up["upgrade"]["changed_services"]) == {m["code"] for m in p["measures"]}
    assert load_workbook(io.BytesIO(P.assessment_xlsx(up))).sheetnames[0] == "Summary"
    import json
    assert json.loads(P.assessment_json(up))["results"]["class"] == up["results"]["class"]
