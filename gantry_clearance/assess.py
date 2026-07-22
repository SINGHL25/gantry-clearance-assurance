"""The assessment.

For every item, at its own transverse position: how far is its underside above
the road directly below it, and does that meet the requirement. Items that clear
comfortably are conforming; items inside a small watch band are marginal — worth
knowing about before the next resurfacing eats the difference; anything below the
requirement is non-conforming and carries a deficit.

The two answers that matter downstream are the *governing item* (the single
lowest thing on the structure, which is what any remediation has to chase) and
the per-lane picture, because that is what a road authority asks for first: not
"does the gantry comply" but "what is the clearance in each lane".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .equipment import EquipmentItem, EquipmentType
from .geometry import Carriageway, Gantry
from .standards import ClearanceStandard

MARGINAL_BAND_M = 0.050   # within this above the requirement: worth watching


class Status(str, Enum):
    CONFORMING = "conforming"
    MARGINAL = "marginal"
    NON_CONFORMING = "non_conforming"


@dataclass
class ItemAssessment:
    item: EquipmentItem
    road_level_m: float
    soffit_level_m: float
    underside_level_m: float
    clearance_m: float
    required_m: float
    status: Status

    def deficit_m(self) -> float:
        """How far short of the requirement, or zero if it meets it."""
        return max(0.0, self.required_m - self.clearance_m)

    def margin_m(self) -> float:
        return self.clearance_m - self.required_m

    def as_dict(self) -> dict:
        return {
            **self.item.as_dict(),
            "road_level_m": round(self.road_level_m, 3),
            "underside_level_m": round(self.underside_level_m, 3),
            "clearance_m": round(self.clearance_m, 3),
            "required_m": round(self.required_m, 3),
            "margin_mm": round(self.margin_m() * 1000, 0),
            "deficit_mm": round(self.deficit_m() * 1000, 0),
            "status": self.status.value,
        }


@dataclass
class LaneAssessment:
    lane: str
    min_clearance_m: float
    required_m: float
    status: Status
    governing_item_id: str
    governing_kind: str

    def deficit_m(self) -> float:
        return max(0.0, self.required_m - self.min_clearance_m)

    def as_dict(self) -> dict:
        return {
            "lane": self.lane, "min_clearance_m": round(self.min_clearance_m, 3),
            "required_m": round(self.required_m, 3), "status": self.status.value,
            "deficit_mm": round(self.deficit_m() * 1000, 0),
            "governing_item_id": self.governing_item_id,
            "governing_kind": self.governing_kind,
        }


@dataclass
class Assessment:
    items: List[ItemAssessment] = field(default_factory=list)
    lanes: List[LaneAssessment] = field(default_factory=list)
    required_m: float = 0.0
    standard_name: str = ""

    def conforming(self) -> bool:
        return not any(i.status is Status.NON_CONFORMING for i in self.items)

    def non_conforming_items(self) -> List[ItemAssessment]:
        return [i for i in self.items if i.status is Status.NON_CONFORMING]

    def non_conforming_lanes(self) -> List[LaneAssessment]:
        return [l for l in self.lanes if l.status is Status.NON_CONFORMING]

    def governing_item(self) -> Optional[ItemAssessment]:
        """The single lowest item on the structure."""
        return min(self.items, key=lambda i: i.clearance_m) if self.items else None

    def worst_deficit_m(self) -> float:
        return max((i.deficit_m() for i in self.items), default=0.0)

    def required_raise_m(self) -> float:
        """How far the worst item has to come up to meet the requirement."""
        return self.worst_deficit_m()

    def affected_kinds(self) -> List[str]:
        return sorted({i.item.kind.value for i in self.non_conforming_items()})

    def as_dict(self) -> dict:
        return {
            "standard": self.standard_name, "required_m": round(self.required_m, 3),
            "conforming": self.conforming(),
            "worst_deficit_mm": round(self.worst_deficit_m() * 1000, 0),
            "required_raise_mm": round(self.required_raise_m() * 1000, 0),
            "affected_kinds": self.affected_kinds(),
            "non_conforming_items": len(self.non_conforming_items()),
            "lanes": [l.as_dict() for l in self.lanes],
            "items": [i.as_dict() for i in self.items],
        }


def _status(clearance: float, required: float) -> Status:
    if clearance < required:
        return Status.NON_CONFORMING
    if clearance < required + MARGINAL_BAND_M:
        return Status.MARGINAL
    return Status.CONFORMING


def assess(gantry: Gantry, carriageway: Carriageway, items: List[EquipmentItem],
           standard: ClearanceStandard) -> Assessment:
    required = standard.required_m()
    result = Assessment(required_m=required, standard_name=standard.name)

    for item in items:
        soffit = gantry.soffit_level(item.offset_m)
        road = carriageway.surface_level(item.offset_m)
        underside = soffit - item.drop_m()
        clearance = underside - road
        result.items.append(ItemAssessment(
            item=item, road_level_m=road, soffit_level_m=soffit,
            underside_level_m=underside, clearance_m=clearance,
            required_m=required, status=_status(clearance, required)))

    by_lane: Dict[str, List[ItemAssessment]] = {}
    for ia in result.items:
        by_lane.setdefault(ia.item.lane, []).append(ia)
    for lane in sorted(by_lane):
        worst = min(by_lane[lane], key=lambda i: i.clearance_m)
        result.lanes.append(LaneAssessment(
            lane=lane, min_clearance_m=worst.clearance_m, required_m=required,
            status=worst.status, governing_item_id=worst.item.item_id,
            governing_kind=worst.item.kind.value))

    return result
