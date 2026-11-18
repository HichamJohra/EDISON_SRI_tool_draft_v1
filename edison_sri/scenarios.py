"""Upgrade scenarios: fast evaluation, stochastic sampling, exact search and Pareto fronts.

A scenario = a functionality level for each upgradable service (applicable, counted in the score, below its highest
level). Evaluation uses the EU calculation of sri_engine incrementally (same results, ~20× faster): the assessed
I(d, ic) sums are updated with the impact differences of the changed services only.

Cost and technical requirements are building-wide: the requirements of all services at their scenario levels are
pooled, so equipment shared by several services (e.g. a BMS or communication network) is counted and priced once;
requirements already needed at the assessed levels are already in the building (cost 0).
Costs (kNOK): CAPEX = investment; OPEX = present value of the annual operation and maintenance costs over the
life-cycle horizon (discount rate); LCC = CAPEX + OPEX.
"""
import itertools
import math
import random
from dataclasses import dataclass, field

from .parameters import BY_ID
from .requirements import annual_opex, annuity_factor, price, requirements_at
from .sri_engine import KF_GROUPS, catalogue_by_code, impacts_at, load_catalogue

CLASS_LOWER = {"A": 90, "B": 80, "C": 65, "D": 50, "E": 35, "F": 20}  # % (Annex VIII)
EXHAUSTIVE_LIMIT = 60_000   # exact search of all combinations up to this size
MAX_SCENARIOS = 4_000       # kept in the browser session


@dataclass
class Service:
    code: str
    name: str
    domain: str
    current: int
    lo: int
    hi: int
    levels: list[int] = field(default_factory=list)


class Problem:
    """Everything needed to evaluate scenarios for one assessment and one set of objectives & constraints."""

    def __init__(self, assessment: dict, params: dict):
        cat = catalogue_by_code()
        self.impacts = load_catalogue()["impact_criteria"]
        self.domains = load_catalogue()["domains"]
        self.w_imp = assessment["weights"]["impact_criteria"]
        self.w_dom = assessment["weights"]["domains"]
        self.area = float(params.get("floor_area_m2") or 1)
        self.db = params.get("cost_db", "default")
        crit = params["criteria"]

        def active(cid):
            return crit[cid]["value"] if crit[cid]["active"] else None

        excluded = {c.strip() for c in str(active("services_excluded") or "").replace(",", ";").split(";") if c.strip()}
        required = {c.strip() for c in str(active("services_required") or "").replace(",", ";").split(";") if c.strip()}
        jump = active("max_level_jump")

        # Assessed sums I, Imax per domain (as in sri_engine.compute)
        self.I = {d: [0.0] * 7 for d in self.domains}
        self.M = {d: [0.0] * 7 for d in self.domains}
        counted = []
        for s in assessment["services"]:
            d = s["domain"]
            self.M[d] = [a + b for a, b in zip(self.M[d], s["max_impacts"])]
            if s["applicable"] and s["in_max_score"]:
                self.I[d] = [a + b for a, b in zip(self.I[d], impacts_at(s["code"], s["level"]))]
                counted.append(s)
        # Upgradable services and their level bounds (never lower a service level in this version)
        self.services: list[Service] = []
        for s in counted:
            lv = [x["level"] for x in cat[s["code"]]["levels"]]
            lo, hi = s["level"], max(lv)
            if s["code"] in excluded:
                hi = lo
            if s["code"] in required:
                lo = min(lo + 1, hi)
            if jump is not None:
                hi = min(hi, s["level"] + int(jump))
            if hi > s["level"] or lo > s["level"]:
                self.services.append(Service(s["code"], cat[s["code"]]["service"], s["domain"], s["level"], lo, hi,
                                             [x for x in lv if lo <= x <= hi]))
        self.codes = [s.code for s in self.services]
        # Impact differences per level, requirement sets per level
        # (also at the current level: the starting point stays evaluable when a service must be upgraded)
        self.delta = {s.code: {lv: [n - c for n, c in zip(impacts_at(s.code, lv), impacts_at(s.code, s.current))]
                               for lv in {s.current, *s.levels}} for s in self.services}
        self.reqs = {s.code: {lv: frozenset(requirements_at(s.domain, lv, s.code)) for lv in {s.current, *s.levels}}
                     for s in self.services}
        self.have = frozenset().union(*[requirements_at(s["domain"], s["level"], s["code"]) for s in counted]) \
            if counted else frozenset()
        self.horizon = float(crit["lcc_horizon"]["value"] or 20)
        self.rate = float(crit["discount_rate"]["value"] or 0)
        self.af = annuity_factor(self.horizon, self.rate)
        self.price, self.opex_y = {}, {}
        self.start_levels = [s.current for s in self.services]

    # ------------------------------------------------------------------------------------------------------------
    def evaluate(self, levels: list[int]) -> dict:
        I = {d: list(v) for d, v in self.I.items()}
        needed = set(self.have)
        for s, lv in zip(self.services, levels):
            if lv != s.current:
                dlt = self.delta[s.code][lv]
                row = I[s.domain]
                for k in range(7):
                    row[k] += dlt[k]
            needed |= self.reqs[s.code][lv]
        sr = []
        for k in range(7):
            num = den = 0.0
            for d in self.domains:
                m = self.M[d][k]
                if m != 0:
                    w = self.w_dom[d][k]
                    num += w * I[d][k]
                    den += w * m
            sr.append(num / den if den else 0.0)
        total = sum(w * s for w, s in zip(self.w_imp, sr))
        kfs = [sum(self.w_imp[k] * sr[k] for k in idx) / sum(self.w_imp[k] for k in idx) for idx in KF_GROUPS.values()]
        doms = []
        for d in self.domains:
            ratios = [I[d][k] / self.M[d][k] if self.M[d][k] != 0 else None for k in range(7)]
            den = sum(w for w, r in zip(self.w_imp, ratios) if r is not None)
            doms.append(sum(w * r for w, r in zip(self.w_imp, ratios) if r is not None) / den if den else None)
        new = needed - self.have
        capex = sum(self._price(r) for r in new) / 1e3
        opex_y = sum(self._opex(r) for r in new) / 1e3
        return {"lv": list(levels), "sri": 100 * total, "kf": [100 * x for x in kfs], "imp": [100 * x for x in sr],
                "dom": [None if x is None else 100 * x for x in doms], "capex": capex, "opex_y": opex_y,
                "opex": opex_y * self.af, "lcc": capex + opex_y * self.af, "reqs": len(new)}

    def new_requirements(self, levels: list[int]) -> list[dict]:
        """Requirements to install for a scenario, with price and annual operating cost (NOK)."""
        needed = set(self.have)
        for s, lv in zip(self.services, levels):
            needed |= self.reqs[s.code][lv]
        return [{"requirement": r, "capex": self._price(r), "opex_y": self._opex(r)}
                for r in sorted(needed - self.have)]

    def _price(self, req: str) -> float:
        if req not in self.price:
            self.price[req] = price(req, self.area, self.db)
        return self.price[req]

    def _opex(self, req: str) -> float:
        if req not in self.opex_y:
            self.opex_y[req] = annual_opex(req, self.area, self.db)
        return self.opex_y[req]

    def combinations(self) -> int:
        return math.prod(len(s.levels) for s in self.services) if self.services else 1

    # ------------------------------------------------------------------------------------------------------------
    def stochastic(self, n: int, rng: random.Random) -> list[list[int]]:
        """n random scenarios: each service keeps its lowest allowed level with probability 0.5, else a random
        higher allowed level (gives a spread of small and large packages)."""
        out = []
        for _ in range(n):
            out.append([s.lo if (len(s.levels) == 1 or rng.random() < 0.5) else rng.choice(s.levels[1:])
                        for s in self.services])
        return out

    def all_combinations(self):
        return itertools.product(*[s.levels for s in self.services])

    def greedy_path(self, key) -> list[list[int]]:
        """Upgrade one level at a time, always the step with the best key(ΔSRI, Δcost, Δreqs)."""
        cur = [s.lo for s in self.services]
        path, m = [list(cur)], self.evaluate(cur)
        while True:
            best, best_val = None, None
            for i, s in enumerate(self.services):
                nxt = [lv for lv in s.levels if lv > cur[i]]
                if not nxt:
                    continue
                cand = list(cur)
                cand[i] = nxt[0]
                mc = self.evaluate(cand)
                v = key(mc["sri"] - m["sri"], mc["lcc"] - m["lcc"], mc["reqs"] - m["reqs"])
                if best_val is None or v > best_val:
                    best, best_val, best_m = cand, v, mc
            if best is None:
                return path
            cur, m = best, best_m
            path.append(list(cur))


# ---------------------------------------------------------------------------------------------------------------
# Parallel-coordinates dimensions and filters
def dimensions(problem: Problem) -> list[dict]:
    """Axis definitions: key, label, accessor; objectives first, then sub-objectives, then service levels."""
    short_imp = ["Energy eff.", "Flexibility", "Comfort", "Convenience", "Health", "Maintenance", "Information"]
    short_dom = ["Heating", "DHW", "Cooling", "Ventilation", "Lighting", "Envelope", "Electricity", "EV charging",
                 "Monitoring"]
    dims = [{"key": "sri", "label": "Total SRI (%)", "get": lambda m: m["sri"], "group": "objective"},
            {"key": "lcc", "label": "LCC (kNOK)", "get": lambda m: m["lcc"], "group": "objective"},
            {"key": "capex", "label": "CAPEX (kNOK)", "get": lambda m: m["capex"], "group": "objective"},
            {"key": "opex", "label": "OPEX (kNOK)", "get": lambda m: m["opex"], "group": "objective"},
            {"key": "reqs", "label": "New tech. req. (#)", "get": lambda m: m["reqs"], "group": "objective"}]
    dims += [{"key": f"kf{i + 1}", "label": f"KF{i + 1} {n} (%)", "get": (lambda m, i=i: m["kf"][i]),
              "group": "kf"} for i, n in enumerate(["building", "user", "grid"])]
    dims += [{"key": f"imp{k}", "label": f"{short_imp[k]} (%)", "get": (lambda m, k=k: m["imp"][k]),
              "group": "impact"} for k in range(7)]
    dims += [{"key": f"dom{j}", "label": f"{short_dom[j]} (%)", "get": (lambda m, j=j: m["dom"][j]),
              "group": "domain"} for j, d in enumerate(problem.domains)]
    dims += [{"key": f"svc:{s.code}", "label": s.code, "get": (lambda m, i=i: m["lv"][i]), "group": "service",
              "service": s} for i, s in enumerate(problem.services)]
    return dims


def filters_from_objectives(problem: Problem, params: dict) -> dict:
    """Initial axis limits from the active objectives & constraints (and the decision mode)."""
    crit = params["criteria"]

    def act(cid):
        return crit[cid]["value"] if crit[cid]["active"] else None

    f = {}
    budget = crit["investment_budget"]["value"] if params["mode"] == "budget" else act("investment_budget")
    per_m2 = act("investment_per_m2_max")
    caps = [x for x in (budget, per_m2 * problem.area if per_m2 is not None else None) if x is not None]
    if caps:
        f["capex"] = [None, min(caps) / 1e3]
    if act("operation_budget") is not None:  # annual budget → present value over the LCC horizon
        f["opex"] = [None, act("operation_budget") * problem.af / 1e3]
    if act("new_requirements_max") is not None:
        f["reqs"] = [None, act("new_requirements_max")]
    sri_min = [act("sri_total_min") or 0]
    if params["mode"] == "target" and act("sri_class_min"):
        sri_min.append(CLASS_LOWER[act("sri_class_min")])
    if max(sri_min) > 0:
        f["sri"] = [max(sri_min), None]
    for i in range(3):
        if act(f"kf{i + 1}_min") is not None:
            f[f"kf{i + 1}"] = [act(f"kf{i + 1}_min"), None]
    imp_ids = [c for c in BY_ID if c.startswith("impact_")]
    for k, cid in enumerate(imp_ids):
        if act(cid) is not None:
            f[f"imp{k}"] = [act(cid), None]
    dom_ids = [c for c in BY_ID if c.startswith("domain_")]
    for j, cid in enumerate(dom_ids):
        if act(cid) is not None:
            f[f"dom{j}"] = [act(cid), None]
    return f


def is_valid(m: dict, dims_by_key: dict, filters: dict) -> bool:
    for key, rng in filters.items():
        if key not in dims_by_key or not rng:
            continue
        v = dims_by_key[key]["get"](m)
        if v is None:
            continue
        lo, hi = rng
        if (lo is not None and v < lo - 1e-9) or (hi is not None and v > hi + 1e-9):
            return False
    return True


def pareto_3d(ms: list[dict]) -> list[int]:
    """Indexes of the non-dominated scenarios for (SRI ↑, life-cycle cost ↓, new requirements ↓)."""
    order = sorted(range(len(ms)), key=lambda i: (ms[i]["lcc"], ms[i]["reqs"], -ms[i]["sri"]))
    front: list[int] = []
    for i in order:
        a = ms[i]
        dominated = any(ms[j]["lcc"] <= a["lcc"] and ms[j]["reqs"] <= a["reqs"] and ms[j]["sri"] >= a["sri"] and
                        (ms[j]["lcc"] < a["lcc"] or ms[j]["reqs"] < a["reqs"] or ms[j]["sri"] > a["sri"])
                        for j in front)
        if not dominated:
            front.append(i)
    return front


def frontier_2d(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Lowest y for each level of x (x ↑ better, y ↓ better): the 2-D Pareto front, sorted by x."""
    out, best = [], math.inf
    for x, y in sorted(points, key=lambda p: (-p[0], p[1])):
        if y < best - 1e-12:
            out.append((x, y))
            best = y
    return sorted(out)


def optimise(problem: Problem, filters: dict, rng: random.Random) -> tuple[list[dict], str]:
    """Scenarios on the constrained Pareto front (exact if the search space is small enough) and a method note."""
    dims_by_key = {d["key"]: d for d in dimensions(problem)}
    n = problem.combinations()
    if n <= EXHAUSTIVE_LIMIT:
        cands = (problem.evaluate(list(c)) for c in problem.all_combinations())
        method = f"exact: all {n:,} combinations evaluated".replace(",", " ")
    else:
        lv = problem.stochastic(20_000, rng)
        lv += problem.greedy_path(lambda ds, dc, dr: ds / (dc + 1e-3))
        lv += problem.greedy_path(lambda ds, dc, dr: ds / (dr + 1e-3))
        cands = (problem.evaluate(x) for x in lv)
        method = f"approximate: 20 000 random + greedy scenarios out of {n:.2e} combinations"
    valid = [m for m in cands if is_valid(m, dims_by_key, filters)]
    front = [valid[i] for i in pareto_3d(valid)]
    return front, method


def best_choice(front: list[dict], params: dict) -> dict | None:
    """Recommended scenario on the front: target mode → lowest life-cycle cost; budget mode → highest SRI."""
    if not front:
        return None
    if params["mode"] == "target":
        return min(front, key=lambda m: (m["lcc"], m["reqs"], -m["sri"]))
    return max(front, key=lambda m: (m["sri"], -m["lcc"], -m["reqs"]))
