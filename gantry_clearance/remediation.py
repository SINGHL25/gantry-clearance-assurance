"""Remediation.

The cheapest fix for an overhead clearance problem is almost never to move the
structure. It is to move whatever hangs lowest off it. A spacer — a *raiser* —
goes between the equipment frame and the girder, lifting only the offending items
and leaving the structure, the cabling and the maintenance routine untouched.

Sizing it is a catalogue problem, not a design problem: pick the smallest
standard height that clears the worst deficit with a sensible margin. Anything
larger is wasted headroom that eats into sensor geometry; anything smaller leaves
a lane still non-conforming, which is the one outcome nobody can sign.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import List, Optional

from .assess import Assessment, Status, assess
from .equipment import EquipmentItem, EquipmentType
from .geometry import Carriageway, Gantry
from .standards import ClearanceStandard

# Standard spacer heights held in stock, in metres.
RAISER_CATALOGUE_M: List[float] = [0.060, 0.100, 0.140, 0.180, 0.220, 0.260]

SIZING_MARGIN_M = 0.030   # headroom demanded above the bare deficit


@dataclass
class RaiserSelection:
    height_m: float
    required_raise_m: float
    margin_m: float
    from_catalogue: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            "height_mm": round(self.height_m * 1000, 0),
            "required_raise_mm": round(self.required_raise_m * 1000, 0),
            "margin_mm": round(self.margin_m * 1000, 0),
            "from_catalogue": self.from_catalogue, "reason": self.reason,
        }


@dataclass
class RemediationPlan:
    selection: RaiserSelection
    affected_item_ids: List[str] = field(default_factory=list)
    affected_kind: Optional[str] = None
    before: Optional[Assessment] = None
    after: Optional[Assessment] = None
    notes: List[str] = field(default_factory=list)

    def resolves(self) -> bool:
        return self.after is not None and self.after.conforming()

    def as_dict(self) -> dict:
        return {
            "selection": self.selection.as_dict(),
            "affected_items": len(self.affected_item_ids),
            "affected_kind": self.affected_kind,
            "resolves": self.resolves(),
            "before_worst_deficit_mm": round(self.before.worst_deficit_m() * 1000, 0) if self.before else None,
            "after_worst_deficit_mm": round(self.after.worst_deficit_m() * 1000, 0) if self.after else None,
            "notes": list(self.notes),
        }


def select_raiser(required_raise_m: float,
                  catalogue: Optional[List[float]] = None,
                  margin_m: float = SIZING_MARGIN_M) -> RaiserSelection:
    """Smallest catalogue height that covers the deficit plus a working margin."""
    catalogue = catalogue if catalogue is not None else RAISER_CATALOGUE_M
    target = required_raise_m + margin_m
    for h in sorted(catalogue):
        if h >= target:
            return RaiserSelection(
                height_m=h, required_raise_m=required_raise_m,
                margin_m=h - required_raise_m, from_catalogue=True,
                reason=f"smallest stock spacer clearing {required_raise_m * 1000:.0f} mm "
                       f"deficit plus {margin_m * 1000:.0f} mm margin")
    tallest = max(catalogue)
    return RaiserSelection(
        height_m=tallest, required_raise_m=required_raise_m,
        margin_m=tallest - required_raise_m, from_catalogue=False,
        reason=f"deficit exceeds the tallest stock spacer ({tallest * 1000:.0f} mm): "
               f"a bespoke spacer or a structural adjustment is required")


def plan_remediation(gantry: Gantry, carriageway: Carriageway,
                     items: List[EquipmentItem], standard: ClearanceStandard,
                     before: Optional[Assessment] = None,
                     forced_height_m: Optional[float] = None) -> RemediationPlan:
    """Size a spacer, apply it to the frame-mounted offenders, and re-assess."""
    before = before or assess(gantry, carriageway, items, standard)
    notes: List[str] = []

    if before.conforming():
        selection = RaiserSelection(0.0, 0.0, 0.0, True, "already conforming: no spacer required")
        return RemediationPlan(selection=selection, before=before, after=before,
                               notes=["No remediation required."])

    if forced_height_m is None:
        selection = select_raiser(before.required_raise_m())
    else:
        selection = RaiserSelection(
            height_m=forced_height_m, required_raise_m=before.required_raise_m(),
            margin_m=forced_height_m - before.required_raise_m(),
            from_catalogue=forced_height_m in RAISER_CATALOGUE_M,
            reason="height specified by the engineer")

    # The governing item type is what gets raised; everything else is left alone.
    offenders = before.non_conforming_items()
    governing_kind = min(before.items, key=lambda i: i.clearance_m).item.kind
    liftable = [ia for ia in offenders if ia.item.frame_mounted()]
    not_liftable = [ia for ia in offenders if not ia.item.frame_mounted()]
    if not_liftable:
        notes.append(f"{len(not_liftable)} non-conforming item(s) are beam-mounted and "
                     "cannot be raised on a spacer: escalate to a structural change.")

    # Raise every item of the governing type, not just the ones that failed, so
    # the installation stays uniform across the gantry.
    raised = copy.deepcopy(items)
    affected: List[str] = []
    for item in raised:
        if item.kind is governing_kind and item.frame_mounted():
            item.raise_m += selection.height_m
            affected.append(item.item_id)

    after = assess(gantry, carriageway, raised, standard)
    if after.conforming():
        notes.append(f"All lanes conform after fitting a {selection.height_m * 1000:.0f} mm spacer.")
    else:
        notes.append(f"{len(after.non_conforming_items())} item(s) still non-conforming: "
                     "the selected spacer is undersized.")

    return RemediationPlan(selection=selection, affected_item_ids=affected,
                           affected_kind=governing_kind.value, before=before,
                           after=after, notes=notes)


def apply_raise(items: List[EquipmentItem], kind: EquipmentType,
                height_m: float) -> List[EquipmentItem]:
    """Return a copy of the equipment with a spacer fitted to one item type."""
    out = copy.deepcopy(items)
    for item in out:
        if item.kind is kind and item.frame_mounted():
            item.raise_m += height_m
    return out
