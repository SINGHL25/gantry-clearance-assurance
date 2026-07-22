"""Domain claims about spacer sizing and field-of-view validation."""
from gantry_clearance.assess import assess
from gantry_clearance.equipment import EquipmentType
from gantry_clearance.fov import (MAX_TILT_DEG, evaluate_fov, minimum_tilt_deg)
from gantry_clearance.remediation import (RAISER_CATALOGUE_M, SIZING_MARGIN_M,
                                          apply_raise, plan_remediation, select_raiser)
from gantry_clearance.scenarios import apply_scenario


def base():
    sc = apply_scenario("as_surveyed")
    return sc.gantry, sc.carriageway, sc.items, sc.standard


# ---- spacer sizing ----------------------------------------------------------

def test_the_smallest_adequate_spacer_is_chosen():
    sel = select_raiser(0.139)
    assert sel.height_m == 0.180
    assert sel.from_catalogue is True


def test_the_chosen_spacer_covers_the_deficit_plus_a_margin():
    sel = select_raiser(0.139)
    assert sel.height_m >= 0.139 + SIZING_MARGIN_M


def test_a_bigger_deficit_selects_a_bigger_spacer():
    small = select_raiser(0.050)
    large = select_raiser(0.200)
    assert large.height_m > small.height_m


def test_every_catalogue_height_is_selectable():
    for h in RAISER_CATALOGUE_M:
        sel = select_raiser(max(0.0, h - SIZING_MARGIN_M))
        assert sel.height_m <= h


def test_a_deficit_beyond_the_catalogue_is_flagged():
    sel = select_raiser(0.500)
    assert sel.from_catalogue is False
    assert "bespoke" in sel.reason or "structural" in sel.reason


def test_remediation_resolves_the_surveyed_site():
    g, c, items, std = base()
    plan = plan_remediation(g, c, items, std)
    assert plan.selection.height_m == 0.180
    assert plan.resolves() is True


def test_remediation_lifts_only_the_governing_equipment_type():
    g, c, items, std = base()
    plan = plan_remediation(g, c, items, std)
    assert plan.affected_kind == "vr_sensor"
    assert all("vr_sensor" in item_id for item_id in plan.affected_item_ids)


def test_the_whole_type_is_raised_not_just_the_offenders():
    g, c, items, std = base()
    before = assess(g, c, items, std)
    plan = plan_remediation(g, c, items, std, before)
    # only two lanes failed, but all four cameras are raised for uniformity
    assert len(plan.affected_item_ids) == 4
    assert len(before.non_conforming_items()) == 2


def test_an_undersized_spacer_does_not_resolve():
    g, c, items, std = base()
    plan = plan_remediation(g, c, items, std, forced_height_m=0.100)
    assert plan.resolves() is False
    assert plan.after is not None
    assert plan.after.non_conforming_items()


def test_a_compliant_structure_gets_no_spacer():
    sc = apply_scenario("already_compliant")
    plan = plan_remediation(sc.gantry, sc.carriageway, sc.items, sc.standard)
    assert plan.selection.height_m == 0.0
    assert plan.affected_item_ids == []


def test_applying_a_spacer_raises_clearance_by_its_height():
    g, c, items, std = base()
    before = assess(g, c, items, std)
    after = assess(g, c, apply_raise(items, EquipmentType.VR_SENSOR, 0.180), std)
    lift = after.lanes[0].min_clearance_m - before.lanes[0].min_clearance_m
    assert abs(lift - 0.180) < 1e-9


def test_remediation_leaves_the_original_equipment_untouched():
    g, c, items, std = base()
    original = [i.raise_m for i in items]
    plan_remediation(g, c, items, std)
    assert [i.raise_m for i in items] == original


# ---- field of view ----------------------------------------------------------

def test_the_unraised_sensor_clears_the_beam_at_twenty_degrees():
    assert abs(minimum_tilt_deg(0.0) - 20.0) < 0.2


def test_raising_the_sensor_steepens_the_minimum_tilt():
    assert minimum_tilt_deg(0.180) > minimum_tilt_deg(0.0)


def test_a_taller_spacer_narrows_the_tilt_window():
    small = evaluate_fov(0.100)
    large = evaluate_fov(0.220)
    assert large.width_deg() < small.width_deg()


def test_the_standard_spacer_keeps_the_operating_angle_valid():
    w = evaluate_fov(0.180)
    assert w.obstructed is False
    assert w.workable() is True
    assert w.margin_deg > 0


def test_an_excessive_spacer_puts_the_beam_in_shot():
    w = evaluate_fov(0.260)
    assert w.obstructed is True
    assert w.workable() is False


def test_the_ceiling_of_the_window_is_set_by_the_mount():
    assert evaluate_fov(0.180).max_tilt_deg == MAX_TILT_DEG


def test_the_window_narrows_but_survives_the_standard_fix():
    before = evaluate_fov(0.0)
    after = evaluate_fov(0.180)
    assert after.width_deg() < before.width_deg()
    assert after.workable() is True


def test_the_fov_result_explains_the_geometry():
    reasons = evaluate_fov(0.180).reasons
    assert any("minimum tilt" in r for r in reasons)
    assert any("spacer" in r for r in reasons)


def test_an_obstructed_result_says_so_plainly():
    assert any("clips" in r for r in evaluate_fov(0.260).reasons)
