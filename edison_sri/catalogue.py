"""Dummy service catalogue and cost matrices.

DUMMY DATA – placeholders to drive the draft app. Replace with the real
Method A/B catalogue (EC calculation sheet / SRI Norsk) and EDISON cost data.
"""
from dataclasses import dataclass, field

# Default key-functionality-free simplification: one weight per domain.
DOMAIN_WEIGHTS = {
    "Heating": 0.25,
    "Domestic hot water": 0.10,
    "Ventilation": 0.15,
    "Lighting": 0.10,
    "Electricity": 0.15,
    "EV charging": 0.10,
    "Monitoring and control": 0.15,
}


@dataclass(frozen=True)
class Service:
    code: str
    name: str
    domain: str
    max_level: int
    # cost_per_m2[from_level][to_level] in NOK/m² (dummy). Missing keys = not possible.
    cost_per_m2: dict = field(default_factory=dict)
    fixed_cost: float = 0.0  # NOK, one-off per upgrade (dummy)


def _matrix(step_costs, max_level):
    """Build an upper-triangular cost matrix from step costs.

    A direct jump is a bit cheaper than the sum of single steps (dummy 10 %),
    to mimic 'level by level ≠ direct' from the cost-mapping slide.
    """
    m = {}
    for a in range(max_level + 1):
        m[a] = {}
        for b in range(a + 1, max_level + 1):
            s = sum(step_costs[a:b])
            m[a][b] = round(s * (0.9 if b - a > 1 else 1.0), 1)
    return m


SERVICES = [
    Service("H-1a", "Heat emission control", "Heating", 4, _matrix([60, 45, 80, 120], 4), 15_000),
    Service("H-3", "Heat generator control", "Heating", 3, _matrix([30, 50, 70], 3), 25_000),
    Service("DHW-1a", "Storage charging control", "Domestic hot water", 3, _matrix([10, 20, 35], 3), 8_000),
    Service("V-1a", "Supply air flow control", "Ventilation", 4, _matrix([40, 60, 90, 110], 4), 20_000),
    Service("L-1a", "Occupancy control for lighting", "Lighting", 3, _matrix([25, 35, 50], 3), 10_000),
    Service("E-2", "Reporting on electricity", "Electricity", 3, _matrix([5, 10, 20], 3), 12_000),
    Service("EV-15", "EV charging grid balancing", "EV charging", 3, _matrix([20, 40, 60], 3), 30_000),
    Service("MC-25", "Smart grid integration", "Monitoring and control", 2, _matrix([50, 90], 2), 40_000),
]

SERVICE_BY_CODE = {s.code: s for s in SERVICES}

BUILDING_CATEGORIES = [
    "Office", "School", "Kindergarten", "Hospital", "Hotel", "Shop", "Apartment block", "Single-family house",
]

DEFAULT_ASSESSMENT = {
    "building": {"name": "Demo office building", "category": "Office", "floor_area_m2": 5000, "method": "B"},
    "levels": {"H-1a": 1, "H-3": 1, "DHW-1a": 0, "V-1a": 1, "L-1a": 0, "E-2": 1, "EV-15": 0, "MC-25": 0},
}

# Default objectives & constraints: see edison_sri/parameters.py (defaults())
