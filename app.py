"""Streamlit front end for the gantry clearance engine.

Run it with:

    pip install -r requirements-app.txt
    streamlit run app.py

Everything shown here is computed by the `gantry_clearance` package. This file
holds no engineering logic of its own — it draws what the engine returns. That
separation is deliberate: the package stays zero-dependency and testable, and
this app is an optional way to look at it.
"""
from __future__ import annotations

import streamlit as st

from gantry_clearance import (
    STANDARDS, SCENARIOS, apply_scenario, assess, advise, apply_raise,
    build_equipment, evaluate_fov, plan_remediation, run_pipeline,
    EquipmentType, Stage, STAGE_TITLE,
)
from gantry_clearance.equipment import LABEL
from gantry_clearance.geometry import MODULE_LENGTH_M
from gantry_clearance.remediation import RAISER_CATALOGUE_M

st.set_page_config(page_title="Gantry Clearance Assurance",
                   page_icon="⌖", layout="wide")

PASS, FAIL, MARGINAL = "#46C08B", "#E8564F", "#F2A93B"
NEWWORK, DIMC, INK, STAMP = "#F2A93B", "#6B829B", "#D6E4F0", "#8B78E0"
STATUS_COLOUR = {"conforming": PASS, "marginal": MARGINAL, "non_conforming": FAIL}
VERDICT_COLOUR = {"pass": PASS, "fail": FAIL, "blocked": MARGINAL, "info": DIMC}

st.markdown("""
<style>
  .stApp { background:#0C1017; }
  .block-container { padding-top:2.2rem; max-width:1400px; }
  h1,h2,h3 { letter-spacing:.04em; }
  .tblock { border:1px solid #26313F; background:#141B26; padding:14px 18px; margin-bottom:6px; }
  .tblock h1 { margin:0; font-size:17px; font-weight:600; letter-spacing:.26em;
               text-transform:uppercase; color:#D6E4F0; }
  .tblock .sub { font-family:ui-monospace,Menlo,monospace; font-size:11px;
                 color:#6B829B; margin-top:5px; letter-spacing:.06em; }
  .finding { border-top:1px solid #1E2836; padding:7px 0 7px 18px; position:relative;
             font-size:13.5px; color:#D6E4F0; line-height:1.55; }
  .finding:before { content:"—"; position:absolute; left:0; color:#455A70; }
  .cmt { background:#141B26; border:1px solid #26313F; border-left:2px solid #6B829B;
         padding:5px 8px; margin-bottom:5px; font-family:ui-monospace,Menlo,monospace;
         font-size:10px; color:#D6E4F0; }
  .cmt.blocking { border-left-color:#E8564F; }
  .cmt small { color:#455A70; display:block; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- elevation --
def elevation_svg(gantry, carriageway, assessment, spacer_m: float) -> str:
    """Draw the section the way the drawing office would: true scale, real
    dimension lines with extension lines, arrowheads and the figure on the line.
    """
    W, H, PX, X0, Y0 = 1180, 430, 36, 58, 356
    ex = lambda m: X0 + m * PX
    ey = lambda lv: Y0 - lv * PX
    g, c, a = gantry, carriageway, assessment
    right = c.right_edge_m()
    out = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;background:#141B26;border:1px solid #26313F">']

    road_l, road_r = ey(c.surface_level(c.left_edge_m)), ey(c.surface_level(right))
    out.append(f'<path d="M {ex(0)} {Y0 + 16} L {ex(g.span_m)} {Y0 + 16} '
               f'L {ex(g.span_m)} {road_r} L {ex(c.left_edge_m)} {road_l} Z" '
               f'fill="#1A2331" opacity="0.6"/>')
    out.append(f'<line x1="{ex(c.left_edge_m)}" y1="{road_l}" x2="{ex(right)}" '
               f'y2="{road_r}" stroke="{INK}" stroke-width="1.7"/>')
    for lane in c.lanes:
        xr = lane.right_m()
        out.append(f'<line x1="{ex(xr)}" y1="{ey(c.surface_level(xr))}" x2="{ex(xr)}" '
                   f'y2="{ey(c.surface_level(xr)) + 10}" stroke="#455A70" stroke-width="0.9"/>')
        out.append(f'<text x="{ex(lane.centre_m())}" y="{Y0 + 34}" fill="#455A70" '
                   f'font-size="10" font-family="monospace" text-anchor="middle">{lane.name}</text>')

    for x in (0.0, g.span_m):
        top = ey(g.soffit_level(x))
        out.append(f'<rect x="{ex(x) - 8}" y="{top}" width="16" height="{Y0 + 16 - top}" '
                   f'fill="#1A2331" stroke="{DIMC}" stroke-width="1"/>')
        out.append(f'<rect x="{ex(x) - 18}" y="{Y0 + 12}" width="36" height="10" '
                   f'fill="#1A2331" stroke="{DIMC}" stroke-width="1"/>')

    steps = [i * 0.4 for i in range(int(g.span_m / 0.4) + 1)]
    top_chord = " ".join(f"{ex(x)},{ey(g.soffit_level(x) + 1.05)}" for x in steps)
    bot_chord = " ".join(f"{ex(x)},{ey(g.soffit_level(x))}" for x in steps)
    out.append(f'<polyline points="{top_chord}" fill="none" stroke="{DIMC}" stroke-width="1.6"/>')
    out.append(f'<polyline points="{bot_chord}" fill="none" stroke="{INK}" stroke-width="1.9"/>')
    x = 0.6
    while x < g.span_m - MODULE_LENGTH_M:
        mid = x + MODULE_LENGTH_M / 2
        out.append(f'<line x1="{ex(x)}" y1="{ey(g.soffit_level(x))}" x2="{ex(mid)}" '
                   f'y2="{ey(g.soffit_level(mid) + 1.05)}" stroke="#26313F" stroke-width="0.7"/>')
        out.append(f'<line x1="{ex(mid)}" y1="{ey(g.soffit_level(mid) + 1.05)}" '
                   f'x2="{ex(x + MODULE_LENGTH_M)}" y2="{ey(g.soffit_level(x + MODULE_LENGTH_M))}" '
                   f'stroke="#26313F" stroke-width="0.7"/>')
        x += MODULE_LENGTH_M

    for ia in a.items:
        item = ia.item
        xp, governing = ex(item.offset_m), item.kind is EquipmentType.VR_SENSOR
        colour = STATUS_COLOUR[ia.status.value] if governing else "#455A70"
        if item.raise_m > 0 and governing:
            y_top, y_sp = ey(ia.soffit_level_m), ey(ia.soffit_level_m - item.raise_m)
            out.append(f'<rect x="{xp - 7}" y="{y_top}" width="14" height="{y_sp - y_top}" '
                       f'fill="{NEWWORK}" opacity="0.85"/>')
        body_top = ey(ia.soffit_level_m - item.raise_m)
        out.append(f'<line x1="{xp}" y1="{body_top}" x2="{xp}" y2="{ey(ia.underside_level_m)}" '
                   f'stroke="{colour}" stroke-width="1"/>')
        out.append(f'<rect x="{xp - 5}" y="{ey(ia.underside_level_m) - 8}" width="11" height="8" '
                   f'fill="{colour}" opacity="{1 if governing else 0.5}"/>')

    for lane_a in a.lanes:
        gi = next(i for i in a.items if i.item.item_id == lane_a.governing_item_id)
        lane = next(l for l in c.lanes if l.name == lane_a.lane)
        xp = ex(lane.centre_m())
        y_t, y_b = ey(gi.underside_level_m), ey(gi.road_level_m)
        colour = STATUS_COLOUR[lane_a.status.value]
        mid_y = (y_t + y_b) / 2
        out.append(
            f'<line x1="{xp - 10}" y1="{y_t}" x2="{xp + 10}" y2="{y_t}" stroke="{colour}" stroke-width="0.6" opacity="0.75"/>'
            f'<line x1="{xp - 10}" y1="{y_b}" x2="{xp + 10}" y2="{y_b}" stroke="{colour}" stroke-width="0.6" opacity="0.75"/>'
            f'<line x1="{xp}" y1="{y_t}" x2="{xp}" y2="{y_b}" stroke="{colour}" stroke-width="0.9"/>'
            f'<path d="M {xp} {y_t} l -3 8 l 6 0 Z" fill="{colour}"/>'
            f'<path d="M {xp} {y_b} l -3 -8 l 6 0 Z" fill="{colour}"/>'
            f'<rect x="{xp - 30}" y="{mid_y - 8}" width="60" height="16" fill="#141B26" opacity="0.94"/>'
            f'<text x="{xp}" y="{mid_y + 4}" fill="{colour}" font-size="12" font-family="monospace" '
            f'font-weight="700" text-anchor="middle">{lane_a.min_clearance_m:.3f}</text>')

    # required-clearance datum across the carriageway
    out.append(f'<line x1="{ex(c.left_edge_m)}" y1="{ey(c.surface_level(c.left_edge_m) + a.required_m)}" '
               f'x2="{ex(right)}" y2="{ey(c.surface_level(right) + a.required_m)}" '
               f'stroke="#4FA8E0" stroke-width="1.3" stroke-dasharray="6 4"/>')
    out.append(f'<text x="{ex(right) + 8}" y="{ey(c.surface_level(right) + a.required_m) + 4}" '
               f'fill="#4FA8E0" font-size="10" font-family="monospace">required {a.required_m:.3f} m</text>')

    out.append(f'<line x1="{ex(0)}" y1="{Y0 + 52}" x2="{ex(g.span_m)}" y2="{Y0 + 52}" '
               f'stroke="#455A70" stroke-width="0.8"/>')
    out.append(f'<rect x="{(ex(0) + ex(g.span_m)) / 2 - 38}" y="{Y0 + 45}" width="76" height="14" fill="#141B26"/>')
    out.append(f'<text x="{(ex(0) + ex(g.span_m)) / 2}" y="{Y0 + 56}" fill="#455A70" '
               f'font-size="10" font-family="monospace" text-anchor="middle">{g.span_m * 1000:.0f}</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ sidebar --
st.sidebar.markdown("### Case")
scenario_labels = {
    "as_surveyed": "As surveyed",
    "undersized_spacer": "Undersized spacer",
    "future_overlay": "After resurfacing",
    "overlay_reserved": "Overlay reserved",
    "flatter_gantry": "Minimal camber",
    "already_compliant": "Already compliant",
}
choice = st.sidebar.radio("Case", list(SCENARIOS),
                          format_func=lambda k: scenario_labels.get(k, k),
                          label_visibility="collapsed")
scenario = apply_scenario(choice)

st.sidebar.markdown("### Standard")
std_key = st.sidebar.selectbox(
    "Standard", list(STANDARDS), index=list(STANDARDS).index(
        next(k for k, v in STANDARDS.items() if v.name == scenario.standard.name)),
    format_func=lambda k: STANDARDS[k].name, label_visibility="collapsed")
standard = STANDARDS[std_key]
st.sidebar.caption(standard.note)
br = standard.breakdown()
st.sidebar.markdown(
    f"<div style='font-family:monospace;font-size:11px;color:#6B829B;line-height:1.9'>"
    f"base {br['base']:.3f}<br>overlay reserve {br['overlay_allowance']:.3f}<br>"
    f"survey tolerance {br['survey_tolerance']:.3f}<br>owner margin {br['operator_margin']:.3f}<br>"
    f"<span style='color:#D6E4F0'><b>required {br['required']:.3f} m</b></span></div>",
    unsafe_allow_html=True)

st.sidebar.markdown("### Spacer")
# A case that carries its own forced height is one where an engineer overrode the
# sizing, so the app opens with automatic sizing switched off for it.
forced = scenario.forced_raiser_m
auto = st.sidebar.checkbox("Size it automatically", value=(forced is None),
                           key=f"auto_{choice}")

baseline = assess(scenario.gantry, scenario.carriageway, scenario.items, standard)
sized = plan_remediation(scenario.gantry, scenario.carriageway, scenario.items,
                         standard, baseline)
if auto:
    spacer_mm = int(round(sized.selection.height_m * 1000))
    st.sidebar.markdown(
        f"<div style='font-family:monospace;font-size:22px;font-weight:800;color:{NEWWORK}'>"
        f"{spacer_mm} mm</div>", unsafe_allow_html=True)
    st.sidebar.caption(sized.selection.reason)
else:
    default_mm = int(round((forced if forced is not None
                            else sized.selection.height_m) * 1000))
    options = sorted({0, default_mm} | {int(h * 1000) for h in RAISER_CATALOGUE_M})
    spacer_mm = st.sidebar.select_slider(
        "Height", options=options, value=default_mm,
        label_visibility="collapsed", key=f"mm_{choice}")
    st.sidebar.caption(f"Sizing calls for {sized.selection.height_m * 1000:.0f} mm "
                       f"against a {baseline.worst_deficit_m() * 1000:.0f} mm deficit.")
spacer_m = spacer_mm / 1000.0

# ------------------------------------------------------------------- header --
project = run_pipeline(scenario.gantry, scenario.carriageway, scenario.items,
                       standard, forced_raiser_m=(None if auto else spacer_m))
assert project.plan is not None
rec = advise(project)
live_items = apply_raise(scenario.items, EquipmentType.VR_SENSOR, spacer_m)
live = assess(scenario.gantry, scenario.carriageway, live_items, standard)

st.markdown(
    "<div class='tblock'><h1>Gantry Clearance Assurance</h1>"
    "<div class='sub'>VERTICAL CLEARANCE · NON-CONFORMANCE · REMEDIATION · VERIFICATION</div></div>",
    unsafe_allow_html=True)
st.caption(scenario.note)

released = project.released()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Requirement", f"{live.required_m:.3f} m")
k2.metric("Worst lane", f"{min(l.min_clearance_m for l in live.lanes):.3f} m",
          f"{(min(l.min_clearance_m for l in live.lanes) - live.required_m) * 1000:+.0f} mm")
k3.metric("Lanes short", f"{len(live.non_conforming_lanes())} of {len(live.lanes)}")
k4.metric("Spacer", f"{spacer_mm} mm")
k5.metric("Change", "Released" if released else "Held")

# --------------------------------------------------------------------- tabs --
tab_elev, tab_stage, tab_review, tab_work, tab_html = st.tabs(
    ["Elevation", "Process", "Review", "Work package", "Full animated demo"])

with tab_elev:
    st.markdown(elevation_svg(scenario.gantry, scenario.carriageway, live, spacer_m),
                unsafe_allow_html=True)
    st.caption("True scale. Camber lifts the girder at mid-span; crossfall drops the road "
               "to one side. The tightest gap is where those two work against each other.")

    left, right_col = st.columns([1.15, 1])
    with left:
        st.markdown("##### Clearance by lane")
        rows = []
        for l in live.lanes:
            rows.append({
                "Lane": l.lane,
                "Governing item": LABEL[EquipmentType(l.governing_kind)],
                "Clearance": f"{l.min_clearance_m:.3f} m",
                "On requirement": f"{(l.min_clearance_m - live.required_m) * 1000:+.0f} mm",
                "Status": l.status.value.replace("_", " "),
            })
        st.dataframe(rows, hide_index=True)
        st.bar_chart(
            {l.lane: l.min_clearance_m - live.required_m for l in live.lanes},
            height=210, color=PASS if live.conforming() else FAIL)
        st.caption("Bars show millimetres above or below the requirement.")
    with right_col:
        st.markdown("##### Optics after the fix")
        fov = evaluate_fov(spacer_m)
        base_fov = evaluate_fov(0.0)
        st.metric("Usable tilt window", f"{fov.width_deg():.1f}°",
                  f"{fov.width_deg() - base_fov.width_deg():+.1f}° vs as-built")
        st.metric("Margin at operating tilt", f"{fov.margin_deg:+.1f}°")
        if fov.workable():
            st.success(f"Tilt window {fov.min_tilt_deg:.1f}° to {fov.max_tilt_deg:.0f}°; "
                       f"operating angle sits inside it.")
        else:
            st.error("Beam clips the field of view at the operating tilt. "
                     "Reduce the spacer or move the sensor forward of the beam.")
        for reason in fov.reasons:
            st.markdown(f"<div class='finding'>{reason}</div>", unsafe_allow_html=True)

with tab_stage:
    stage_names = [f"{i + 1:02d} · {STAGE_TITLE[s.stage]}" for i, s in enumerate(project.stages)]
    picked = st.radio("Stage", range(len(project.stages)),
                      format_func=lambda i: stage_names[i],
                      horizontal=True, label_visibility="collapsed")
    s = project.stages[picked]
    colour = VERDICT_COLOUR[s.verdict.value]
    st.markdown(
        f"<div style='font-family:monospace;font-size:11px;color:#455A70;letter-spacing:.06em'>"
        f"{s.question if hasattr(s, 'question') else ''}</div>"
        f"<div style='font-size:19px;font-weight:650;color:{colour};margin:6px 0 12px'>"
        f"{s.headline}</div>", unsafe_allow_html=True)
    for f in s.findings:
        st.markdown(f"<div class='finding'>{f}</div>", unsafe_allow_html=True)

    st.markdown("###### Every stage at a glance")
    cols = st.columns(len(project.stages))
    for col, stage in zip(cols, project.stages):
        c = VERDICT_COLOUR[stage.verdict.value]
        col.markdown(
            f"<div style='border-top:3px solid {c};background:#141B26;padding:8px'>"
            f"<div style='font-family:monospace;font-size:9px;color:#455A70'>"
            f"{STAGE_TITLE[stage.stage].upper()}</div>"
            f"<div style='font-family:monospace;font-size:10px;color:{c};margin-top:4px'>"
            f"{stage.verdict.value}</div></div>", unsafe_allow_html=True)

with tab_review:
    reg = project.register
    st.markdown(f"##### Comment register — {len(reg.comments)} comments, "
                f"{len(reg.hold_points)} hold points")
    cols = st.columns(4)
    for col, state in zip(cols, ["open", "responded", "agreed", "closed"]):
        items = [c for c in reg.comments if c.state.value == state]
        col.markdown(f"**{state.title()}** · {len(items)}")
        for c in items:
            blocking = " blocking" if c.severity.value == "blocking" else ""
            col.markdown(f"<div class='cmt{blocking}'>{c.ref} · {c.section}"
                         f"<small>{c.discipline.value}</small></div>", unsafe_allow_html=True)
    st.markdown("###### Hold points — these cannot be closed by discussion")
    hcols = st.columns(len(reg.hold_points))
    for col, h in zip(hcols, reg.hold_points):
        mark, c = ("✓", PASS) if h.met else ("○", FAIL)
        col.markdown(f"<div style='background:#1A2331;border:1px solid #26313F;padding:9px;"
                     f"font-family:monospace;font-size:10px'><span style='color:{c};"
                     f"font-weight:800'>{mark}</span> {h.ref} {h.title}</div>",
                     unsafe_allow_html=True)
    with st.expander("Responses on the record"):
        for c in reg.comments:
            st.markdown(f"**{c.ref} · {c.section}** — {c.summary}")
            st.caption(c.response or "Awaiting response.")

with tab_work:
    wp = project.workpack
    w1, w2, w3 = st.columns(3)
    w1.metric("Units", wp.item_count)
    w2.metric("Possession", f"{wp.duration_min / 60:.1f} h")
    w3.metric("Lane closures", len(wp.lanes_to_close))
    for note in wp.notes:
        st.markdown(f"<div class='finding'>{note}</div>", unsafe_allow_html=True)
    st.markdown("###### Method")
    for step in wp.steps:
        tag = " · hold point" if step.hold else ""
        st.markdown(f"**{step.order:02d} — {step.title}{tag}**")
        st.caption(step.detail)

with tab_html:
    st.caption("The self-contained demo, embedded. It runs the same engine, ported to "
               "the browser, and animates the whole process.")
    from pathlib import Path
    demo_path = Path(__file__).with_name("demo") / "index.html"
    if not demo_path.exists():
        st.warning("demo/index.html not found. Open it directly in a browser.")
    elif hasattr(st, "iframe"):
        st.iframe(demo_path, height=1500)
    else:
        import streamlit.components.v1 as components
        components.html(demo_path.read_text(), height=1500, scrolling=True)

# ---------------------------------------------------------------- assistant --
st.markdown("---")
prio_colour = {"critical": FAIL, "elevated": MARGINAL, "normal": PASS}[rec.priority]
st.markdown(
    f"<div style='border-left:3px solid {STAMP};background:#141B26;padding:14px 18px'>"
    f"<span style='font-family:monospace;font-size:10px;font-weight:800;text-transform:uppercase;"
    f"letter-spacing:.16em;background:{prio_colour}22;color:{prio_colour};padding:3px 10px'>"
    f"{rec.priority}</span>"
    f"<div style='font-size:16px;font-weight:650;margin:11px 0 4px;color:#D6E4F0'>"
    f"{rec.headline}</div></div>", unsafe_allow_html=True)
for a in rec.actions:
    st.markdown(f"<div class='finding'>{a}</div>", unsafe_allow_html=True)
with st.expander("Show working"):
    st.code("\n".join(rec.trace), language=None)
