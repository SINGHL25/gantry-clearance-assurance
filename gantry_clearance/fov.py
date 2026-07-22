"""Field-of-view validation.

Raising a camera to fix a clearance problem moves it up behind the steelwork it
hangs from. That is the trade nobody spots on a section drawing: the structure
gets legal, and the camera starts looking at a beam.

The check is geometric. A downward-looking sensor is clipped by the beam edge in
front of it whenever its upper field-of-view ray still passes above that edge —
which happens at shallow tilt angles. Tilt it down further and the view clears.
So there is a *minimum* tilt set by the steelwork and a *maximum* tilt set by the
mount and the aim point, and the sensor has to live between them. Adding a spacer
raises the floor of that window without touching the ceiling, so the window
narrows — and the job of this module is to say by how much, and whether the
operating angle is still inside it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

HALF_FOV_DEG = 12.0          # half the vertical field of view
BEAM_OFFSET_M = 2.20         # horizontal distance forward to the obstructing beam edge
BEAM_DROP_M = 0.31           # how far that edge sits below the sensor, as installed
MAX_TILT_DEG = 30.0          # ceiling set by the mount and the aim point
OPERATING_TILT_DEG = 26.0    # where the sensor is actually set
MIN_WINDOW_DEG = 2.0         # a window narrower than this is not workable


@dataclass
class FovWindow:
    min_tilt_deg: float
    max_tilt_deg: float
    operating_tilt_deg: float
    raise_m: float
    obstructed: bool
    margin_deg: float
    reasons: List[str] = field(default_factory=list)

    def width_deg(self) -> float:
        return max(0.0, self.max_tilt_deg - self.min_tilt_deg)

    def workable(self) -> bool:
        return (not self.obstructed) and self.width_deg() >= MIN_WINDOW_DEG

    def as_dict(self) -> dict:
        return {
            "min_tilt_deg": round(self.min_tilt_deg, 1),
            "max_tilt_deg": round(self.max_tilt_deg, 1),
            "operating_tilt_deg": round(self.operating_tilt_deg, 1),
            "raise_mm": round(self.raise_m * 1000, 0),
            "window_deg": round(self.width_deg(), 1),
            "margin_deg": round(self.margin_deg, 1),
            "obstructed": self.obstructed, "workable": self.workable(),
            "reasons": list(self.reasons),
        }


def minimum_tilt_deg(raise_m: float = 0.0, half_fov_deg: float = HALF_FOV_DEG,
                     beam_offset_m: float = BEAM_OFFSET_M,
                     beam_drop_m: float = BEAM_DROP_M) -> float:
    """Shallowest tilt at which the upper field-of-view ray clears the beam edge.

    Raising the sensor increases its height above that edge, so the ray has to be
    steeper to get past it.
    """
    drop = beam_drop_m + raise_m
    return half_fov_deg + math.degrees(math.atan2(drop, beam_offset_m))


def evaluate_fov(raise_m: float = 0.0,
                 operating_tilt_deg: float = OPERATING_TILT_DEG,
                 max_tilt_deg: float = MAX_TILT_DEG,
                 half_fov_deg: float = HALF_FOV_DEG,
                 beam_offset_m: float = BEAM_OFFSET_M,
                 beam_drop_m: float = BEAM_DROP_M) -> FovWindow:
    min_tilt = minimum_tilt_deg(raise_m, half_fov_deg, beam_offset_m, beam_drop_m)
    obstructed = operating_tilt_deg < min_tilt
    margin = operating_tilt_deg - min_tilt

    reasons = [
        f"beam edge {beam_offset_m:.2f} m forward and "
        f"{(beam_drop_m + raise_m) * 1000:.0f} mm below the sensor",
        f"half field of view {half_fov_deg:.0f} deg gives a {min_tilt:.1f} deg minimum tilt",
    ]
    if raise_m > 0:
        base = minimum_tilt_deg(0.0, half_fov_deg, beam_offset_m, beam_drop_m)
        reasons.append(f"spacer of {raise_m * 1000:.0f} mm lifts the minimum tilt from "
                       f"{base:.1f} to {min_tilt:.1f} deg")
    if obstructed:
        reasons.append(f"operating tilt {operating_tilt_deg:.0f} deg is below the minimum: "
                       "the beam clips the field of view")
    else:
        reasons.append(f"operating tilt {operating_tilt_deg:.0f} deg clears the beam by "
                       f"{margin:.1f} deg")
    window = max_tilt_deg - min_tilt
    if 0 < window < MIN_WINDOW_DEG:
        reasons.append(f"usable window is only {window:.1f} deg: too tight to commission reliably")

    return FovWindow(min_tilt_deg=min_tilt, max_tilt_deg=max_tilt_deg,
                     operating_tilt_deg=operating_tilt_deg, raise_m=raise_m,
                     obstructed=obstructed, margin_deg=margin, reasons=reasons)
