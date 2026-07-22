"""Domain claims about geometry and the clearance assessment."""
from gantry_clearance.assess import MARGINAL_BAND_M, Status, assess
from gantry_clearance.equipment import (EquipmentType, NOMINAL_DROP_M, build_equipment)
from gantry_clearance.geometry import (Gantry, standard_carriageway, standard_gantry)
from gantry_clearance.scenarios import apply_scenario
from gantry_clearance.standards import get_standard


def base():
    sc = apply_scenario("as_surveyed")
    return sc.gantry, sc.carriageway, sc.items, sc.standard


# ---- geometry ---------------------------------------------------------------

def test_camber_lifts_the_girder_at_mid_span():
    g = standard_gantry()
    assert g.soffit_level(g.mid_span_m()) > g.soffit_level(0.0)


def test_camber_equals_the_stated_rise_at_mid_span():
    g = standard_gantry()
    rise = g.soffit_level(g.mid_span_m()) - g.soffit_level(0.0)
    assert abs(rise - g.camber_m) < 1e-9


def test_the_girder_is_symmetric_about_mid_span():
    g = standard_gantry()
    assert abs(g.soffit_level(5.0) - g.soffit_level(g.span_m - 5.0)) < 1e-9


def test_crossfall_drops_the_road_from_the_high_side():
    c = standard_carriageway()
    assert c.surface_level(c.left_edge_m) > c.surface_level(c.right_edge_m())


def test_crossfall_drop_matches_the_gradient():
    c = standard_carriageway()
    drop = c.surface_level(c.left_edge_m) - c.surface_level(c.right_edge_m())
    assert abs(drop - c.crossfall * c.width_m()) < 1e-9


def test_an_overlay_raises_the_road_everywhere():
    c = standard_carriageway()
    before = c.surface_level(10.0)
    c.overlay_m = 0.040
    assert abs((c.surface_level(10.0) - before) - 0.040) < 1e-9


def test_four_lanes_span_the_carriageway_width():
    c = standard_carriageway()
    assert len(c.lanes) == 4
    assert abs(c.width_m() - 14.0) < 1e-9


# ---- equipment --------------------------------------------------------------

def test_the_registration_camera_hangs_lowest():
    lowest = max(NOMINAL_DROP_M, key=lambda k: NOMINAL_DROP_M[k])
    assert lowest is EquipmentType.VR_SENSOR


def test_only_frame_mounted_items_can_take_a_spacer():
    g, c, items, _ = base()
    frame = {i.kind for i in items if i.frame_mounted()}
    assert frame == {EquipmentType.VR_SENSOR}


def test_fitting_a_spacer_reduces_the_drop():
    g, c, items, _ = base()
    item = next(i for i in items if i.kind is EquipmentType.VR_SENSOR)
    before = item.drop_m()
    item.raise_m = 0.180
    assert abs((before - item.drop_m()) - 0.180) < 1e-9


def test_every_lane_gets_a_full_complement():
    g, c, items, _ = base()
    assert len(items) == len(c.lanes) * len(EquipmentType)


# ---- assessment -------------------------------------------------------------

def test_the_surveyed_site_fails_two_lanes():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    assert len(a.non_conforming_lanes()) == 2
    assert a.conforming() is False


def test_the_high_side_lane_is_the_worst():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    assert a.lanes[0].lane == "L1"
    assert a.lanes[0].min_clearance_m == min(l.min_clearance_m for l in a.lanes)


def test_clearance_improves_across_the_carriageway():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    values = [l.min_clearance_m for l in a.lanes]
    assert values == sorted(values)


def test_the_registration_camera_governs_every_lane():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    assert {l.governing_kind for l in a.lanes} == {"vr_sensor"}


def test_only_the_camera_is_non_conforming():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    assert a.affected_kinds() == ["vr_sensor"]


def test_the_worst_deficit_drives_the_required_raise():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    assert abs(a.required_raise_m() - a.worst_deficit_m()) < 1e-12
    assert 0.130 < a.required_raise_m() < 0.150


def test_a_lane_just_above_the_requirement_is_marginal_not_conforming():
    g, c, items, std = base()
    a = assess(g, c, items, std)
    # L3 clears by less than the marginal band
    l3 = next(l for l in a.lanes if l.lane == "L3")
    assert 0 <= (l3.min_clearance_m - a.required_m) < MARGINAL_BAND_M + 0.01


def test_a_compliant_structure_reports_no_deficit():
    sc = apply_scenario("already_compliant")
    a = assess(sc.gantry, sc.carriageway, sc.items, sc.standard)
    assert a.conforming() is True
    assert a.worst_deficit_m() == 0.0


def test_an_overlay_reduces_clearance_by_its_thickness():
    dry = apply_scenario("as_surveyed")
    wet = apply_scenario("future_overlay")
    a1 = assess(dry.gantry, dry.carriageway, dry.items, dry.standard)
    a2 = assess(wet.gantry, wet.carriageway, wet.items, wet.standard)
    drop = a1.lanes[0].min_clearance_m - a2.lanes[0].min_clearance_m
    assert abs(drop - 0.040) < 1e-9


# ---- standards --------------------------------------------------------------

def test_the_requirement_is_the_sum_of_its_allowances():
    s = get_standard("motorway_gantry_with_overlay")
    assert abs(s.required_m() - (s.base_m + s.overlay_allowance_m
                                 + s.survey_tolerance_m + s.operator_margin_m)) < 1e-12


def test_reserving_an_overlay_raises_the_bar():
    plain = get_standard("motorway_gantry")
    reserved = get_standard("motorway_gantry_with_overlay")
    assert reserved.required_m() > plain.required_m()


def test_a_stricter_standard_pulls_in_more_lanes():
    sc = apply_scenario("as_surveyed")
    plain = assess(sc.gantry, sc.carriageway, sc.items, get_standard("motorway_gantry"))
    strict = assess(sc.gantry, sc.carriageway, sc.items,
                    get_standard("motorway_gantry_with_overlay"))
    assert len(strict.non_conforming_lanes()) > len(plain.non_conforming_lanes())


def test_a_bridge_requirement_is_lower_than_a_gantry_requirement():
    assert get_standard("bridge_over_road").required_m() < get_standard("motorway_gantry").required_m()
