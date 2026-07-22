"""Scenarios.

Each one is a complete project on the same structure, changed in one meaningful
way: the site as first surveyed, the same site with an undersized spacer chosen,
the same site after an asphalt overlay has eaten the headroom, a structure whose
camber puts the problem somewhere else entirely, and a site that was already
compliant so nothing should happen at all.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .equipment import EquipmentItem, build_equipment
from .geometry import Carriageway, Gantry, standard_carriageway, standard_gantry
from .standards import ClearanceStandard, get_standard


@dataclass
class Scenario:
    name: str
    title: str
    gantry: Gantry
    carriageway: Carriageway
    items: List[EquipmentItem]
    standard: ClearanceStandard
    forced_raiser_m: Optional[float] = None
    resolve_review: bool = True
    note: str = ""


def _base(gantry: Optional[Gantry] = None,
          carriageway: Optional[Carriageway] = None):
    g = gantry or standard_gantry()
    c = carriageway or standard_carriageway()
    return g, c, build_equipment(g, c.lanes)


def as_surveyed() -> Scenario:
    """The site as first measured: two lanes short of the requirement."""
    g, c, items = _base()
    return Scenario("as_surveyed", "As surveyed", g, c, items,
                    get_standard("motorway_gantry"),
                    note="Camber and crossfall pull in opposite directions, so the two "
                         "lanes nearest the high side fall below the requirement.")


def undersized_spacer() -> Scenario:
    """An engineer overrides the sizing and picks a spacer that is too short."""
    g, c, items = _base()
    return Scenario("undersized_spacer", "Undersized spacer", g, c, items,
                    get_standard("motorway_gantry"), forced_raiser_m=0.100,
                    note="A 100 mm spacer looks generous against a 139 mm deficit until "
                         "you check it: the worst lane is still short and the change "
                         "cannot be released.")


def future_overlay() -> Scenario:
    """The same structure after 40 mm of asphalt has been laid beneath it."""
    g, c, items = _base()
    c.overlay_m = 0.040
    return Scenario("future_overlay", "After resurfacing", g, c, items,
                    get_standard("motorway_gantry"),
                    note="Forty millimetres of new asphalt raises the road under every "
                         "lane and takes the same amount straight off the clearance.")


def overlay_reserved() -> Scenario:
    """The stricter standard that reserves headroom for resurfacing up front."""
    g, c, items = _base()
    return Scenario("overlay_reserved", "Overlay reserved", g, c, items,
                    get_standard("motorway_gantry_with_overlay"),
                    note="Carrying the resurfacing reserve and survey tolerance in the "
                         "requirement raises the bar to 6.675 m and pulls a third lane "
                         "into the problem.")


def flatter_gantry() -> Scenario:
    """A structure built with less camber: the problem moves to the middle."""
    g = Gantry(span_m=28.2, soffit_at_supports_m=7.10, camber_m=0.010)
    c = standard_carriageway()
    items = build_equipment(g, c.lanes)
    return Scenario("flatter_gantry", "Minimal camber", g, c, items,
                    get_standard("motorway_gantry"),
                    note="With the camber almost gone, crossfall alone governs and the "
                         "shortfall marches across the carriageway from the high side.")


def already_compliant() -> Scenario:
    """A structure that meets the requirement: the process should do nothing."""
    g = Gantry(span_m=28.2, soffit_at_supports_m=7.30, camber_m=0.09)
    c = standard_carriageway()
    items = build_equipment(g, c.lanes)
    return Scenario("already_compliant", "Already compliant", g, c, items,
                    get_standard("motorway_gantry"),
                    note="Nothing is short, so no spacer is sized and no site work is "
                         "generated. The process should stop, not invent work.")


SCENARIOS: Dict[str, Callable[[], Scenario]] = {
    "as_surveyed": as_surveyed,
    "undersized_spacer": undersized_spacer,
    "future_overlay": future_overlay,
    "overlay_reserved": overlay_reserved,
    "flatter_gantry": flatter_gantry,
    "already_compliant": already_compliant,
}
baseline = as_surveyed


def apply_scenario(name: str) -> Scenario:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario: {name}")
    return copy.deepcopy(SCENARIOS[name]())
