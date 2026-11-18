"""Placeholder SRI scoring.

DUMMY METHOD – a weighted mean of normalised functionality levels per domain.
It is NOT the regulation's method (impact scores per criterion, key
functionalities, ratio of weighted sums). Swap in the real engine later and
keep the same function signatures so the pages keep working.
"""
from .catalogue import DOMAIN_WEIGHTS, SERVICES

# Annex VIII class limits (lower bounds, %)
CLASS_LIMITS = [("A", 90), ("B", 80), ("C", 65), ("D", 50), ("E", 35), ("F", 20), ("G", 0)]


def sri_score(levels: dict) -> float:
    """Return a dummy SRI in % from {service_code: level}."""
    num = den = 0.0
    for domain, w in DOMAIN_WEIGHTS.items():
        services = [s for s in SERVICES if s.domain == domain]
        if not services:
            continue
        ratio = sum(levels.get(s.code, 0) / s.max_level for s in services) / len(services)
        num += w * ratio
        den += w
    return round(100 * num / den, 2) if den else 0.0


def sri_class(score: float) -> str:
    for cls, lower in CLASS_LIMITS:
        if score >= lower:
            return cls
    return "G"


def class_lower_bound(cls: str) -> float:
    return dict(CLASS_LIMITS)[cls]
