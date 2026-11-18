"""Upgrade plan and upgraded SRI assessment of one scenario, and their exports (JSON, Excel).

Used by "5. SRI upgrade assessment" and "6. Upgrade plan". Pure functions (no Dash), so they can be tested and
reused outside the web app.

Cost allocation per service (draft rule): each new technical requirement is shared equally between the upgraded
services that need it at their target level (e.g. a BMS needed by three upgrades → one third each).
"""
import copy
import io
import json
from datetime import date

from .parameters import BY_ID
from .scenarios import CLASS_LOWER, Problem
from .sri_engine import KF_GROUPS, catalogue_by_code, compute, sri_class

FORMAT = "edison-sri-upgrade-plan/0.1"
IMPACT_NAMES = ["Energy efficiency", "Energy flexibility and storage", "Comfort", "Convenience",
                "Health, well-being and accessibility", "Maintenance and fault prediction", "Information to occupants"]
KF_LABELS = ["Key functionality 1 – building", "Key functionality 2 – user", "Key functionality 3 – grid"]


# ---------------------------------------------------------------------------------------------------------------
# Upgraded assessment
def upgraded_assessment(assessment: dict, levels: dict, label: str, scenario: dict | None = None) -> dict:
    """The assessment with some service levels replaced ({code: level}) and its results recomputed (EU method),
    in the same format as an imported assessment (can be imported again as JSON)."""
    cat = catalogue_by_code()
    data = copy.deepcopy(assessment)
    for s in data["services"]:
        if s["code"] in levels and levels[s["code"]] != s["level"]:
            s["level"] = levels[s["code"]]
            s["level_description"] = next((x["description"] for x in cat[s["code"]]["levels"]
                                            if x["level"] == s["level"]), s.get("level_description"))
    res = compute(data)
    names = list(assessment["results"]["impact_criteria"])  # engine lists → named dicts (as in imported results)
    data["results"] = {**res, "class": sri_class(res["total"]),
                       "impact_criteria": dict(zip(names, res["impact_criteria"])),
                       "domain_impact": {d: dict(zip(names, v)) for d, v in res["domain_impact"].items()}}
    data["building"] = {**data["building"], "name": f"{data['building']['name']} – {label}"}
    data["upgrade"] = {"label": label, "date": date.today().isoformat(),
                       "initial_total": assessment["results"]["total"],
                       "changed_services": {c: {"from": s0["level"], "to": levels[c]}
                                            for s0 in assessment["services"] for c in [s0["code"]]
                                            if c in levels and levels[c] != s0["level"]},
                       **({"costs_knok": {k: scenario[k] for k in ("capex", "opex", "opex_y", "lcc")},
                           "new_requirements": scenario["reqs"]} if scenario else {})}
    return data


# ---------------------------------------------------------------------------------------------------------------
# Upgrade plan
def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _level_desc(cat: dict, code: str, level: int) -> str:
    return next((x["description"] for x in cat[code]["levels"] if x["level"] == level), "")


def build_plan(assessment: dict, params: dict, problem: Problem, scenario: dict, label: str) -> dict:
    """Everything the upgrade plan shows and exports, for one evaluated scenario (see Problem.evaluate)."""
    cat = catalogue_by_code()
    start = problem.evaluate(problem.start_levels)
    lv = scenario["lv"]
    upgraded = [(i, s, lv[i]) for i, s in enumerate(problem.services) if lv[i] != s.current]
    new_reqs = problem.new_requirements(lv)

    # Requirements: which upgraded services need each new item → equal shares
    users = {r["requirement"]: [s.code for _, s, t in upgraded if r["requirement"] in problem.reqs[s.code][t]]
             for r in new_reqs}
    share = {code: {"capex": 0.0, "opex_y": 0.0, "items": []} for _, s, _ in upgraded for code in [s.code]}
    for r in new_reqs:
        u = users[r["requirement"]] or [None]
        for code in u:
            if code is None:
                continue
            share[code]["capex"] += r["capex"] / len(u)
            share[code]["opex_y"] += r["opex_y"] / len(u)
            share[code]["items"].append(r["requirement"] + (f" (shared by {len(u)})" if len(u) > 1 else ""))

    # Measures
    measures = []
    for i, s, t in upgraded:
        alone = list(problem.start_levels)
        alone[i] = t
        m1 = problem.evaluate(alone)
        d_imp = [n - o for n, o in zip(m1["imp"], start["imp"])]
        top = [IMPACT_NAMES[k] for k in sorted(range(7), key=lambda k: -d_imp[k]) if d_imp[k] > 1e-9][:3]
        capex, opex_y = share[s.code]["capex"], share[s.code]["opex_y"]
        lcc = capex + opex_y * problem.af
        d_sri = m1["sri"] - start["sri"]
        kfs = [KF_LABELS[n] for n, idx in enumerate(KF_GROUPS.values())
               if any(abs(problem.delta[s.code][t][k]) > 1e-12 for k in idx)]
        text = (f"Raise “{s.name}” from level {s.current} ({_level_desc(cat, s.code, s.current) or '–'}) to level "
                f"{t} ({_level_desc(cat, s.code, t) or '–'}). ")
        text += (f"On its own this upgrade adds {d_sri:+.2f} SRI points" +
                 (f", mainly through {_and(top).lower()}." if top else ".") if d_sri > 1e-9 else
                 "On its own it does not change the total score; it supports other upgrades.")
        measures.append({
            "code": s.code, "service": s.name, "domain": s.domain, "from": s.current, "to": t,
            "from_description": _level_desc(cat, s.code, s.current), "to_description": _level_desc(cat, s.code, t),
            "d_sri_alone": d_sri, "key_functionalities": kfs, "explanation": text,
            "requirements": share[s.code]["items"], "capex": capex, "opex_y": opex_y, "lcc": lcc,
            "sri_per_mnok": d_sri / (lcc / 1e6) if lcc > 0 else None,
        })
    # Suggested order: most SRI per NOK of life-cycle cost first
    measures.sort(key=lambda m: -(m["sri_per_mnok"] if m["sri_per_mnok"] is not None else 1e12))
    for n, m in enumerate(measures, 1):
        m["priority"] = n

    # Costs per domain
    by_domain: dict[str, dict] = {}
    for m in measures:
        d = by_domain.setdefault(m["domain"], {"domain": m["domain"], "capex": 0.0, "opex_y": 0.0, "lcc": 0.0,
                                                "services": 0})
        for k in ("capex", "opex_y", "lcc"):
            d[k] += m[k]
        d["services"] += 1

    # Cumulative discounted cost over the life-cycle horizon (CAPEX in year 0, OPEX every year)
    r = problem.rate / 100
    cum, cash = 1e3 * scenario["capex"], []
    for y in range(int(problem.horizon) + 1):
        if y > 0:
            cum += 1e3 * scenario["opex_y"] / (1 + r) ** y
        cash.append({"year": y, "cumulative_cost": cum})

    return {
        "format": FORMAT, "date": date.today().isoformat(), "label": label, "scenario_id": scenario.get("id"),
        "building": assessment["building"], "source": assessment.get("source", {}),
        "settings": {"mode": params["mode"], "cost_db": params["cost_db"], "floor_area_m2": problem.area,
                     "lcc_horizon": problem.horizon, "discount_rate": problem.rate},
        "initial": {"sri": start["sri"], "class": sri_class(start["sri"] / 100), "kf": start["kf"],
                    "imp": start["imp"], "dom": start["dom"]},
        "upgraded": {"sri": scenario["sri"], "class": sri_class(scenario["sri"] / 100), "kf": scenario["kf"],
                     "imp": scenario["imp"], "dom": scenario["dom"]},
        "domains": problem.domains,
        "costs": {"capex": 1e3 * scenario["capex"], "opex_y": 1e3 * scenario["opex_y"],
                  "opex": 1e3 * scenario["opex"], "lcc": 1e3 * scenario["lcc"],
                  "capex_per_m2": 1e3 * scenario["capex"] / problem.area},
        "measures": measures,
        "requirements": [{**r, "used_by": users[r["requirement"]]} for r in new_reqs],
        "by_domain": sorted(by_domain.values(), key=lambda d: -d["lcc"]),
        "cash_flow": cash,
        "criteria": check_criteria(params, problem, scenario, measures),
    }


def check_criteria(params: dict, problem: Problem, sc: dict, measures: list[dict]) -> list[dict]:
    """Active objectives & constraints with the value reached by the scenario: met / not met / not evaluated."""
    crit = params["criteria"]
    capex_by_domain: dict[str, float] = {}
    for m in measures:
        capex_by_domain[m["domain"]] = capex_by_domain.get(m["domain"], 0) + m["capex"]
    changed = {m["code"]: m for m in measures}
    imp_ids = [c for c in BY_ID if c.startswith("impact_") and c.endswith("_min")]
    dom_ids = [c for c in BY_ID if c.startswith("domain_") and c.endswith("_min")]
    budget_dom = {f"budget_{c[len('domain_'):-len('_min')]}": d for c, d in zip(dom_ids, problem.domains)}

    def codes(v):
        return [c.strip() for c in str(v or "").replace(",", ";").split(";") if c.strip()]

    rows = []
    for c in BY_ID.values():
        active = crit[c.id]["active"] or (c.id == "investment_budget" and params["mode"] == "budget")
        if not active or c.kind == "Setting":
            continue
        v = crit[c.id]["value"]
        reached, ok = None, None
        if c.id == "sri_class_min":
            reached, ok = sri_class(sc["sri"] / 100), sc["sri"] >= CLASS_LOWER[v]
        elif c.id == "sri_total_min":
            reached = sc["sri"]
        elif c.id in ("kf1_min", "kf2_min", "kf3_min"):
            reached = sc["kf"][int(c.id[2]) - 1]
        elif c.id in imp_ids:
            reached = sc["imp"][imp_ids.index(c.id)]
        elif c.id in dom_ids:
            reached = sc["dom"][dom_ids.index(c.id)]
        elif c.id == "investment_budget":
            reached = 1e3 * sc["capex"]
        elif c.id == "investment_per_m2_max":
            reached = 1e3 * sc["capex"] / problem.area
        elif c.id == "operation_budget":
            reached = 1e3 * sc["opex_y"]
        elif c.id in budget_dom:
            reached = capex_by_domain.get(budget_dom[c.id], 0.0)
        elif c.id in ("budget_kf1", "budget_kf2", "budget_kf3"):
            label = KF_LABELS[int(c.id[-1]) - 1]
            reached = sum(m["capex"] for m in measures if label in m["key_functionalities"])
        elif c.id == "new_requirements_max":
            reached = sc["reqs"]
        elif c.id == "max_level_jump":
            reached = max([m["to"] - m["from"] for m in measures] or [0])
        elif c.id == "reuse_existing":
            reached, ok = "equipment already in the building is counted at no cost", True
        elif c.id == "no_downgrade":
            reached, ok = "no service lowered", True
        elif c.id == "services_required":
            missing = [x for x in codes(v) if x not in changed]
            reached, ok = ("all upgraded" if not missing else "missing: " + ", ".join(missing)), not missing
        elif c.id == "services_excluded":
            touched = [x for x in codes(v) if x in changed]
            reached, ok = ("none changed" if not touched else "changed: " + ", ".join(touched)), not touched
        if ok is None and isinstance(reached, (int, float)) and v is not None:
            ok = reached >= v - 1e-9 if c.op == "≥" else reached <= v + 1e-9
        rows.append({"id": c.id, "category": c.category, "criterion": c.label, "kind": c.kind, "operator": c.op,
                     "target": v, "unit": c.unit, "reached": reached,
                     "status": "not evaluated in the draft" if ok is None else ("met" if ok else "not met")})
    return rows


# ---------------------------------------------------------------------------------------------------------------
# Exports
def _json_default(o):
    return str(o)


def assessment_json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")


def plan_json(plan: dict) -> bytes:
    return json.dumps(plan, ensure_ascii=False, indent=2, default=_json_default).encode("utf-8")


def _workbook(sheets: list[tuple[str, list[str], list[list]]], widths: dict | None = None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    wb.remove(wb.active)
    for title, header, rows in sheets:
        ws = wb.create_sheet(title[:31])
        ws.append(header)
        for row in rows:
            ws.append([x if isinstance(x, (int, float, str)) or x is None else str(x) for x in row])
        for cell in ws[1]:
            cell.font = Font(name="Arial", bold=True)
            cell.fill = PatternFill("solid", fgColor="DCE6F1")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Arial")
                if isinstance(cell.value, float):
                    cell.number_format = "#,##0.00" if abs(cell.value) < 1000 else "#,##0"
                if isinstance(cell.value, str) and len(cell.value) > 60:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
        for i, h in enumerate(header):
            longest = max([len(str(h))] + [len(str(r[i])) for r in rows if i < len(r) and r[i] is not None])
            ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = min(max(10, longest + 2), 70)
        ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def assessment_xlsx(data: dict) -> bytes:
    r, b = data["results"], data["building"]
    up = data.get("upgrade", {})
    summary = [["Building", b.get("name")], ["Usage", b.get("usage")], ["Location", b.get("location")],
               ["Source", f"{data['source']['tool']} v{data['source']['version']}"],
               ["Service catalogue", f"Method {data['method']['catalogue']}"],
               ["Total SRI (%)", 100 * r["total"]], ["SRI class", r["class"]],
               *[[k, 100 * v] for k, v in r["key_functionalities"].items()]]
    if up:
        summary += [["Initial total SRI (%)", 100 * up["initial_total"]], ["Upgrade", up["label"]],
                    ["Date", up["date"]]]
        summary += [[f"{k.upper()} (kNOK)", v] for k, v in up.get("costs_knok", {}).items()]
    changed = up.get("changed_services", {})
    services = [[s["domain"], s["code"], s["service"], changed.get(s["code"], {}).get("from", s["level"]),
                 s["level"], s["max_level"], "yes" if s["code"] in changed else "", s.get("level_description"),
                 "yes" if s["applicable"] else "no"] for s in data["services"]]
    impacts = list(r["impact_criteria"])
    return _workbook([
        ("Summary", ["Item", "Value"], summary),
        ("Services", ["Domain", "Code", "Service", "Initial level", "Level", "Highest level", "Upgraded",
                      "Functionality level", "Applicable"], services),
        ("Impact criteria", ["Impact criterion", "Score (%)"], [[k, 100 * v] for k, v in r["impact_criteria"].items()]),
        ("Domains", ["Domain", "Score (%)"], [[k, None if v is None else 100 * v] for k, v in r["domains"].items()]),
        ("Domain x impact", ["Domain"] + impacts,
         [[d] + [None if row[i] is None else 100 * row[i] for i in impacts] for d, row in r["domain_impact"].items()]),
    ])


def plan_xlsx(plan: dict) -> bytes:
    c, i, u = plan["costs"], plan["initial"], plan["upgraded"]
    st = plan["settings"]
    summary = [["Building", plan["building"].get("name")], ["Plan", plan["label"]], ["Date", plan["date"]],
               ["Decision mode", st["mode"]], ["Cost database", st["cost_db"]], ["Floor area (m²)", st["floor_area_m2"]],
               ["LCC horizon (years)", st["lcc_horizon"]], ["Discount rate (%)", st["discount_rate"]],
               ["Initial total SRI (%)", i["sri"]], ["Upgraded total SRI (%)", u["sri"]],
               ["Initial SRI class", i["class"]], ["Upgraded SRI class", u["class"]],
               *[[f"{KF_LABELS[k]} (%) initial → upgraded", f"{i['kf'][k]:.1f} → {u['kf'][k]:.1f}"] for k in range(3)],
               ["CAPEX (NOK)", c["capex"]], ["CAPEX per m² (NOK/m²)", c["capex_per_m2"]],
               ["OPEX (NOK/year)", c["opex_y"]], ["OPEX present value (NOK)", c["opex"]], ["LCC (NOK)", c["lcc"]],
               ["Upgraded services", len(plan["measures"])], ["New technical requirements", len(plan["requirements"])],
               ["Note", "Draft: dummy technical requirements, prices and operating costs."]]
    return _workbook([
        ("Summary", ["Item", "Value"], summary),
        ("Objectives & constraints", ["Category", "Criterion", "Type", "Operator", "Target", "Unit", "Reached",
                                      "Status"],
         [[r["category"], r["criterion"], r["kind"], r["operator"], r["target"], r["unit"], r["reached"], r["status"]]
          for r in plan["criteria"]]),
        ("Measures", ["Priority", "Code", "Service", "Domain", "From level", "To level", "Target functionality",
                      "ΔSRI alone (pt)", "CAPEX (NOK)", "OPEX (NOK/year)", "LCC (NOK)", "Requirements",
                      "Explanation"],
         [[m["priority"], m["code"], m["service"], m["domain"], m["from"], m["to"], m["to_description"],
           m["d_sri_alone"], m["capex"], m["opex_y"], m["lcc"], "; ".join(m["requirements"]), m["explanation"]]
          for m in plan["measures"]]),
        ("Technical requirements", ["Requirement", "Used by", "CAPEX (NOK)", "OPEX (NOK/year)"],
         [[r["requirement"], ", ".join(r["used_by"]), r["capex"], r["opex_y"]] for r in plan["requirements"]]),
        ("Costs per domain", ["Domain", "Upgraded services", "CAPEX (NOK)", "OPEX (NOK/year)", "LCC (NOK)"],
         [[d["domain"], d["services"], d["capex"], d["opex_y"], d["lcc"]] for d in plan["by_domain"]]),
        ("Scores", ["Score", "Initial (%)", "Upgraded (%)"],
         [["Total SRI", i["sri"], u["sri"]]] + [[KF_LABELS[k], i["kf"][k], u["kf"][k]] for k in range(3)] +
         [[n, i["imp"][k], u["imp"][k]] for k, n in enumerate(IMPACT_NAMES)] +
         [[d, i["dom"][k], u["dom"][k]] for k, d in enumerate(plan["domains"])]),
        ("Cash flow", ["Year", "Cumulative discounted cost (NOK)"],
         [[x["year"], x["cumulative_cost"]] for x in plan["cash_flow"]]),
    ])

