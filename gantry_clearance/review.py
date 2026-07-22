"""Design review.

A change over a live carriageway is not approved because the engineering is
right. It is approved because every reviewer's comment has been answered, the
answers have been agreed, and the things that cannot be argued away — a signed
structural drawing, a raised non-conformance, a decision on lane closures — have
actually happened.

So this module models two different objects. Comments move through a lifecycle
and can be closed by discussion. **Hold points** cannot: they are binary
obligations, and while one is outstanding no amount of agreement unlocks the
gate. Keeping them apart is what stops a review from being talked to a close.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class CommentState(str, Enum):
    OPEN = "open"              # raised, no response yet
    RESPONDED = "responded"    # issuer has answered, awaiting agreement
    AGREED = "agreed"          # reviewer accepts the response
    CLOSED = "closed"          # response incorporated and verified


class Discipline(str, Enum):
    STRUCTURAL = "structural"
    DESIGN = "design"
    COMMISSIONING = "commissioning"
    CONSTRUCTION = "construction"
    QUALITY = "quality"
    DOCUMENTATION = "documentation"
    APPROVAL = "approval"


class Severity(str, Enum):
    BLOCKING = "blocking"      # cannot proceed until resolved
    MAJOR = "major"
    MINOR = "minor"


@dataclass
class Comment:
    ref: str
    discipline: Discipline
    severity: Severity
    section: str
    summary: str
    state: CommentState = CommentState.OPEN
    response: str = ""

    def respond(self, response: str) -> None:
        self.response = response
        if self.state is CommentState.OPEN:
            self.state = CommentState.RESPONDED

    def agree(self) -> None:
        if self.state is CommentState.RESPONDED:
            self.state = CommentState.AGREED

    def close(self) -> None:
        if self.state is CommentState.AGREED:
            self.state = CommentState.CLOSED

    def is_closed(self) -> bool:
        return self.state is CommentState.CLOSED

    def as_dict(self) -> dict:
        return {
            "ref": self.ref, "discipline": self.discipline.value,
            "severity": self.severity.value, "section": self.section,
            "summary": self.summary, "state": self.state.value,
            "response": self.response,
        }


@dataclass
class HoldPoint:
    ref: str
    title: str
    detail: str
    met: bool = False
    evidence: str = ""

    def satisfy(self, evidence: str) -> None:
        self.met = True
        self.evidence = evidence

    def as_dict(self) -> dict:
        return {"ref": self.ref, "title": self.title, "detail": self.detail,
                "met": self.met, "evidence": self.evidence}


@dataclass
class ReviewRegister:
    comments: List[Comment] = field(default_factory=list)
    hold_points: List[HoldPoint] = field(default_factory=list)

    def by_state(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in CommentState}
        for c in self.comments:
            counts[c.state.value] += 1
        return counts

    def open_comments(self) -> List[Comment]:
        return [c for c in self.comments if not c.is_closed()]

    def blocking_open(self) -> List[Comment]:
        return [c for c in self.open_comments() if c.severity is Severity.BLOCKING]

    def outstanding_hold_points(self) -> List[HoldPoint]:
        return [h for h in self.hold_points if not h.met]

    def approved(self) -> bool:
        return not self.open_comments() and not self.outstanding_hold_points()

    def gate_reasons(self) -> List[str]:
        reasons: List[str] = []
        blocking = self.blocking_open()
        if blocking:
            reasons.append(f"{len(blocking)} blocking comment(s) still open: "
                           + ", ".join(c.ref for c in blocking))
        other = [c for c in self.open_comments() if c.severity is not Severity.BLOCKING]
        if other:
            reasons.append(f"{len(other)} further comment(s) not yet closed")
        for h in self.outstanding_hold_points():
            reasons.append(f"hold point {h.ref} outstanding: {h.title}")
        if not reasons:
            reasons.append("all comments closed and all hold points satisfied")
        return reasons

    def find(self, ref: str) -> Optional[Comment]:
        return next((c for c in self.comments if c.ref == ref), None)

    def find_hold(self, ref: str) -> Optional[HoldPoint]:
        return next((h for h in self.hold_points if h.ref == ref), None)

    def as_dict(self) -> dict:
        return {
            "approved": self.approved(), "by_state": self.by_state(),
            "open": len(self.open_comments()),
            "blocking_open": len(self.blocking_open()),
            "hold_points_outstanding": len(self.outstanding_hold_points()),
            "gate_reasons": self.gate_reasons(),
            "comments": [c.as_dict() for c in self.comments],
            "hold_points": [h.as_dict() for h in self.hold_points],
        }


def standard_register() -> ReviewRegister:
    """The comment themes a change like this reliably attracts.

    These are the recurring review questions for an over-carriageway equipment
    change: prove the optics still work, prove the fixing is a fixing, show the
    numbers lane by lane, and put a signature on the drawings.
    """
    c = [
        Comment("C-01", Discipline.DESIGN, Severity.BLOCKING, "FOV",
                "Confirm the raised sensor's field of view is not clipped by the girder beam, "
                "and state the tilt range over which that holds."),
        Comment("C-02", Discipline.COMMISSIONING, Severity.MAJOR, "Alignment",
                "Confirm re-alignment to the aim point follows the commissioning procedure, "
                "and whether the classification sensor alignment is affected."),
        Comment("C-03", Discipline.STRUCTURAL, Severity.BLOCKING, "Fixing",
                "The spacer must be positively fixed, not seated in existing slots. "
                "Confirm the fixing and whether it introduces a second vibration path."),
        Comment("C-04", Discipline.DOCUMENTATION, Severity.BLOCKING, "General",
                "Design detail not supplied: steel grade, sections, bolting. Illustrations "
                "in a memo are not a substitute for drawings."),
        Comment("C-05", Discipline.APPROVAL, Severity.BLOCKING, "General",
                "Structural drawings for work over a live carriageway must carry a certifying "
                "engineer's signature, and the document must name its author."),
        Comment("C-06", Discipline.DESIGN, Severity.BLOCKING, "Clearance",
                "State the actual clearance per lane, how many items are affected, and the "
                "clearance each lane is raised to."),
        Comment("C-07", Discipline.DOCUMENTATION, Severity.MINOR, "Geometry",
                "Confirm whether the system geometry drawing needs reissue for the new "
                "sensor heights."),
        Comment("C-08", Discipline.COMMISSIONING, Severity.MINOR, "Parameters",
                "List any system parameters requiring adjustment after the change."),
        Comment("C-09", Discipline.QUALITY, Severity.MAJOR, "Validation",
                "List the tests that will demonstrate no performance impact."),
        Comment("C-10", Discipline.CONSTRUCTION, Severity.BLOCKING, "Method",
                "State the installation method and confirm whether lane closures are required."),
        Comment("C-11", Discipline.CONSTRUCTION, Severity.MAJOR, "Work plan",
                "Work plan must carry enough detail to settle principal contractor and "
                "traffic control responsibilities."),
        Comment("C-12", Discipline.QUALITY, Severity.BLOCKING, "Non-conformance",
                "The existing arrangement does not meet the standard: raise a non-conformance "
                "report with the spacer as its disposition."),
        Comment("C-13", Discipline.DOCUMENTATION, Severity.MAJOR, "Drawing register",
                "New drawings require authority drawing numbers, requested as an addendum."),
        Comment("C-14", Discipline.DOCUMENTATION, Severity.MINOR, "Figures",
                "Tilt envelope differs between two figures. Check and confirm."),
    ]
    h = [
        HoldPoint("H-1", "Certified structural drawings",
                  "Spacer drawings signed by a registered professional engineer."),
        HoldPoint("H-2", "Non-conformance report raised",
                  "NCR recorded against the standard, with the spacer as its disposition."),
        HoldPoint("H-3", "Authority drawing numbers issued",
                  "Drawing numbers allocated by the road authority for the new sheets."),
        HoldPoint("H-4", "Traffic management agreed",
                  "Lane closure requirement determined and traffic control responsibility settled."),
    ]
    return ReviewRegister(comments=c, hold_points=h)


# The evidence that closes each hold point, once the preceding work is done.
HOLD_EVIDENCE = {
    "H-1": "Spacer general arrangement and fixing detail issued, engineer-signed.",
    "H-2": "Non-conformance report raised against the clearance standard.",
    "H-3": "Authority drawing numbers allocated to the new sheets.",
    "H-4": "Night closure of the affected lanes agreed with the traffic manager.",
}
