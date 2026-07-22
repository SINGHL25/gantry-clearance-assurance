"""Geometry of the gantry and the carriageway beneath it.

Vertical clearance is never a single number. The girder is cambered, so its
underside is highest at mid-span and drops toward the columns. The carriageway
has crossfall for drainage, so the road surface is highest on one side. Those two
curves run in opposite directions, which means the tightest gap is usually near
one column — not in the middle where anyone would think to measure.

Everything here is referenced to a local datum: transverse offset in metres from
the left column, and level in metres above the left carriageway edge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

MODULE_LENGTH_M = 1.17     # the girder is built from repeating modules


@dataclass(frozen=True)
class Lane:
    name: str
    left_m: float
    width_m: float

    def centre_m(self) -> float:
        return self.left_m + self.width_m / 2.0

    def right_m(self) -> float:
        return self.left_m + self.width_m


@dataclass
class Carriageway:
    left_edge_m: float          # transverse offset of the left carriageway edge
    lanes: List[Lane]
    crossfall: float = 0.025    # fall per metre, left edge high
    left_edge_level_m: float = 0.0
    overlay_m: float = 0.0      # asphalt added since the original survey

    def right_edge_m(self) -> float:
        return self.lanes[-1].right_m() if self.lanes else self.left_edge_m

    def width_m(self) -> float:
        return self.right_edge_m() - self.left_edge_m

    def surface_level(self, offset_m: float) -> float:
        """Road surface level at a transverse offset, including any overlay."""
        drop = self.crossfall * (offset_m - self.left_edge_m)
        return self.left_edge_level_m - drop + self.overlay_m


@dataclass
class Gantry:
    span_m: float                     # centre-to-centre of the columns
    soffit_at_supports_m: float       # underside of the girder floor at a column
    camber_m: float = 0.09            # net upward rise at mid-span
    module_length_m: float = MODULE_LENGTH_M

    def mid_span_m(self) -> float:
        return self.span_m / 2.0

    def soffit_level(self, offset_m: float) -> float:
        """Underside of the girder floor, following the parabolic camber."""
        half = self.span_m / 2.0
        if half <= 0:
            return self.soffit_at_supports_m
        t = (offset_m - half) / half
        return self.soffit_at_supports_m + self.camber_m * max(0.0, 1.0 - t * t)

    def module_index(self, offset_m: float) -> int:
        return int(offset_m // self.module_length_m)

    def module_centres(self) -> List[float]:
        n = int(self.span_m // self.module_length_m)
        return [(i + 0.5) * self.module_length_m for i in range(n)]


def standard_carriageway(left_edge_m: float = 7.0, lane_count: int = 4,
                         lane_width_m: float = 3.5,
                         crossfall: float = 0.025) -> Carriageway:
    lanes = [Lane(f"L{i + 1}", left_edge_m + i * lane_width_m, lane_width_m)
             for i in range(lane_count)]
    return Carriageway(left_edge_m=left_edge_m, lanes=lanes, crossfall=crossfall)


def standard_gantry() -> Gantry:
    """A four-lane tolling gantry: 28.2 m between columns, modest precamber."""
    return Gantry(span_m=28.2, soffit_at_supports_m=7.085, camber_m=0.09)
