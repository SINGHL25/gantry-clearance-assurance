"""Clearance standards.

The headline number in a standard is never the number you build to. A base
requirement protects the design vehicle; on top of it sit allowances for the
asphalt that will be laid over the life of the road, for the tolerance of the
survey that measured it, and for whatever margin the asset owner wants between
"compliant" and "arguing about it later".

Those four numbers are kept separate here rather than pre-added, because when a
structure fails by 40 mm the first question asked is always *which* of them the
40 mm came out of.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ClearanceStandard:
    name: str
    authority: str
    base_m: float               # protects the design vehicle envelope
    overlay_allowance_m: float  # future resurfacing
    survey_tolerance_m: float   # measurement uncertainty
    operator_margin_m: float    # asset owner's own buffer
    note: str = ""

    def required_m(self) -> float:
        return (self.base_m + self.overlay_allowance_m
                + self.survey_tolerance_m + self.operator_margin_m)

    def breakdown(self) -> Dict[str, float]:
        return {
            "base": self.base_m, "overlay_allowance": self.overlay_allowance_m,
            "survey_tolerance": self.survey_tolerance_m,
            "operator_margin": self.operator_margin_m,
            "required": round(self.required_m(), 3),
        }

    def as_dict(self) -> dict:
        return {"name": self.name, "authority": self.authority,
                "note": self.note, **self.breakdown()}


# Representative profiles. The motorway gantry profile is the one that governs a
# tolling point over a high-speed carriageway: a 6.5 m base with a 100 mm owner
# margin, giving the 6.6 m that such structures are commonly held to.
STANDARDS: Dict[str, ClearanceStandard] = {
    "motorway_gantry": ClearanceStandard(
        name="Overhead gantry over motorway", authority="road authority",
        base_m=6.500, overlay_allowance_m=0.000, survey_tolerance_m=0.000,
        operator_margin_m=0.100,
        note="6.5 m base plus a 100 mm owner margin."),
    "motorway_gantry_with_overlay": ClearanceStandard(
        name="Overhead gantry, future overlay reserved", authority="road authority",
        base_m=6.500, overlay_allowance_m=0.050, survey_tolerance_m=0.025,
        operator_margin_m=0.100,
        note="Adds a 50 mm resurfacing reserve and 25 mm survey tolerance."),
    "bridge_over_road": ClearanceStandard(
        name="Bridge superstructure over road", authority="road authority",
        base_m=5.400, overlay_allowance_m=0.100, survey_tolerance_m=0.025,
        operator_margin_m=0.000,
        note="Lower base than a gantry; overlay reserve carried explicitly."),
    "sign_structure": ClearanceStandard(
        name="Sign gantry over motorway", authority="road authority",
        base_m=6.100, overlay_allowance_m=0.050, survey_tolerance_m=0.025,
        operator_margin_m=0.050,
        note="Signals and signage mounted overhead."),
}

DEFAULT_STANDARD = "motorway_gantry"


def get_standard(key: str = DEFAULT_STANDARD) -> ClearanceStandard:
    if key not in STANDARDS:
        raise KeyError(f"unknown standard: {key}")
    return STANDARDS[key]
