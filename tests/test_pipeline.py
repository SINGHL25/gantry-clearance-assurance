"""Domain claims about the review gate, the work package and the whole process."""
from gantry_clearance.assistant import advise
from gantry_clearance.pipeline import Stage, Verdict, run_pipeline
from gantry_clearance.review import (CommentState, Severity, standard_register)
from gantry_clearance.scenarios import SCENARIOS, apply_scenario
from gantry_clearance.workpack import NIGHT_WINDOW_MIN


def run(name):
    sc = apply_scenario(name)
    return sc, run_pipeline(sc.gantry, sc.carriageway, sc.items, sc.standard,
                            sc.forced_raiser_m, sc.resolve_review)


# ---- review register --------------------------------------------------------

def test_a_fresh_register_is_not_approved():
    assert standard_register().approved() is False


def test_a_comment_moves_through_its_lifecycle():
    r = standard_register()
    c = r.find("C-01")
    assert c.state is CommentState.OPEN
    c.respond("Answered.")
    assert c.state is CommentState.RESPONDED
    c.agree()
    assert c.state is CommentState.AGREED
    c.close()
    assert c.is_closed()


def test_a_comment_cannot_skip_straight_to_closed():
    c = standard_register().find("C-01")
    c.close()
    assert c.is_closed() is False


def test_closing_every_comment_is_not_enough_to_approve():
    r = standard_register()
    for c in r.comments:
        c.respond("Answered.")
        c.agree()
        c.close()
    assert not r.open_comments()
    assert r.approved() is False          # hold points still outstanding
    assert r.outstanding_hold_points()


def test_satisfying_every_hold_point_is_not_enough_either():
    r = standard_register()
    for h in r.hold_points:
        h.satisfy("done")
    assert r.approved() is False          # comments still open


def test_approval_needs_both_comments_closed_and_hold_points_met():
    r = standard_register()
    for c in r.comments:
        c.respond("Answered.")
        c.agree()
        c.close()
    for h in r.hold_points:
        h.satisfy("done")
    assert r.approved() is True


def test_blocking_comments_are_named_in_the_gate_reasons():
    r = standard_register()
    reasons = " ".join(r.gate_reasons())
    assert "blocking" in reasons


def test_the_register_carries_blocking_comments():
    r = standard_register()
    assert any(c.severity is Severity.BLOCKING for c in r.comments)


def test_every_comment_has_a_discipline_and_a_section():
    for c in standard_register().comments:
        assert c.discipline and c.section


# ---- work package -----------------------------------------------------------

def test_the_work_package_closes_the_lanes_that_hold_raised_units():
    _, project = run("as_surveyed")
    wp = project.workpack
    assert wp.lanes_to_close == ["L1", "L2", "L3", "L4"]


def test_duration_scales_with_the_number_of_units():
    _, project = run("as_surveyed")
    wp = project.workpack
    assert wp.duration_min > wp.item_count * 30


def test_the_job_fits_a_single_night_possession():
    _, project = run("as_surveyed")
    assert project.workpack.duration_min <= NIGHT_WINDOW_MIN
    assert project.workpack.fits_one_shift() is True


def test_the_method_opens_with_an_approvals_hold():
    _, project = run("as_surveyed")
    first = project.workpack.steps[0]
    assert first.hold is True
    assert "approval" in first.title.lower()


def test_the_method_closes_with_a_verification_survey():
    _, project = run("as_surveyed")
    last = project.workpack.steps[-1]
    assert last.hold is True
    assert "verification" in last.title.lower()


def test_a_compliant_structure_generates_no_site_work():
    _, project = run("already_compliant")
    assert project.workpack.item_count == 0


# ---- end-to-end pipeline ----------------------------------------------------

def test_every_scenario_runs_all_eight_stages():
    for name in SCENARIOS:
        _, project = run(name)
        assert [s.stage for s in project.stages] == list(Stage)


def test_the_surveyed_site_is_released_and_verified():
    _, project = run("as_surveyed")
    assert project.released() is True
    assert project.stage(Stage.VERIFY).verdict is Verdict.PASS
    assert project.verified.conforming() is True


def test_verification_confirms_the_worst_lane_now_complies():
    _, project = run("as_surveyed")
    worst = min(l.min_clearance_m for l in project.verified.lanes)
    assert worst >= project.verified.required_m


def test_an_undersized_spacer_blocks_release():
    _, project = run("undersized_spacer")
    assert project.stage(Stage.SIZE).verdict is Verdict.FAIL
    assert project.released() is False
    assert project.stage(Stage.VERIFY).verdict is Verdict.BLOCKED


def test_an_obstructed_field_of_view_blocks_release():
    _, project = run("overlay_reserved")
    assert project.stage(Stage.VALIDATE).verdict is Verdict.FAIL
    assert project.released() is False


def test_a_blocked_change_never_reaches_site_verification():
    for name in ("undersized_spacer", "overlay_reserved"):
        _, project = run(name)
        assert project.verified is None


def test_a_compliant_structure_passes_assessment_outright():
    _, project = run("already_compliant")
    assert project.stage(Stage.ASSESS).verdict is Verdict.PASS
    assert project.released() is True


def test_the_review_stage_answers_every_comment():
    _, project = run("as_surveyed")
    assert all(c.is_closed() for c in project.register.comments)
    assert project.register.approved() is True


def test_the_clearance_comment_is_answered_with_actual_lane_figures():
    _, project = run("as_surveyed")
    response = project.register.find("C-06").response
    assert "L1" in response and "m" in response


def test_the_optics_comment_quotes_the_recalculated_window():
    _, project = run("as_surveyed")
    response = project.register.find("C-01").response
    assert "deg" in response


def test_a_resolved_project_reads_as_normal_priority():
    _, project = run("as_surveyed")
    assert advise(project).priority == "normal"


def test_a_blocked_project_reads_as_critical():
    for name in ("undersized_spacer", "overlay_reserved"):
        _, project = run(name)
        assert advise(project).priority == "critical"


def test_the_assistant_traces_the_requirement_and_the_spacer():
    _, project = run("as_surveyed")
    trace = " ".join(advise(project).trace)
    assert "Requirement" in trace and "Spacer" in trace


def test_the_assistant_tells_a_compliant_site_to_do_nothing():
    _, project = run("already_compliant")
    rec = advise(project)
    assert rec.priority == "normal"
    assert any("No remediation" in a for a in rec.actions)


def test_a_resurfaced_road_needs_a_taller_spacer():
    _, dry = run("as_surveyed")
    _, wet = run("future_overlay")
    assert wet.plan.selection.height_m > dry.plan.selection.height_m
