"""gantry_clearance: overhead gantry vertical-clearance assurance.

Survey an overhead tolling gantry, assess vertical clearance lane by lane against
a standard, size the smallest remediation that works, prove it does not break the
sensor optics, package the change, run it through design review, gate the
approval and verify it on site.

Zero third-party dependencies. Standard library only.
"""
from .geometry import (Gantry, Carriageway, Lane, standard_gantry,
                       standard_carriageway, MODULE_LENGTH_M)
from .equipment import (EquipmentItem, EquipmentType, NOMINAL_DROP_M,
                        build_equipment)
from .standards import ClearanceStandard, STANDARDS, get_standard
from .assess import (assess, Assessment, ItemAssessment, LaneAssessment, Status,
                     MARGINAL_BAND_M)
from .remediation import (plan_remediation, select_raiser, apply_raise,
                          RemediationPlan, RaiserSelection, RAISER_CATALOGUE_M)
from .fov import evaluate_fov, minimum_tilt_deg, FovWindow, MAX_TILT_DEG
from .review import (ReviewRegister, Comment, HoldPoint, CommentState, Severity,
                     Discipline, standard_register)
from .workpack import build_work_package, WorkPackage, WorkStep
from .pipeline import run_pipeline, Project, Stage, StageResult, Verdict, STAGE_TITLE
from .assistant import advise, Recommendation
from .scenarios import SCENARIOS, apply_scenario, baseline, Scenario

__all__ = [
    "Gantry", "Carriageway", "Lane", "standard_gantry", "standard_carriageway",
    "MODULE_LENGTH_M", "EquipmentItem", "EquipmentType", "NOMINAL_DROP_M",
    "build_equipment", "ClearanceStandard", "STANDARDS", "get_standard",
    "assess", "Assessment", "ItemAssessment", "LaneAssessment", "Status",
    "MARGINAL_BAND_M", "plan_remediation", "select_raiser", "apply_raise",
    "RemediationPlan", "RaiserSelection", "RAISER_CATALOGUE_M", "evaluate_fov",
    "minimum_tilt_deg", "FovWindow", "MAX_TILT_DEG", "ReviewRegister", "Comment",
    "HoldPoint", "CommentState", "Severity", "Discipline", "standard_register",
    "build_work_package", "WorkPackage", "WorkStep", "run_pipeline", "Project",
    "Stage", "StageResult", "Verdict", "STAGE_TITLE", "advise", "Recommendation",
    "SCENARIOS", "apply_scenario", "baseline", "Scenario",
]
