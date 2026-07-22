"""The work package.

The output that actually goes to site. How many spacers, which lanes have to be
shut and for how long, and the ordered steps — because on a gantry over a live
motorway the sequence is the safety case, not a formality.

Duration is built from the work rather than guessed: a fixed possession overhead
for setting up and removing traffic control, plus per-item time for the lift,
the fit and the re-alignment that follows it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .assess import Assessment
from .remediation import RemediationPlan

SETUP_MIN = 45          # traffic control on
TEARDOWN_MIN = 30       # traffic control off
PER_ITEM_FIT_MIN = 25   # disconnect, lift, fit spacer, remount
PER_ITEM_ALIGN_MIN = 15 # re-aim and verify
CREW_SIZE = 4
NIGHT_WINDOW_MIN = 360  # a standard night possession


@dataclass
class WorkStep:
    order: int
    title: str
    detail: str
    hold: bool = False       # a step that cannot be passed without sign-off

    def as_dict(self) -> dict:
        return {"order": self.order, "title": self.title,
                "detail": self.detail, "hold": self.hold}


@dataclass
class WorkPackage:
    steps: List[WorkStep] = field(default_factory=list)
    lanes_to_close: List[str] = field(default_factory=list)
    item_count: int = 0
    duration_min: int = 0
    crew: int = CREW_SIZE
    night_shifts: int = 1
    notes: List[str] = field(default_factory=list)

    def fits_one_shift(self) -> bool:
        return self.duration_min <= NIGHT_WINDOW_MIN

    def as_dict(self) -> dict:
        return {
            "lanes_to_close": list(self.lanes_to_close),
            "item_count": self.item_count, "duration_min": self.duration_min,
            "duration_h": round(self.duration_min / 60.0, 1),
            "crew": self.crew, "night_shifts": self.night_shifts,
            "fits_one_shift": self.fits_one_shift(),
            "steps": [s.as_dict() for s in self.steps],
            "notes": list(self.notes),
        }


def build_work_package(plan: RemediationPlan,
                       assessment: Assessment) -> WorkPackage:
    items = len(plan.affected_item_ids)
    lanes = sorted({item_id.split("-")[0] for item_id in plan.affected_item_ids})

    work_min = items * (PER_ITEM_FIT_MIN + PER_ITEM_ALIGN_MIN)
    duration = SETUP_MIN + work_min + TEARDOWN_MIN
    shifts = max(1, -(-duration // NIGHT_WINDOW_MIN))   # ceiling division

    height_mm = plan.selection.height_m * 1000
    steps = [
        WorkStep(1, "Confirm approvals in place",
                 "Certified drawings, non-conformance report and traffic management "
                 "agreement all closed out before mobilising.", hold=True),
        WorkStep(2, "Establish traffic management",
                 f"Close {', '.join(lanes) if lanes else 'the affected lanes'} under the "
                 "agreed night possession; gantry access rules apply throughout."),
        WorkStep(3, "Set the tolling system to maintenance mode",
                 "Suspend live transactions for the affected lanes so no passage is lost."),
        WorkStep(4, "Isolate power to the affected units",
                 "Lock off and prove dead before any disconnection."),
        WorkStep(5, "Disconnect and lift the units",
                 "Disconnect cabling and lift each unit to the girder floor. Cabling is "
                 "reused unchanged — no electrical modification forms part of this work."),
        WorkStep(6, f"Fit the {height_mm:.0f} mm spacers",
                 "Fix each spacer between the girder and the equipment frame. No drilling "
                 "and no welding, so the corrosion protection is undisturbed."),
        WorkStep(7, "Remount and re-aim",
                 "Remount each frame on its spacer and re-aim to the surveyed aim point; "
                 "verify the tilt sits inside the permitted window."),
        WorkStep(8, "Reconnect, energise and return to service",
                 "Reconnect cabling, restore power, return the system to operational mode "
                 "and confirm passages are being captured."),
        WorkStep(9, "Verification survey",
                 "Re-survey the raised units and confirm every lane now meets the "
                 "requirement. This is the evidence that closes the non-conformance.",
                 hold=True),
    ]

    notes: List[str] = []
    if items == 0:
        notes.append("No items require raising; no site work is generated.")
    else:
        notes.append(f"{items} unit(s) across {len(lanes)} lane(s) receive a "
                     f"{height_mm:.0f} mm spacer.")
    if duration > NIGHT_WINDOW_MIN:
        notes.append(f"Estimated {duration} min exceeds a single {NIGHT_WINDOW_MIN} min "
                     f"possession: plan {shifts} shifts.")
    else:
        notes.append(f"Estimated {duration} min fits inside a single night possession.")
    notes.append("Lane closures are required: the work is directly over the running lanes.")

    return WorkPackage(steps=steps, lanes_to_close=lanes, item_count=items,
                       duration_min=duration, night_shifts=shifts, notes=notes)
