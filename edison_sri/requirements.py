"""Technical requirements of each service level and their prices (cost databases).

DUMMY MODEL – placeholder until the EDISON requirement library exists: each functionality level needs the
requirements of the level below plus a few typical items for its domain (shared equipment, e.g. a BMS), and – when
a service code is given – one service-specific item per level step (its own devices and configuration).
Prices are invented numbers.
Each requirement is priced once: going from level a to level b costs the requirements of b not already needed
at a (equipment already in the building costs nothing).
"""

# Requirement library: name -> (price per m² of floor area in NOK, fixed price in NOK)
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "Central controller": (4, 40_000),
    "Room / zone controllers": (35, 0),
    "Temperature sensors": (6, 0),
    "Presence sensors": (12, 0),
    "CO₂ / air-quality sensors": (10, 0),
    "Light / daylight sensors": (5, 0),
    "Actuators (valves, dampers, drives)": (25, 0),
    "Variable-speed drives": (8, 30_000),
    "Energy meters (sub-metering)": (3, 25_000),
    "Communication network (BACnet / KNX / Modbus)": (10, 30_000),
    "Building management system (BMS)": (6, 150_000),
    "Data platform and dashboard": (2, 80_000),
    "Fault detection and diagnostics software": (2, 60_000),
    "Weather forecast service": (0, 20_000),
    "Grid-signal / price interface": (0, 50_000),
    "Optimisation / predictive control software": (3, 120_000),
    "Thermal or electric storage controller": (1, 60_000),
    "Motorised blinds / shading": (40, 0),
    "Lighting control gear (dimmable drivers)": (30, 0),
    "EV chargers": (0, 250_000),
    "Smart charging controller": (0, 60_000),
    "Occupant information display / app": (1, 40_000),
}

COST_DATABASES = {
    "default": {"name": "Default cost database", "available": True,
                "description": "Indicative dummy prices (NOK, excl. VAT) for the draft."},
    "edison_partners": {"name": "EDISON partner prices (planned)", "available": False, "description": ""},
    "statsbygg": {"name": "Statsbygg catalogue (planned)", "available": False, "description": ""},
    "iso52120": {"name": "ISO 52120-1 based estimates (planned)", "available": False, "description": ""},
}

# Typical requirements per domain, by level step (level 1, 2, 3, 4) – dummy
DOMAIN_STEPS = {
    "Heating": [["Central controller", "Temperature sensors"], ["Room / zone controllers", "Actuators (valves, dampers, drives)"],
                ["Communication network (BACnet / KNX / Modbus)", "Building management system (BMS)"],
                ["Presence sensors", "Weather forecast service", "Optimisation / predictive control software"]],
    "Domestic hot water": [["Central controller", "Temperature sensors"], ["Energy meters (sub-metering)"],
                           ["Communication network (BACnet / KNX / Modbus)", "Grid-signal / price interface"],
                           ["Thermal or electric storage controller", "Optimisation / predictive control software"]],
    "Cooling": [["Central controller", "Temperature sensors"], ["Room / zone controllers", "Actuators (valves, dampers, drives)"],
                ["Communication network (BACnet / KNX / Modbus)", "Building management system (BMS)"],
                ["Weather forecast service", "Optimisation / predictive control software"]],
    "Ventilation": [["Central controller", "Variable-speed drives"], ["CO₂ / air-quality sensors", "Actuators (valves, dampers, drives)"],
                    ["Presence sensors", "Communication network (BACnet / KNX / Modbus)"],
                    ["Building management system (BMS)", "Optimisation / predictive control software"]],
    "Lighting": [["Lighting control gear (dimmable drivers)"], ["Presence sensors", "Light / daylight sensors"],
                 ["Communication network (BACnet / KNX / Modbus)"], ["Building management system (BMS)"]],
    "Dynamic building envelope": [["Motorised blinds / shading"], ["Light / daylight sensors", "Central controller"],
                                  ["Communication network (BACnet / KNX / Modbus)", "Building management system (BMS)"],
                                  ["Weather forecast service", "Optimisation / predictive control software"]],
    "Electricity": [["Energy meters (sub-metering)"], ["Data platform and dashboard"],
                    ["Communication network (BACnet / KNX / Modbus)", "Grid-signal / price interface"],
                    ["Thermal or electric storage controller", "Optimisation / predictive control software"]],
    "Electric vehicle charging": [["EV chargers"], ["Smart charging controller"],
                                  ["Communication network (BACnet / KNX / Modbus)", "Grid-signal / price interface"],
                                  ["Optimisation / predictive control software"]],
    "Monitoring and control": [["Data platform and dashboard", "Energy meters (sub-metering)"],
                               ["Communication network (BACnet / KNX / Modbus)", "Building management system (BMS)"],
                               ["Fault detection and diagnostics software", "Occupant information display / app"],
                               ["Grid-signal / price interface", "Optimisation / predictive control software"]],
}


SERVICE_STEP = " – devices and configuration, level "


def service_items(code: str, level: int) -> list[str]:
    """Service-specific requirement per level step (dummy): e.g. 'V-3 – devices and configuration, level 2'."""
    return [f"{code}{SERVICE_STEP}{k}" for k in range(1, max(level, 0) + 1)]


def requirements_at(domain: str, level: int, code: str | None = None) -> list[str]:
    """Technical requirements needed for a service of this domain at this level (cumulative, no duplicates):
    shared domain equipment, plus the service's own items when `code` is given."""
    out: list[str] = []
    for step in DOMAIN_STEPS.get(domain, [])[:max(level, 0)]:
        out += [r for r in step if r not in out]
    return out + (service_items(code, level) if code else [])


def _service_step_price(req: str) -> tuple[float, float]:
    code, k = req.split(SERVICE_STEP)
    h = sum(map(ord, code))
    return 2 + h % 7 + int(k), 10_000 * (1 + (h + int(k)) % 4)  # dummy, deterministic per service and level


def price(req: str, floor_area_m2: float, db: str = "default") -> float:
    """Price in NOK of one requirement (only the default database exists in the draft)."""
    per_m2, fixed = _service_step_price(req) if SERVICE_STEP in req else DEFAULT_PRICES[req]
    return per_m2 * floor_area_m2 + fixed


# Annual operation and maintenance cost as a share of the purchase price (dummy): software, services and platforms
# carry licences / subscriptions; hardware needs maintenance.
OPEX_KEYWORDS = ("software", "service", "platform", "interface", "app", "configuration")
OPEX_RATE_SOFTWARE, OPEX_RATE_HARDWARE = 0.15, 0.02


def opex_rate(req: str) -> float:
    """Annual operating cost of a requirement as a fraction of its price (dummy)."""
    return OPEX_RATE_SOFTWARE if any(k in req.lower() for k in OPEX_KEYWORDS) else OPEX_RATE_HARDWARE


def annual_opex(req: str, floor_area_m2: float, db: str = "default") -> float:
    """Annual operation and maintenance cost in NOK of one requirement."""
    return opex_rate(req) * price(req, floor_area_m2, db)


def annuity_factor(years: float, rate_percent: float) -> float:
    """Present value of 1 NOK paid every year for `years` years at a discount rate (in %)."""
    r = rate_percent / 100
    return float(years) if r == 0 else (1 - (1 + r) ** -years) / r


def upgrade(domain: str, current: int, target: int, floor_area_m2: float, db: str = "default",
            code: str | None = None) -> dict:
    """Requirements to add and their cost to go from `current` to `target` (nothing if target <= current)."""
    have = set(requirements_at(domain, current, code))
    new = [r for r in requirements_at(domain, target, code) if r not in have] if target > current else []
    return {"requirements": new, "cost": sum(price(r, floor_area_m2, db) for r in new)}
