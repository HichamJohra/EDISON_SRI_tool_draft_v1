"""Upgrade selection: exhaustive search over the dummy catalogue.

Exact for the small dummy catalogue (a few thousand combinations). Replace with
a MILP (e.g. scipy.optimize.milp) once the real 27/54-service catalogue and the
measure library are in.
"""
from itertools import product

from .catalogue import SERVICES
from .scoring import class_lower_bound, sri_class, sri_score


def upgrade_cost(code_levels_from: dict, code_levels_to: dict, floor_area_m2: float) -> float:
    total = 0.0
    for s in SERVICES:
        a, b = code_levels_from.get(s.code, 0), code_levels_to.get(s.code, 0)
        if b > a:
            total += s.fixed_cost + s.cost_per_m2[a][b] * floor_area_m2
    return round(total, 0)


def enumerate_packages(levels: dict, floor_area_m2: float):
    """Yield (cost, score, new_levels) for every combination of target levels."""
    options = [range(levels.get(s.code, 0), s.max_level + 1) for s in SERVICES]
    for combo in product(*options):
        new = {s.code: lvl for s, lvl in zip(SERVICES, combo)}
        yield upgrade_cost(levels, new, floor_area_m2), sri_score(new), new


def pareto_front(levels: dict, floor_area_m2: float):
    """Cost–SRI curve: cheapest package for each reachable score, non-dominated."""
    pts = sorted(enumerate_packages(levels, floor_area_m2), key=lambda p: (p[0], -p[1]))
    front, best = [], -1.0
    for cost, score, new in pts:
        if score > best:
            front.append({"cost": cost, "sri": score, "levels": new})
            best = score
    return front


def best_package(levels: dict, floor_area_m2: float, mode: str, target_class: str = "D", budget_nok: float = 0):
    """Target mode: cheapest package reaching the class. Budget mode: highest SRI within budget."""
    front = pareto_front(levels, floor_area_m2)
    if mode == "target":
        need = class_lower_bound(target_class)
        feasible = [p for p in front if p["sri"] >= need]
        return min(feasible, key=lambda p: p["cost"]) if feasible else None
    feasible = [p for p in front if p["cost"] <= budget_nok]
    return max(feasible, key=lambda p: p["sri"]) if feasible else None


def package_table(levels: dict, new_levels: dict, floor_area_m2: float):
    """Rows describing each service step in a package (for the results table)."""
    rows = []
    for s in SERVICES:
        a, b = levels.get(s.code, 0), new_levels.get(s.code, 0)
        if b > a:
            one = {**levels, s.code: b}
            rows.append({
                "Service": f"{s.code} {s.name}",
                "Domain": s.domain,
                "From": a,
                "To": b,
                "Cost (NOK)": upgrade_cost(levels, one, floor_area_m2),
                "SRI gain alone (pts)": round(sri_score(one) - sri_score(levels), 2),
            })
    return sorted(rows, key=lambda r: r["Cost (NOK)"] / max(r["SRI gain alone (pts)"], 1e-9))


__all__ = ["best_package", "pareto_front", "package_table", "upgrade_cost", "sri_class"]
