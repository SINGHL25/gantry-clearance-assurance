"""Engineering assistant.

Reads the whole project and says the thing an engineer would say in the meeting:
what is wrong, how far wrong, what the fix costs in optics and possession time,
and what is standing between the change and a signature. The priority follows the
worst unresolved item, not the last stage that ran.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .pipeline import Project, Stage, Verdict


@dataclass
class Recommendation:
    priority: str
    headline: str
    actions: List[str] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "priority": self.priority, "headline": self.headline,
            "actions": list(self.actions), "trace": list(self.trace),
            "summary": dict(self.summary),
        }


def advise(project: Project) -> Recommendation:
    before = project.before
    plan = project.plan
    fov = project.fov_after
    wp = project.workpack
    verified = project.verified

    trace: List[str] = []
    if before:
        trace.append(f"Requirement {before.required_m:.2f} m "
                     f"({project.standard.name}).")
        trace.append(f"Lowest item {before.governing_item().clearance_m:.3f} m; "
                     f"{len(before.non_conforming_lanes())} lane(s) non-conforming."
                     if before.governing_item() else "")
    if plan and plan.selection.height_m:
        trace.append(f"Spacer {plan.selection.height_m * 1000:.0f} mm selected against a "
                     f"{plan.selection.required_raise_m * 1000:.0f} mm deficit "
                     f"({plan.selection.margin_m * 1000:.0f} mm margin).")
    if fov:
        trace.append(f"Tilt window {fov.min_tilt_deg:.1f}-{fov.max_tilt_deg:.0f} deg, "
                     f"operating at {fov.operating_tilt_deg:.0f} deg.")
    if wp:
        trace.append(f"{wp.item_count} unit(s), {wp.duration_min} min, "
                     f"{len(wp.lanes_to_close)} lane closure(s).")
    if verified:
        trace.append(f"Verification survey: worst lane "
                     f"{min(l.min_clearance_m for l in verified.lanes):.3f} m.")
    trace = [t for t in trace if t]

    actions: List[str] = []
    # A failing assess stage is why the project exists; it is not a process
    # failure. What matters is whether everything downstream of it succeeded.
    failing = [s for s in project.stages
               if s.verdict is Verdict.FAIL and s.stage is not Stage.ASSESS]
    blocked = [s for s in project.stages
               if s.verdict is Verdict.BLOCKED and s.stage is not Stage.VERIFY]
    resolved = (project.released() and verified is not None and verified.conforming())

    if resolved:
        priority = "normal"
        worst = min(l.min_clearance_m for l in verified.lanes)
        if before is not None and not before.conforming():
            headline = (f"Non-conformance closed: every lane now at or above "
                        f"{worst:.3f} m against a {verified.required_m:.2f} m requirement")
            actions.append("File the verification survey as the closure evidence for the "
                           "non-conformance report.")
            if plan and plan.selection.height_m:
                actions.append(f"Record the {plan.selection.height_m * 1000:.0f} mm spacer on "
                               "the asset register so the next resurfacing assessment starts "
                               "from the corrected geometry.")
            if fov:
                actions.append(f"Tilt window is now {fov.width_deg():.1f} deg wide — note it "
                               "as a constraint before any future height change.")
        else:
            headline = (f"Structure complies: worst lane {worst:.3f} m against a "
                        f"{verified.required_m:.2f} m requirement")
            actions.append("No remediation required. Re-assess after the next resurfacing.")
    elif failing:
        first = failing[0]
        priority = "critical"
        headline = f"{first.stage.value.title()} stage fails: {first.headline}"
        for s in failing:
            actions.append(f"[{s.stage.value}] {s.headline}")
        if plan and not plan.resolves():
            actions.append("Select a taller spacer or escalate to a structural adjustment.")
        if fov and not fov.workable():
            actions.append("Reduce the spacer height or move the sensor forward of the beam "
                           "so the tilt window reopens.")
    elif blocked:
        priority = "elevated"
        headline = f"Change is not releasable: {blocked[0].headline}"
        for s in blocked:
            actions.extend(s.findings[:3])
    else:
        priority = "elevated"
        headline = "Change in progress"
        actions.append("Complete the remaining stages before release.")

    if before and not before.conforming():
        overlay_headroom = min(
            (l.min_clearance_m - before.required_m) for l in before.lanes)
        if plan and plan.after:
            after_headroom = min(
                (l.min_clearance_m - plan.after.required_m) for l in plan.after.lanes)
            if after_headroom < 0.050:
                actions.append(f"Post-fix headroom is only {after_headroom * 1000:.0f} mm: "
                               "flag the structure before the next asphalt overlay.")

    return Recommendation(priority=priority, headline=headline, actions=actions,
                          trace=trace, summary=project.as_dict())
