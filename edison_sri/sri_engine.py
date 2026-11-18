"""SRI calculation (EU method, Delegated Regulation 2020/2155, Annex I), as implemented in the EU calculation
sheet v4.5. Reproduces the sheet's total, impact-criterion and key-functionality scores exactly for the ARV example
(see tests/test_sri_engine.py).

For each technical domain d and impact criterion ic:
    I(d, ic)     = sum of the ordinal impact scores of the services at their assessed level
                   (only services applicable in the building and counted in the maximum score)
    Imax(d, ic)  = sum of the services' maximum impact scores (as the sheet computes them)
    SR_ic        = sum_d W(d, ic) * I(d, ic) / sum_d W(d, ic) * Imax(d, ic)     (ratio of weighted sums)
    SRI          = sum_ic W_ic * SR_ic
Key functionalities: 1 building = energy efficiency + maintenance; 2 user = comfort, convenience, health,
information; 3 grid = energy flexibility (weighted by the impact weights).
Domain score (not in the regulation, as in the sheet's results): impact-weighted mean of the domain's
I/Imax ratios over the criteria where Imax != 0.
"""
from functools import lru_cache
import json

from .sri_assessment import DATA_DIR

CATALOGUE_FILE = DATA_DIR / "sri_catalogue_v4_5.json"
KF_GROUPS = {"Key functionality 1 - building": [0, 5], "Key functionality 2 - user": [2, 3, 4, 6],
             "Key functionality 3 - grid": [1]}
KF_NAMES = {"Key functionality 1 - building": "Energy performance and operation",
            "Key functionality 2 - user": "Response to user needs",
            "Key functionality 3 - grid": "Energy flexibility"}
CLASS_BOUNDS = [(0.9, "90–100 %"), (0.8, "80–90 %"), (0.65, "65–80 %"), (0.5, "50–65 %"),
                (0.35, "35–50 %"), (0.2, "20–35 %"), (0.0, "< 20 %")]


@lru_cache(maxsize=1)
def load_catalogue() -> dict:
    return json.loads(CATALOGUE_FILE.read_text(encoding="utf-8"))


def catalogue_by_code() -> dict:
    return {s["code"]: s for s in load_catalogue()["services"]}


def impacts_at(code: str, level: int) -> list[float]:
    svc = catalogue_by_code()[code]
    return next((lv["impacts"] for lv in svc["levels"] if lv["level"] == level), [0] * 7)


def sri_class(score: float) -> str:
    return next(label for bound, label in CLASS_BOUNDS if score >= bound)


def compute(assessment: dict, levels: dict | None = None) -> dict:
    """SRI results for the assessment, optionally with some service levels replaced ({code: level})."""
    levels = levels or {}
    w_imp = assessment["weights"]["impact_criteria"]
    w_dom = assessment["weights"]["domains"]
    I: dict[str, list[float]] = {}
    M: dict[str, list[float]] = {}
    for s in assessment["services"]:
        d = s["domain"]
        I.setdefault(d, [0.0] * 7)
        M.setdefault(d, [0.0] * 7)
        for k in range(7):
            M[d][k] += s["max_impacts"][k]
        if s["applicable"] and s["in_max_score"]:
            imp = impacts_at(s["code"], levels.get(s["code"], s["level"]))
            for k in range(7):
                I[d][k] += imp[k]
    sr = []
    for k in range(7):
        doms = [d for d in I if M[d][k] != 0]
        den = sum(w_dom[d][k] * M[d][k] for d in doms)
        sr.append(sum(w_dom[d][k] * I[d][k] for d in doms) / den if den else 0.0)
    total = sum(w * s for w, s in zip(w_imp, sr))
    kfs = {kf: sum(w_imp[k] * sr[k] for k in idx) / sum(w_imp[k] for k in idx) for kf, idx in KF_GROUPS.items()}
    domain_impact = {d: [I[d][k] / M[d][k] if M[d][k] != 0 else None for k in range(7)] for d in I}
    domains = {}
    for d, ratios in domain_impact.items():
        den = sum(w for w, r in zip(w_imp, ratios) if r is not None)
        domains[d] = sum(w * r for w, r in zip(w_imp, ratios) if r is not None) / den if den else None
    return {"total": total, "impact_criteria": sr, "key_functionalities": kfs,
            "domains": domains, "domain_impact": domain_impact}


def level_sensitivity(assessment: dict, code: str) -> list[dict]:
    """SRI when only this service changes level (all others as assessed). Empty if not counted in the score."""
    svc = next((s for s in assessment["services"] if s["code"] == code), None)
    if svc is None or not (svc["applicable"] and svc["in_max_score"]):
        return []
    out = []
    for lv in catalogue_by_code()[code]["levels"]:
        r = compute(assessment, {code: lv["level"]})
        out.append({"level": lv["level"], **r})
    return out


def affected(code: str) -> dict:
    """Impact criteria (indexes) and key functionalities on which the service has a non-zero impact at any level."""
    svc = catalogue_by_code()[code]
    crit = [k for k in range(7) if any(lv["impacts"][k] != 0 for lv in svc["levels"])]
    kfs = [kf for kf, idx in KF_GROUPS.items() if set(idx) & set(crit)]
    return {"impact_criteria": crit, "key_functionalities": kfs}
