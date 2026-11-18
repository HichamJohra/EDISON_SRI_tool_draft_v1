"""Step 4: optimisation – the heart of the EDISON tool.

Generate upgrade scenarios (stochastic run, exact/approximate optimisation, manual points), explore them in a
parallel-coordinates plot whose axis limits filter the valid scenarios, and compare them on SRI, life-cycle cost
(LCC = CAPEX + OPEX), investment, operating costs and new technical requirements.
Figures and state handling are shared with "Detailed analysis" (components/opt_view.py).
"""
import random

import dash
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from components import opt_view as ov
from components.ui import GRAPH_CONFIG, card, page_head
from edison_sri.scenarios import best_choice, optimise

dash.register_page(__name__, path="/optimization", name="4. Optimization", order=4,
                   title="Optimization · EDISON SRI upgrade tool")


def _scatter_card(key: str):
    return card(title=ov.SCATTERS[key][1], subtitle=ov.CLICK_HINT, className="card-expand", children=[
        ov.expand_link(key), ov.colour_control(key, f"opt-col-{key}"),
        dcc.Graph(id=f"opt-g-{key}", config=GRAPH_CONFIG)])


layout = html.Div([
    page_head("4. Optimization",
              "Find the upgrade packages that raise the SRI ↑ while keeping the life-cycle cost ↓ and new "
              "technical requirements ↓, within your objectives & constraints."),
    card(title="Global optimizer", subtitle="Generate scenarios, then explore them below. A scenario sets a "
         "functionality level for every upgradable service of the imported assessment.", children=[
        html.Div(className="action-bar", children=[
            html.Button("Stochastic run", id="opt-stoch", className="btn", title="Add random upgrade packages"),
            html.Span(dcc.Input(id="opt-n", type="number", value=300, min=0, max=2000, step=10,
                                className="field-input n-input"), title="Number of random scenarios"),
            html.Span("scenarios", className="muted"),
            html.Span(className="action-sep"),
            html.Button("Find optimal solution(s)", id="opt-run", className="btn",
                        title="Pareto front of SRI ↑, LCC ↓, new requirements ↓ within the axis limits"),
            html.Span(className="action-sep"),
            html.Button("Generate point from selected levels", id="opt-gen", className="btn btn-outline",
                        title="Evaluate the levels chosen below and add the point"),
            html.Span(className="action-sep"),
            html.Button("Clear scenarios", id="opt-reset", className="btn btn-outline",
                        title="Remove all scenarios except the starting point (imported assessment)"),
            dcc.Link("Analyse SRI report of the selected scenario →", href="/upgraded-assessment",
                     className="btn btn-report",
                     title="Full SRI report of the current selection in “5. SRI upgrade assessment”"),
        ]),
        html.Div(id="opt-status", className="status-line-opt"),
        html.H4("Service levels for a new point", className="mini-title", style={"marginTop": "14px"}),
        html.Div(id="opt-levels", className="level-strip"),
        html.Div("Start level marked “•”. Click a service code for its details in “2. Smart services”. Levels are "
                 "limited by the objectives & constraints (no service lowered, excluded / required services, "
                 "largest level increase).", className="field-hint"),
    ]),
    card(title=ov.FIGURES["pc"], className="card-expand",
         subtitle="Objectives on the left (SRI, LCC, CAPEX, OPEX, new requirements), then key functionalities, "
                  "impact criteria, domains and the level of each service. Drag along an axis to set limits: "
                  "scenarios outside are greyed out here and in the graphs below. Initial limits come from the "
                  "active objectives & constraints. Click a service code (axis title) for its details. "
                  "Scroll sideways for more axes.",
         children=[
             ov.expand_link("pc"),
             html.Div(className="action-bar", children=[
                 html.Button("Reset limits to objectives & constraints", id="opt-reset-filters",
                             className="btn btn-outline"),
                 html.Div(className="legend", children=[
                     html.Span([html.I(style={"background": c}), lab]) for lab, c, _ in ov.SRC_STYLE.values()] +
                     [html.Span([html.I(style={"background": ov.CURRENT_COLOUR}), "Current selection"])]),
             ]),
             html.Div(dcc.Loading(dcc.Graph(id="opt-pc", config=GRAPH_CONFIG, className="pc-graph")),
                      className="pc-scroll"),
         ]),
    card(title=ov.FIGURES["sri"], className="card-expand",
         subtitle="Bars: current selection; grey: largest value reached among all scenarios; red tick: starting "
                  "point. Costs and requirements are shown as % of their largest value among the scenarios.",
         children=[ov.expand_link("sri"), html.Div(id="opt-sri")]),
    html.Div(className="grid-2 opt-graphs", children=[_scatter_card(k) for k in ov.SCATTERS]),
])


# ---------------------------------------------------------------------------------------------------------------
def _levels_strip(c: dict):
    problem, cur = c["problem"], ov.current(c["store"])
    return [html.Div(className="level-box", title=s.name, children=[
        dcc.Link(s.code, href=f"/services?code={s.code}", className="level-code"),
        dcc.Dropdown([{"label": f"{lv}{' •' if lv == s.current else ''}", "value": lv} for lv in s.levels],
                     value=lv, id={"type": "opt-lv", "code": s.code}, clearable=False, searchable=False),
    ]) for s, lv in zip(problem.services, cur["lv"])] or [html.Div("No service can be upgraded within the "
                                                                    "constraints.", className="msg msg-warning")]


SCATTER_KEYS = list(ov.SCATTERS)


# One callback for everything on this page (see the note in pages/assessment.py about page-entry firing).
@callback(Output("store-opt", "data"), Output("store-opt-filters", "data"), Output("opt-status", "children"),
          Output("opt-pc", "figure"), Output("opt-sri", "children"),
          *[Output(f"opt-g-{k}", "figure") for k in SCATTER_KEYS], Output("opt-levels", "children"),
          Input("opt-stoch", "n_clicks"), Input("opt-run", "n_clicks"), Input("opt-gen", "n_clicks"),
          Input("opt-reset", "n_clicks"), Input("opt-reset-filters", "n_clicks"),
          *[Input(f"opt-g-{k}", "clickData") for k in SCATTER_KEYS], Input("opt-pc", "restyleData"),
          *[Input(f"opt-col-{k}", "value") for k in SCATTER_KEYS],
          State("store-opt", "data"), State("store-opt-filters", "data"), State("store-sri", "data"),
          State("store-objectives", "data"), State("opt-n", "value"),
          State({"type": "opt-lv", "code": ALL}, "value"), State({"type": "opt-lv", "code": ALL}, "id"))
def run(_s, _r, _g, _x, _f, *rest):
    clicks, restyle = rest[:4], rest[4]
    colours = rest[5:9]
    store, fstore, stored_sri, stored_obj, n, lv_values, lv_ids = rest[9:]
    trig = ctx.triggered_id
    c = ov.load(stored_sri, stored_obj, store, fstore, clear=trig == "opt-reset",
                reset_filters=trig == "opt-reset-filters")
    problem, params, store = c["problem"], c["params"], c["store"]
    note, rebuild_pc = "", True

    if trig == "opt-reset":
        note = "Scenarios cleared: only the starting point (imported assessment) is left."
    elif trig == "opt-stoch":
        k = min(max(int(n or 300), 10), 2000)
        ov.add(store, [problem.evaluate(lv) for lv in problem.stochastic(k, random.Random())], "stochastic")
        note = f"{k} random scenarios added."
    elif trig == "opt-run":
        front, method = optimise(problem, c["fstore"]["f"], random.Random())
        ids = ov.add(store, front, "optimal")
        best = best_choice(front, params)
        store["method"] = method
        if best is None:
            note = f"No scenario satisfies all limits ({method}). Relax some limits."
        else:
            store["current"] = ids[front.index(best)]
            goal = "lowest LCC" if params["mode"] == "target" else "highest SRI"
            note = (f"Pareto front within the limits: {len(front)} scenarios ({method}). Current selection = "
                    f"{goal} on the front.")
            if best["lv"] == problem.start_levels:
                note += " The starting point already meets the limits: raise a target to see upgrades."
    elif trig == "opt-gen" and lv_values:
        lv_map = {i["code"]: v for i, v in zip(lv_ids, lv_values)}
        levels = [lv_map.get(code, s.current) for code, s in zip(problem.codes, problem.services)]
        store["current"] = ov.add(store, [problem.evaluate(levels)], "manual")[0]
        note = "New point generated from the selected levels."
    elif trig in [f"opt-g-{k}" for k in SCATTER_KEYS]:
        sid = ov.click_id(clicks[SCATTER_KEYS.index(trig[len("opt-g-"):])])
        if sid is not None and any(s["id"] == sid for s in store["scen"]):
            store["current"] = sid
    elif trig == "opt-pc":
        c["fstore"] = {**c["fstore"], "f": ov.parse_restyle(restyle, c["dims"], c["fstore"]["f"])}
        rebuild_pc = False

    valid = ov.valid_ids(c)
    only_colour = isinstance(trig, str) and trig.startswith("opt-col-")
    return (store, c["fstore"], ov.status(c, valid, note),
            ov.pc_figure(c) if rebuild_pc and not only_colour else no_update,
            ov.sri_panel(c) if not only_colour else no_update,
            *[ov.scatter(c, valid, k, ov.colour_value(col)) for k, col in zip(SCATTER_KEYS, colours)],
            _levels_strip(c) if trig not in ("opt-pc",) and not only_colour else no_update)
