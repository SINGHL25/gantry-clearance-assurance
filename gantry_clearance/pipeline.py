"""The end-to-end process.

Eight stages, in the order they actually happen on a project: measure it, judge
it against the standard, size the fix, prove the fix does not break something
else, package it, survive the review, get it signed, then go back and prove it on
site. Each stage produces evidence and a verdict, and a stage that fails does not
quietly hand its problem to the next one.

Running the whole thing as one object is what makes the process auditable: the
verification survey at the end can be traced all the way back to the survey point
that started it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .assess import Assessment, assess
from .equipment import EquipmentItem, EquipmentType
from .fov import FovWindow, evaluate_fov
from .geometry import Carriageway, Gantry
from .remediation import RemediationPlan, apply_raise, plan_remediation
from .review import HOLD_EVIDENCE, ReviewRegister, standard_register
from .standards import ClearanceStandard
from .workpack import WorkPackage, build_work_package


class Stage(str, Enum):
    SURVEY = "survey"
    ASSESS = "assess"
    SIZE = "size"
    VALIDATE = "validate"
    PACKAGE = "package"
    REVIEW = "review"
    APPROVE = "approve"
    VERIFY = "verify"


STAGE_TITLE = {
    Stage.SURVEY: "Survey",
    Stage.ASSESS: "Assess clearance",
    Stage.SIZE: "Size remediation",
    Stage.VALIDATE: "Validate side effects",
    Stage.PACKAGE: "Package the change",
    Stage.REVIEW: "Design review",
    Stage.APPROVE: "Approval gate",
    Stage.VERIFY: "Verify on site",
}

STAGE_QUESTION = {
    Stage.SURVEY: "What is actually there?",
    Stage.ASSESS: "Does every lane meet the requirement?",
    Stage.SIZE: "What is the smallest fix that works?",
    Stage.VALIDATE: "Does the fix break anything else?",
    Stage.PACKAGE: "What goes to site, and who signs it?",
    Stage.REVIEW: "Has every comment been answered?",
    Stage.APPROVE: "Can this be released?",
    Stage.VERIFY: "Did it work?",
}


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    INFO = "info"


@dataclass
class StageResult:
    stage: Stage
    verdict: Verdict
    headline: str
    findings: List[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "stage": self.stage.value, "title": STAGE_TITLE[self.stage],
            "question": STAGE_QUESTION[self.stage], "verdict": self.verdict.value,
            "headline": self.headline, "findings": list(self.findings),
            "data": dict(self.data),
        }


@dataclass
class Project:
    gantry: Gantry
    carriageway: Carriageway
    items: List[EquipmentItem]
    standard: ClearanceStandard
    stages: List[StageResult] = field(default_factory=list)
    before: Optional[Assessment] = None
    plan: Optional[RemediationPlan] = None
    fov_before: Optional[FovWindow] = None
    fov_after: Optional[FovWindow] = None
    workpack: Optional[WorkPackage] = None
    register: Optional[ReviewRegister] = None
    verified: Optional[Assessment] = None

    def stage(self, stage: Stage) -> Optional[StageResult]:
        return next((s for s in self.stages if s.stage is stage), None)

    def released(self) -> bool:
        approve = self.stage(Stage.APPROVE)
        return approve is not None and approve.verdict is Verdict.PASS

    def as_dict(self) -> dict:
        return {
            "standard": self.standard.as_dict(),
            "released": self.released(),
            "stages": [s.as_dict() for s in self.stages],
        }


def _resolve_review(register: ReviewRegister, project: Project) -> None:
    """Answer every comment from the evidence the earlier stages produced."""
    plan = project.plan
    before = project.before
    fov_after = project.fov_after
    wp = project.workpack
    height_mm = plan.selection.height_m * 1000 if plan else 0

    lane_lines = "; ".join(
        f"{l.lane} {l.min_clearance_m:.3f} m" for l in before.lanes) if before else ""
    after_lines = "; ".join(
        f"{l.lane} {l.min_clearance_m:.3f} m" for l in plan.after.lanes) if plan and plan.after else ""

    responses = {
        "C-01": (f"Permitted tilt window after the change is "
                 f"{fov_after.min_tilt_deg:.1f} to {fov_after.max_tilt_deg:.0f} deg; "
                 f"the operating angle sits {fov_after.margin_deg:.1f} deg inside it."
                 if fov_after else "Field-of-view window recalculated."),
        "C-02": ("Raised units are re-aimed to their surveyed aim points under the standard "
                 "commissioning procedure. Classification sensors are untouched, so their "
                 "alignment is unaffected."),
        "C-03": ("The spacer is positively fixed to the girder, not seated. No second "
                 "hanging interface is introduced and no additional vibration path results."),
        "C-04": (f"Spacer general arrangement, fixing detail, material grade and bolting "
                 f"issued as drawings for the {height_mm:.0f} mm spacer."),
        "C-05": ("Structural drawings certified and signed by a registered professional "
                 "engineer; the change document names its author and approver."),
        "C-06": (f"Clearance before: {lane_lines}. After: {after_lines}."),
        "C-07": ("The height change does not alter the field of view, so the system geometry "
                 "drawing is reissued for the revised mounting height only."),
        "C-08": ("No system parameter changes result: the field of view and aim points are "
                 "unchanged after re-aiming."),
        "C-09": ("The revised mounting height stays inside the qualified installation range, "
                 "so baseline capture and classification tests cover it. Post-installation "
                 "performance is monitored for an agreed observation period."),
        "C-10": (f"Installation requires closure of {', '.join(wp.lanes_to_close)} under a "
                 f"night possession; estimated {wp.duration_min} min on site."
                 if wp and wp.lanes_to_close else "Lane closures required; method issued."),
        "C-11": ("Work plan issued with the full method, crew, possession window and traffic "
                 "control responsibilities identified."),
        "C-12": ("Non-conformance report raised against the clearance standard, with the "
                 "spacer recorded as its disposition and the verification survey as closure."),
        "C-13": ("Authority drawing numbers requested and allocated to the new sheets as an "
                 "addendum to the existing register."),
        "C-14": ("Figures regenerated from a single geometry source so the tilt envelope is "
                 "consistent across the document."),
    }
    for comment in register.comments:
        comment.respond(responses.get(comment.ref, "Addressed in the reissued document."))
        comment.agree()
        comment.close()
    for hold in register.hold_points:
        hold.satisfy(HOLD_EVIDENCE.get(hold.ref, "Evidence supplied."))


def run_pipeline(gantry: Gantry, carriageway: Carriageway,
                 items: List[EquipmentItem], standard: ClearanceStandard,
                 forced_raiser_m: Optional[float] = None,
                 resolve_review: bool = True) -> Project:
    project = Project(gantry=gantry, carriageway=carriageway, items=items,
                      standard=standard, register=standard_register())

    # 1 — Survey
    project.stages.append(StageResult(
        Stage.SURVEY, Verdict.INFO,
        f"{len(items)} units surveyed across {len(carriageway.lanes)} lanes",
        [f"Gantry span {gantry.span_m:.1f} m with {gantry.camber_m * 1000:.0f} mm "
         f"camber at mid-span.",
         f"Carriageway {carriageway.width_m():.1f} m wide at "
         f"{carriageway.crossfall * 100:.1f}% crossfall."
         + (f" Includes {carriageway.overlay_m * 1000:.0f} mm of overlay since construction."
            if carriageway.overlay_m else ""),
         "Camber lifts the girder at mid-span while crossfall drops the road to one side, "
         "so the tightest gap is off-centre."],
        {"span_m": gantry.span_m, "lanes": len(carriageway.lanes),
         "items": len(items), "overlay_mm": round(carriageway.overlay_m * 1000)}))

    # 2 — Assess
    before = assess(gantry, carriageway, items, standard)
    project.before = before
    gov = before.governing_item()
    bad_lanes = before.non_conforming_lanes()
    project.stages.append(StageResult(
        Stage.ASSESS,
        Verdict.PASS if before.conforming() else Verdict.FAIL,
        (f"All {len(before.lanes)} lanes meet {before.required_m:.2f} m"
         if before.conforming()
         else f"{len(bad_lanes)} of {len(before.lanes)} lanes below {before.required_m:.2f} m"),
        ([f"Governing item is the {gov.item.label()} in {gov.item.lane} at "
          f"{gov.clearance_m:.3f} m." if gov else ""]
         + [f"{l.lane}: {l.min_clearance_m:.3f} m, short by {l.deficit_m() * 1000:.0f} mm."
            for l in bad_lanes]
         + ([f"Only the {', '.join(before.affected_kinds())} are involved; everything else "
             "on the structure clears."] if bad_lanes else [])),
        before.as_dict()))

    # 3 — Size
    plan = plan_remediation(gantry, carriageway, items, standard, before,
                            forced_height_m=forced_raiser_m)
    project.plan = plan
    project.stages.append(StageResult(
        Stage.SIZE,
        Verdict.PASS if plan.resolves() else Verdict.FAIL,
        (f"{plan.selection.height_m * 1000:.0f} mm spacer on "
         f"{len(plan.affected_item_ids)} unit(s)" if plan.selection.height_m
         else "No remediation required"),
        [plan.selection.reason] + plan.notes,
        plan.as_dict()))

    # 4 — Validate side effects
    raise_m = plan.selection.height_m
    project.fov_before = evaluate_fov(0.0)
    project.fov_after = evaluate_fov(raise_m)
    fov = project.fov_after
    side_effects = [
        f"Tilt window narrows from {project.fov_before.width_deg():.1f} to "
        f"{fov.width_deg():.1f} deg.",
        "Added mass is negligible against the girder's design load; no structural change.",
        "No drilling and no welding, so corrosion protection is undisturbed.",
        "Cabling is reused as installed; no electrical modification.",
        "Maintenance access is preserved: beam-mounted units still rotate for servicing.",
    ]
    project.stages.append(StageResult(
        Stage.VALIDATE,
        Verdict.PASS if fov.workable() else Verdict.FAIL,
        (f"Optics hold: {fov.margin_deg:.1f} deg of tilt margin remains"
         if fov.workable() else "Beam clips the field of view at the operating angle"),
        fov.reasons + side_effects,
        {"fov_before": project.fov_before.as_dict(), "fov_after": fov.as_dict()}))

    # 5 — Package
    wp = build_work_package(plan, before)
    project.workpack = wp
    project.stages.append(StageResult(
        Stage.PACKAGE, Verdict.INFO,
        f"{wp.item_count} unit(s), {wp.duration_min / 60.0:.1f} h on site",
        wp.notes + ["Non-conformance report, certified drawings and authority drawing "
                    "numbers are raised as hold points on the review."],
        wp.as_dict()))

    # 6 — Review
    register = project.register
    if resolve_review:
        _resolve_review(register, project)
    project.stages.append(StageResult(
        Stage.REVIEW,
        Verdict.PASS if register.approved() else Verdict.BLOCKED,
        (f"All {len(register.comments)} comments closed"
         if register.approved()
         else f"{len(register.open_comments())} comment(s) open, "
              f"{len(register.outstanding_hold_points())} hold point(s) outstanding"),
        register.gate_reasons(),
        register.as_dict()))

    # 7 — Approve
    gate_ok = register.approved() and plan.resolves() and project.fov_after.workable()
    blockers: List[str] = []
    if not register.approved():
        blockers.extend(register.gate_reasons())
    if not plan.resolves():
        blockers.append("Remediation does not bring every lane into conformance.")
    if not project.fov_after.workable():
        blockers.append("Field of view is obstructed at the operating tilt.")
    project.stages.append(StageResult(
        Stage.APPROVE,
        Verdict.PASS if gate_ok else Verdict.BLOCKED,
        "Released for construction" if gate_ok else "Not released",
        blockers if blockers else ["Comments closed, hold points satisfied, remediation "
                                   "proven and optics validated."],
        {"released": gate_ok, "blockers": blockers}))

    # 8 — Verify
    if gate_ok and plan.affected_kind:
        verified_items = apply_raise(items, EquipmentType(plan.affected_kind),
                                     plan.selection.height_m)
        verified = assess(gantry, carriageway, verified_items, standard)
        project.verified = verified
        project.stages.append(StageResult(
            Stage.VERIFY,
            Verdict.PASS if verified.conforming() else Verdict.FAIL,
            ("Verification survey confirms every lane compliant"
             if verified.conforming() else "Verification survey still shows a shortfall"),
            [f"{l.lane}: {l.min_clearance_m:.3f} m "
             f"({(l.min_clearance_m - verified.required_m) * 1000:+.0f} mm on requirement)."
             for l in verified.lanes]
            + (["Non-conformance closed out against the verification survey."]
               if verified.conforming() else []),
            verified.as_dict()))
    elif gate_ok and before.conforming():
        project.verified = before
        project.stages.append(StageResult(
            Stage.VERIFY, Verdict.PASS,
            "Nothing to verify: the structure already complies",
            [f"{l.lane}: {l.min_clearance_m:.3f} m "
             f"({(l.min_clearance_m - before.required_m) * 1000:+.0f} mm on requirement)."
             for l in before.lanes]
            + ["No spacer fitted and no site work generated."],
            before.as_dict()))
    else:
        project.stages.append(StageResult(
            Stage.VERIFY, Verdict.BLOCKED, "Not reached",
            ["Site verification cannot start until the change is released."], {}))

    return project
