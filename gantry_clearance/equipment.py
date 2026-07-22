"""The equipment hanging under the girder.

A tolling gantry is not a bare beam. Cameras, illuminators, transceivers and
classification sensors all hang below the girder floor, each at its own drop.
Clearance is governed by whichever of them reaches lowest — so the assessment has
to be item by item, not structure by structure. In practice one item type is
almost always the culprit, and finding out which one is the whole point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

from .geometry import Gantry, Lane


class EquipmentType(str, Enum):
    VR_SENSOR = "vr_sensor"                 # registration camera (front / rear)
    VR_ILLUMINATOR = "vr_illuminator"       # infrared illumination for the camera
    DSRC_TRANSCEIVER = "dsrc_transceiver"   # tag reader
    VDC_SENSOR = "vdc_sensor"               # detection and classification


# Nominal drop of each item below the girder floor soffit, in metres.
NOMINAL_DROP_M: Dict[EquipmentType, float] = {
    EquipmentType.VR_SENSOR: 0.72,
    EquipmentType.VR_ILLUMINATOR: 0.42,
    EquipmentType.DSRC_TRANSCEIVER: 0.38,
    EquipmentType.VDC_SENSOR: 0.30,
}

LABEL: Dict[EquipmentType, str] = {
    EquipmentType.VR_SENSOR: "VR sensor",
    EquipmentType.VR_ILLUMINATOR: "VR illuminator",
    EquipmentType.DSRC_TRANSCEIVER: "DSRC transceiver",
    EquipmentType.VDC_SENSOR: "VDC sensor",
}

# Which items sit in a liftable frame, and can therefore be raised on a spacer
# without touching the girder itself.
FRAME_MOUNTED = {EquipmentType.VR_SENSOR}


@dataclass
class EquipmentItem:
    item_id: str
    kind: EquipmentType
    offset_m: float          # transverse offset from the left column
    lane: str                # lane it serves
    raise_m: float = 0.0     # spacer fitted under the mount, if any

    def drop_m(self) -> float:
        """How far the underside of this item sits below the girder soffit."""
        return NOMINAL_DROP_M[self.kind] - self.raise_m

    def frame_mounted(self) -> bool:
        return self.kind in FRAME_MOUNTED

    def label(self) -> str:
        return LABEL[self.kind]

    def as_dict(self) -> dict:
        return {
            "item_id": self.item_id, "kind": self.kind.value, "label": self.label(),
            "offset_m": round(self.offset_m, 3), "lane": self.lane,
            "raise_mm": round(self.raise_m * 1000, 0),
            "drop_m": round(self.drop_m(), 3),
        }


def build_equipment(gantry: Gantry, lanes: List[Lane]) -> List[EquipmentItem]:
    """One of each item type per lane, placed on the nearest module centre.

    Real gantries vary the mix module by module; this lays out a representative
    set so every lane has a full complement to assess.
    """
    items: List[EquipmentItem] = []
    for lane in lanes:
        centre = lane.centre_m()
        for n, kind in enumerate(EquipmentType):
            # spread the four items across the lane so they read separately
            offset = centre + (n - 1.5) * 0.55
            items.append(EquipmentItem(
                item_id=f"{lane.name}-{kind.value}", kind=kind,
                offset_m=offset, lane=lane.name))
    return items
