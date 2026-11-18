"""Objectives & constraints: definitions, validation, and export/import as JSON, YAML or Excel.

Stored / exported content:
    format, mode, cost_db, floor_area_m2      general settings
    criteria: {id: {"active": bool, "value": …}}   the table of objectives and constraints (CRITERIA below)
Derived for the draft optimiser (not exported): target_class, budget_nok.
Excel: sheet "Settings" (Parameter | Value | Description) and sheet "Objectives and constraints"
(id | Active | Value | Category | Parameter | Operator | Unit | Status). Only id, Active and Value are read back.
Files are read in memory only and never stored on the server.
"""
import base64
import io
import json
from dataclasses import dataclass
from datetime import date

from .requirements import COST_DATABASES

FORMAT = "edison-sri-objectives/0.2"
MAX_BYTES = 1_000_000
EXPORT_FORMATS = {"xlsx": "Excel (.xlsx)", "yaml": "YAML (.yaml)", "json": "JSON (.json)"}
YES_NO = ["yes", "no"]
CLASSES = list("ABCDEF")


@dataclass(frozen=True)
class Criterion:
    id: str
    category: str
    label: str
    kind: str          # "Objective" or "Constraint"
    op: str            # "≥", "≤", "=", "include", "exclude"
    vtype: str         # percent | number | class | yesno | text
    default: object
    unit: str = ""
    active: bool = False
    in_draft: bool = False   # used by the draft optimiser today
    vmax: float | None = None
    help: str = ""


_IMPACTS = ["Energy efficiency", "Energy flexibility and storage", "Comfort", "Convenience",
            "Health, well-being and accessibility", "Maintenance and fault prediction", "Information to occupants"]
_DOMAINS = ["Heating", "Domestic hot water", "Cooling", "Ventilation", "Lighting", "Dynamic building envelope",
            "Electricity", "Electric vehicle charging", "Monitoring and control"]
_KFS = [("kf1", "Key functionality 1 – building (energy performance and operation)"),
        ("kf2", "Key functionality 2 – user (response to user needs)"),
        ("kf3", "Key functionality 3 – grid (energy flexibility)")]


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_").replace("__", "_")


CRITERIA: list[Criterion] = [
    # --- SRI targets -----------------------------------------------------------------------------------------
    Criterion("sri_class_min", "1. SRI targets", "SRI class", "Objective", "≥", "class", "D", "class",
              active=True, in_draft=True, help="Target mode: reach at least this class at the lowest cost"),
    Criterion("sri_total_min", "1. SRI targets", "Total SRI score", "Objective", "≥", "percent", 65, "%"),
    *[Criterion(f"{k}_min", "1. SRI targets", label, "Objective", "≥", "percent", 70, "%") for k, label in _KFS],
    *[Criterion(f"impact_{_slug(i)}_min", "2. Impact criteria", i, "Objective", "≥", "percent", 60, "%")
      for i in _IMPACTS],
    *[Criterion(f"domain_{_slug(d)}_min", "3. Technical domains", f"Domain score – {d}", "Objective", "≥",
                "percent", 50, "%") for d in _DOMAINS],
    # --- Investment and operation ----------------------------------------------------------------------------
    Criterion("investment_budget", "4. Budgets and costs", "Total investment budget", "Constraint", "≤", "number",
              1_500_000, "NOK", in_draft=True, help="Budget mode: highest SRI within this investment"),
    Criterion("investment_per_m2_max", "4. Budgets and costs", "Investment per m² of heated floor area", "Constraint",
              "≤", "number", 150, "NOK/m²"),
    Criterion("operation_budget", "4. Budgets and costs", "Annual operation and maintenance budget", "Constraint",
              "≤", "number", 100_000, "NOK/year"),
    Criterion("payback_max", "4. Budgets and costs", "Simple payback time", "Constraint", "≤", "number", 15, "years",
              help="Needs energy savings (later version)"),
    Criterion("lcc_horizon", "4. Budgets and costs", "Life-cycle cost horizon", "Setting", "=", "number", 20, "years"),
    Criterion("discount_rate", "4. Budgets and costs", "Discount rate", "Setting", "=", "percent", 4, "%"),
    *[Criterion(f"budget_{_slug(d)}", "5. Budget per domain", f"Investment budget – {d}", "Constraint", "≤",
                "number", 500_000, "NOK") for d in _DOMAINS],
    *[Criterion(f"budget_{k}", "6. Budget per key functionality", f"Investment budget – {label}", "Constraint",
                "≤", "number", 750_000, "NOK", help="Investment of services affecting this key functionality")
      for k, label in _KFS],
    # --- Technical requirements ------------------------------------------------------------------------------
    Criterion("new_requirements_max", "7. Technical requirements", "Number of new technical requirements",
              "Constraint", "≤", "number", 10, "items"),
    Criterion("reuse_existing", "7. Technical requirements", "Reuse equipment already in the building",
              "Objective", "=", "yesno", "yes", "", active=True),
    Criterion("open_protocols", "7. Technical requirements", "Open communication protocols only (BACnet, KNX, Modbus)",
              "Constraint", "=", "yesno", "yes", ""),
    Criterion("requirements_required", "7. Technical requirements", "Technical requirements that must be included",
              "Constraint", "include", "text", "", "list", help="Names separated by ';'"),
    Criterion("requirements_excluded", "7. Technical requirements", "Technical requirements that must not be used",
              "Constraint", "exclude", "text", "", "list", help="Names separated by ';'"),
    # --- Implementation --------------------------------------------------------------------------------------
    Criterion("no_downgrade", "8. Implementation", "Never lower a service level", "Constraint", "=", "yesno", "yes", "",
              active=True, in_draft=True),
    Criterion("max_level_jump", "8. Implementation", "Largest level increase per service", "Constraint", "≤", "number",
              4, "levels"),
    Criterion("services_required", "8. Implementation", "Services that must be upgraded", "Constraint", "include",
              "text", "", "codes", help="Service codes separated by ';' (e.g. H-1a; MC-25)"),
    Criterion("services_excluded", "8. Implementation", "Services that must not be changed", "Constraint", "exclude",
              "text", "", "codes", help="Service codes separated by ';'"),
    Criterion("phases_max", "8. Implementation", "Number of implementation phases (roadmap)", "Constraint", "≤",
              "number", 3, "phases"),
]
BY_ID = {c.id: c for c in CRITERIA}
SETTINGS = {
    "mode": "Decision mode: 'target' (reach the targets at the lowest investment) or 'budget' (highest SRI within the "
            "investment budget)",
    "cost_db": "Cost database: " + ", ".join(k for k, v in COST_DATABASES.items() if v["available"]),
    "floor_area_m2": "Heated floor area used for cost estimates, in m²",
}
DEFAULT_SETTINGS = {"mode": "target", "cost_db": "default", "floor_area_m2": 17_500}


class ParameterError(ValueError):
    """Problem in a parameter value or file (message shown to the user)."""


def default_criteria() -> dict:
    return {c.id: {"active": c.active, "value": c.default} for c in CRITERIA}


def defaults() -> dict:
    return _derive({**DEFAULT_SETTINGS, "criteria": default_criteria()})


def _derive(p: dict) -> dict:
    """Keys read by the draft optimiser (page 4)."""
    p["target_class"] = p["criteria"]["sri_class_min"]["value"]
    p["budget_nok"] = p["criteria"]["investment_budget"]["value"]
    return p


def _check_value(c: Criterion, v):
    if v in (None, "") and c.vtype == "text":
        return ""
    if c.vtype == "class":
        v = str(v).strip().upper()
        if v not in CLASSES:
            raise ParameterError(f"{c.label}: use one of {', '.join(CLASSES)}.")
        return v
    if c.vtype == "yesno":
        v = {"true": "yes", "false": "no", "1": "yes", "0": "no"}.get(str(v).strip().lower(), str(v).strip().lower())
        if v not in YES_NO:
            raise ParameterError(f"{c.label}: use yes or no.")
        return v
    if c.vtype == "text":
        return str(v).strip()
    try:
        x = float(str(v).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        raise ParameterError(f"{c.label}: '{v}' is not a number.") from None
    hi = 100 if c.vtype == "percent" else 1e12
    if not 0 <= x <= hi:
        raise ParameterError(f"{c.label}: must be between 0 and {hi:g}.")
    return int(x) if x.is_integer() else x


def _to_bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y", "x", "✓")


def validate(raw: dict) -> tuple[dict, list[str]]:
    """Checked parameters (missing ones = defaults) and warnings. Raises ParameterError if a value is invalid.

    Also accepts the flat files of format 0.1 (target_class, budget_nok at top level)."""
    if not isinstance(raw, dict):
        raise ParameterError("The file must contain named parameters (e.g. mode: target).")
    warnings = []
    out = {**DEFAULT_SETTINGS, "criteria": default_criteria()}
    for k in SETTINGS:
        if raw.get(k) not in (None, ""):
            out[k] = raw[k]
    out["mode"] = str(out["mode"]).strip().lower()
    if out["mode"] not in ("target", "budget"):
        raise ParameterError("mode must be 'target' or 'budget'.")
    out["cost_db"] = str(out["cost_db"]).strip()
    if out["cost_db"] not in COST_DATABASES or not COST_DATABASES[out["cost_db"]]["available"]:
        raise ParameterError(f"cost_db '{out['cost_db']}' is not available.")
    try:
        out["floor_area_m2"] = float(out["floor_area_m2"])
    except (TypeError, ValueError):
        raise ParameterError("floor_area_m2 must be a number.") from None
    if not 1 <= out["floor_area_m2"] <= 1e7:
        raise ParameterError("floor_area_m2 must be between 1 and 10 000 000.")
    if out["floor_area_m2"].is_integer():
        out["floor_area_m2"] = int(out["floor_area_m2"])

    crit = raw.get("criteria") or {}
    if not isinstance(crit, dict):
        raise ParameterError("criteria must be a mapping id → {active, value}.")
    for legacy, cid in (("target_class", "sri_class_min"), ("budget_nok", "investment_budget")):
        if legacy in raw and cid not in crit:  # format 0.1
            crit[cid] = {"active": True, "value": raw[legacy]}
    for cid, item in crit.items():
        if cid not in BY_ID:
            warnings.append(f"Unknown objective/constraint ignored: {cid}")
            continue
        item = item if isinstance(item, dict) else {"value": item}
        c = BY_ID[cid]
        if "active" in item:
            out["criteria"][cid]["active"] = _to_bool(item["active"])
        if "value" in item:
            out["criteria"][cid]["value"] = _check_value(c, item["value"])
    known = set(SETTINGS) | {"format", "criteria", "target_class", "budget_nok"}
    warnings += [f"Unknown parameter ignored: {k}" for k in raw if k not in known]
    return _derive(out), warnings


def grid_rows(params: dict) -> list[dict]:
    """Rows of the objectives & constraints table (for dash-ag-grid)."""
    rows = []
    for c in CRITERIA:
        item = params["criteria"].get(c.id, {"active": c.active, "value": c.default})
        rows.append({"id": c.id, "active": bool(item["active"]), "category": c.category, "label": c.label,
                     "kind": c.kind, "op": c.op, "value": item["value"], "unit": c.unit,
                     "status": "Used now" if c.in_draft else "Planned", "help": c.help,
                     "options": CLASSES if c.vtype == "class" else YES_NO if c.vtype == "yesno" else None})
    return rows


def from_grid(rows: list[dict]) -> dict:
    return {r["id"]: {"active": bool(r.get("active")), "value": r.get("value")} for r in rows or []}


def export_bytes(params: dict, fmt: str) -> tuple[bytes, str]:
    data = {"format": FORMAT, **{k: params.get(k) for k in SETTINGS},
            "criteria": {c.id: dict(params["criteria"][c.id]) for c in CRITERIA}}
    stem = f"edison_sri_objectives_{date.today().isoformat()}"
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"), f"{stem}.json"
    if fmt == "yaml":
        import yaml  # optional dependency (pyyaml)
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True).encode("utf-8"), f"{stem}.yaml"
    if fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb = Workbook()
        ws = wb.active
        ws.title = "Settings"
        ws.append(["Parameter", "Value", "Description"])
        ws.append(["format", FORMAT, "File format marker – do not change"])
        for k, desc in SETTINGS.items():
            ws.append([k, params.get(k), desc])
        t = wb.create_sheet("Objectives and constraints")
        t.append(["id", "Active", "Value", "Category", "Parameter", "Operator", "Unit", "Type", "Status", "Help"])
        for c in CRITERIA:
            item = params["criteria"][c.id]
            t.append([c.id, "yes" if item["active"] else "no", item["value"], c.category, c.label, c.op, c.unit,
                      c.kind, "Used now" if c.in_draft else "Planned", c.help])
        for sheet, widths in ((ws, (16, 26, 90)), (t, (30, 8, 14, 30, 60, 9, 9, 11, 10, 50))):
            for cell in sheet[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="DCE6F1")
            for i, w in enumerate(widths):
                sheet.column_dimensions[chr(65 + i)].width = w
        t.freeze_panes = "D2"
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue(), f"{stem}.xlsx"
    raise ValueError(f"Unknown export format: {fmt}")


def import_upload(contents: str, filename: str) -> tuple[dict, list[str]]:
    """Parse a dcc.Upload payload ('data:…;base64,…') into checked parameters and warnings."""
    try:
        raw_bytes = base64.b64decode(contents.split(",", 1)[1])
    except Exception:  # noqa: BLE001
        raise ParameterError("The file could not be read.") from None
    if len(raw_bytes) > MAX_BYTES:
        raise ParameterError("The file is larger than 1 MB.")
    name = (filename or "").lower()
    try:
        if name.endswith(".json"):
            raw = json.loads(raw_bytes.decode("utf-8-sig"))
        elif name.endswith((".yaml", ".yml")):
            import yaml
            raw = yaml.safe_load(raw_bytes.decode("utf-8-sig"))
        elif name.endswith(".xlsx"):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
            first = wb["Settings"] if "Settings" in wb.sheetnames else wb.worksheets[0]
            raw = {str(r[0]).strip(): r[1] for r in first.iter_rows(min_row=2, max_col=2, values_only=True)
                   if r and r[0] not in (None, "")}
            if "Objectives and constraints" in wb.sheetnames:
                raw["criteria"] = {str(r[0]).strip(): {"active": r[1], "value": r[2]}
                                   for r in wb["Objectives and constraints"].iter_rows(min_row=2, max_col=3,
                                                                                       values_only=True)
                                   if r and r[0] not in (None, "")}
        else:
            raise ParameterError("Use a .json, .yaml/.yml or .xlsx file.")
    except ParameterError:
        raise
    except ImportError as exc:
        raise ParameterError(f"Missing package on the server: {exc.name} (run: uv add {exc.name}).") from None
    except Exception as exc:  # noqa: BLE001 – malformed file
        raise ParameterError(f"The file could not be parsed ({type(exc).__name__}).") from None
    return validate(raw)
