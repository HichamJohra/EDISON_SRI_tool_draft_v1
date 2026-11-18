"""Technical requirements of each service level and their prices (cost databases).

DUMMY MODEL – placeholder until the EDISON requirement library exists: each functionality level needs the
requirements of the level below plus a few typical items for its domain. Prices are invented round numbers.
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


def requirements_at(domain: str, level: int) -> list[str]:
    """Technical requirements needed for a service of this domain at this level (cumulative, no duplicates)."""
    out: list[str] = []
    for step in DOMAIN_STEPS.get(domain, [])[:max(level, 0)]:
        out += [r for r in step if r not in out]
    return out


def price(req: str, floor_area_m2: float, db: str = "default") -> float:
    per_m2, fixed = DEFAULT_PRICES[req]  # only the default database exists in the draft
    return per_m2 * floor_area_m2 + fixed


def upgrade(domain: str, current: int, target: int, floor_area_m2: float, db: str = "default") -> dict:
    """Requirements to add and their cost to go from `current` to `target` (nothing if target <= current)."""
    have = set(requirements_at(domain, current))
    new = [r for r in requirements_at(domain, target) if r not in have] if target > current else []
    return {"requirements": new, "cost": sum(price(r, floor_area_m2, db) for r in new)}
