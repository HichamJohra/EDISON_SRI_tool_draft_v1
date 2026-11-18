"""Shared state handling and figures of the optimisation pages ("4. Optimization" and "Detailed analysis").

Session stores (app.py):
- store-opt: {"sig", "codes", "scen": [scenario], "current": id, "next_id", "method"}; scenario = evaluated metrics
  (see edison_sri.scenarios.Problem.evaluate) + "id" + "src" (start / stochastic / optimal / manual).
- store-opt-filters: {"seed": objectives used to seed the limits, "f": {dimension key: [low, high]}}.
"""
import json
from typing import Any

import plotly.graph_objects as go
from dash import dcc, html

from edison_sri.parameters import ParameterError, defaults, validate
from edison_sri.scenarios import MAX_SCENARIOS, Problem, dimensions, filters_from_objectives, frontier_2d, is_valid
from edison_sri.sri_assessment import load_example

SRC_STYLE = {  # legend, colour and parcoords colour index of each scenario source
    "stochastic": ("Generated (stochastic)", "#9ecae1", 1),
    "optimal": ("Pareto-optimal", "#7a5195", 2),
    "manual": ("Manual point (history)", "#ff7f0e", 3),
    "start": ("Starting point (imported assessment)", "#d62728", 0),
}
CURRENT_COLOUR, INVALID_COLOUR, FRONT_COLOUR, MAX_COLOUR = "#2ca02c", "#d5dae1", "#b05aa0", "#e6e9ef"
PC_COLORSCALE = [[0, "#d62728"], [0.2, "#d62728"], [0.2, "#9ecae1"], [0.4, "#9ecae1"], [0.4, "#7a5195"],
                 [0.6, "#7a5195"], [0.6, "#ff7f0e"], [0.8, "#ff7f0e"], [0.8, CURRENT_COLOUR], [1, CURRENT_COLOUR]]
KF_SHORT = ["KF1 – building", "KF2 – user", "KF3 – grid"]
IMP_SHORT = ["Energy efficiency", "Energy flexibility and storage", "Comfort", "Convenience", "Health, well-being "
             "and accessibility", "Maintenance and fault prediction", "Information to occupants"]

METRIC = {  # key: (axis / colour-bar title, short label, unit)
    "lcc": ("LCC = CAPEX + OPEX (kNOK)", "LCC", "kNOK"),
    "capex": ("CAPEX – investment (kNOK)", "CAPEX", "kNOK"),
    "opex": ("OPEX – operation, present value (kNOK)", "OPEX", "kNOK"),
    "reqs": ("New technical requirements (number)", "New req.", ""),
}
# Scatter graphs: key → (y metric, card title, colour-scale options, exclusive radio?)
SCATTERS = {
    "lcc": ("lcc", "Life-cycle cost (LCC) against SRI", ["reqs"]),
    "req": ("reqs", "Technical requirements against SRI", ["lcc", "capex", "opex"]),
    "capex": ("capex", "Investment (CAPEX) against SRI", ["reqs"]),
    "opex": ("opex", "Operating costs (OPEX) against SRI", ["reqs"]),
}
FIGURES = {"pc": "Scenarios: parallel coordinates", "sri": "SRI score of the current selection",
           **{k: v[1] for k, v in SCATTERS.items()}}
COST_COLOURS = {"lcc": "#8c1c13", "capex": "#bf4342", "opex": "#e07a5f", "reqs": "#d4a373"}
CLICK_HINT = "Click a point to make it the current selection."
CHECK: Any = {"marginRight": "4px"}


# ---------------------------------------------------------------------------------------------------------------
# State
def params_of(stored) -> dict:
    try:
        return validate(stored or {})[0]
    except ParameterError:
        return defaults()


def _signature(problem: Problem, assessment: dict) -> str:
    return json.dumps([assessment["building"]["name"], round(assessment["results"]["total"], 10), problem.area,
                       problem.db, problem.horizon, problem.rate, [(s.code, s.lo, s.hi) for s in problem.services]])


def new_store(problem: Problem, sig: str) -> dict:
    """Only the starting point: the levels of the imported SRI assessment."""
    start = {"id": 0, "src": "start", **problem.evaluate(problem.start_levels)}
    return {"sig": sig, "codes": problem.codes, "scen": [start], "current": 0, "next_id": 1, "method": ""}


def load(stored_sri, stored_obj, store, fstore, clear=False, reset_filters=False) -> dict:
    """Problem, axes, scenarios and limits for the current assessment and objectives (stores rebuilt when these
    changed, or on request)."""
    assessment = stored_sri or load_example()
    params = params_of(stored_obj)
    problem = Problem(assessment, params)
    dims = dimensions(problem)
    sig = _signature(problem, assessment)
    if clear or not store or store.get("sig") != sig or "lcc" not in store["scen"][0]:
        store = new_store(problem, sig)
    seed = filters_from_objectives(problem, params)
    seed_sig = json.dumps(seed, sort_keys=True)
    if reset_filters or not fstore or fstore.get("seed") != seed_sig:
        fstore = {"seed": seed_sig, "f": seed}
    return {"assessment": assessment, "params": params, "problem": problem, "dims": dims,
            "dims_by_key": {d["key"]: d for d in dims}, "store": store, "fstore": fstore}


def add(store: dict, metrics: list[dict], src: str) -> list[int]:
    """Add scenarios (deduplicated by levels); returns their ids."""
    by_lv = {tuple(s["lv"]): s for s in store["scen"]}
    ids = []
    for m in metrics:
        key = tuple(m["lv"])
        if key in by_lv:
            s = by_lv[key]
            if src in ("optimal", "manual") and s["src"] == "stochastic":
                s["src"] = src
            ids.append(s["id"])
            continue
        s = {"id": store["next_id"], "src": src, **m}
        store["next_id"] += 1
        store["scen"].append(s)
        by_lv[key] = s
        ids.append(s["id"])
    over = len(store["scen"]) - MAX_SCENARIOS
    if over > 0:  # drop the oldest stochastic scenarios
        drop = sorted(s["id"] for s in store["scen"] if s["src"] == "stochastic")[:over]
        drop = set(drop) - {store["current"]}
        store["scen"] = [s for s in store["scen"] if s["id"] not in drop]
    return ids


def current(store: dict) -> dict:
    return next((s for s in store["scen"] if s["id"] == store["current"]), store["scen"][0])


def selected(c: dict, sid=None) -> tuple[dict | None, str]:
    """Scenario with id `sid` (default: the current selection) and its label."""
    store = c["store"]
    try:
        sid = int(sid) if sid not in (None, "") else store["current"]
    except (TypeError, ValueError):
        sid = store["current"]
    scen = next((s for s in store["scen"] if s["id"] == sid), None)
    return scen, ("starting point (initial assessment)" if sid == 0 else f"scenario #{sid}")


def click_id(click) -> int | None:
    if click and click.get("points") and "customdata" in click["points"][0]:
        return int(click["points"][0]["customdata"])
    return None


def parse_restyle(rd, dims: list[dict], filters: dict) -> dict:
    """Update the limits from a parcoords restyleData event (brushing an axis)."""
    if not rd or not isinstance(rd, list) or not isinstance(rd[0], dict):
        return filters
    f = dict(filters)
    for k, v in rd[0].items():
        if not k.startswith("dimensions[") or not k.endswith("constraintrange"):
            continue
        i = int(k[len("dimensions["):k.index("]")])
        if i >= len(dims):
            continue
        rng = v[0] if isinstance(v, list) and v and (v[0] is None or isinstance(v[0], list)) else v
        if rng and isinstance(rng[0], list):  # several ranges on one axis: keep their envelope
            rng = [min(r[0] for r in rng), max(r[1] for r in rng)]
        f[dims[i]["key"]] = [float(rng[0]), float(rng[1])] if rng and None not in rng[:2] else None
    return {k: v for k, v in f.items() if v}


def valid_ids(c: dict) -> set:
    f = c["fstore"]["f"]
    return {s["id"] for s in c["store"]["scen"] if is_valid(s, c["dims_by_key"], f)}


def status(c: dict, valid: set, note: str = "") -> list:
    store = c["store"]
    out = [html.Strong(f"{len(store['scen'])} scenarios"), f" · {len(valid)} within the limits",
           f" · current selection #{store['current']}"]
    if store.get("method"):
        out.append(f" · last optimisation: {store['method']}")
    return ([html.Span(note, className="status-note"), html.Br()] if note else []) + out


# ---------------------------------------------------------------------------------------------------------------
# Figures
def pc_figure(c: dict, full: bool = False) -> go.Figure:
    problem, store, dims, filters = c["problem"], c["store"], c["dims"], c["fstore"]["f"]
    order = {"stochastic": 0, "optimal": 1, "manual": 2, "start": 3}
    scen = sorted(store["scen"], key=lambda s: (order[s["src"]], s["id"] == store["current"]))
    colour = [4 if s["id"] == store["current"] else SRC_STYLE[s["src"]][2] for s in scen]
    pdims = []
    for d in dims:
        vals = [d["get"](s) for s in scen]
        vals = [v if v is not None else 0 for v in vals]
        if d["group"] == "service":
            svc = d["service"]
            rng = [svc.levels[0] - 0.2, svc.levels[-1] + 0.2]
            dim = dict(label=d["label"], values=vals, range=rng, tickvals=svc.levels,
                       ticktext=[f"{lv}•" if lv == svc.current else str(lv) for lv in svc.levels])
        else:
            lo, hi = min(vals), max(vals)
            rng = [lo, hi] if hi > lo else [lo - 1, hi + 1]
            dim = dict(label=d["label"], values=vals, range=rng)
        if d["key"] in filters:
            flo, fhi = filters[d["key"]]
            a = rng[0] if flo is None else min(max(flo, rng[0]), rng[1])
            b = rng[1] if fhi is None else max(min(fhi, rng[1]), rng[0])
            dim["constraintrange"] = [a, max(a, b)]  # a limit outside every scenario greys them all out
        pdims.append(dim)
    fig = go.Figure(go.Parcoords(dimensions=pdims, labelangle=-30, labelside="top",
                                 line=dict(color=colour, colorscale=PC_COLORSCALE, cmin=0, cmax=4),
                                 unselected=dict(line=dict(color=INVALID_COLOUR, opacity=0.35)),
                                 labelfont=dict(size=13 if full else 12), tickfont=dict(size=10)))
    fig.update_layout(width=pc_width(c), height=None if full else 520, margin=dict(l=60, r=60, t=110, b=30),
                      paper_bgcolor="white")
    return fig


def pc_width(c: dict) -> int:
    return max(1300, 92 * len(c["dims"]))


def scatter(c: dict, valid: set, key: str, colour_by: str | None, full: bool = False) -> go.Figure:
    """One of the four 'metric against SRI' graphs, with its 2-D Pareto front (straight segments)."""
    y_key = SCATTERS[key][0]
    store = c["store"]
    scen = store["scen"]
    hover = ("#%{customdata}<br>SRI %{x:.2f} %<br>" + METRIC[y_key][1] + " %{y:,.1f} " + METRIC[y_key][2] +
             "<extra>%{fullData.name}</extra>")
    fig = go.Figure()
    inv = [s for s in scen if s["id"] not in valid and s["src"] != "start"]
    gen = [s for s in scen if s["id"] in valid and s["src"] == "stochastic"]
    if inv:
        fig.add_trace(go.Scatter(x=[s["sri"] for s in inv], y=[s[y_key] for s in inv], mode="markers",
                                 name="Outside limits", marker=dict(size=6, color=INVALID_COLOUR),
                                 customdata=[s["id"] for s in inv], hovertemplate=hover))
    if gen:
        mk = dict(size=8, color=SRC_STYLE["stochastic"][1])
        if colour_by:
            mk = dict(size=8, color=[s[colour_by] for s in gen], colorscale="Viridis", showscale=True,
                      colorbar=dict(title=METRIC[colour_by][1], thickness=12, len=0.8))
        fig.add_trace(go.Scatter(x=[s["sri"] for s in gen], y=[s[y_key] for s in gen], mode="markers",
                                 name="Generated cases", marker=mk, customdata=[s["id"] for s in gen],
                                 hovertemplate=hover))
    pts = frontier_2d([(s["sri"], s[y_key]) for s in scen if s["id"] in valid])
    if len(pts) > 1:
        fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="lines", name="Pareto front",
                                 line=dict(color=FRONT_COLOUR, width=2), hoverinfo="skip"))
    for src, symbol, size in (("optimal", "circle", 9), ("manual", "diamond", 11), ("start", "circle", 14)):
        sel = [s for s in scen if s["src"] == src and (src == "start" or s["id"] in valid)]
        if sel:
            fig.add_trace(go.Scatter(x=[s["sri"] for s in sel], y=[s[y_key] for s in sel], mode="markers",
                                     name=SRC_STYLE[src][0], customdata=[s["id"] for s in sel], hovertemplate=hover,
                                     marker=dict(size=size, symbol=symbol, color=SRC_STYLE[src][1],
                                                 line=dict(color="white", width=1))))
    cur = current(store)
    fig.add_trace(go.Scatter(x=[cur["sri"]], y=[cur[y_key]], mode="markers", name="Current selection",
                             customdata=[cur["id"]], hovertemplate=hover,
                             marker=dict(size=18, color=CURRENT_COLOUR, line=dict(color="white", width=2))))
    fig.update_layout(height=None if full else 420, margin=dict(l=70, r=10, t=10, b=40), plot_bgcolor="white",
                      paper_bgcolor="white", clickmode="event",
                      xaxis=dict(title="Total SRI (%)", gridcolor="#dfe3ea", ticksuffix=" %"),
                      yaxis=dict(title=METRIC[y_key][0], gridcolor="#dfe3ea", rangemode="tozero"),
                      legend=dict(orientation="v", x=1.02, y=1, font_size=11, xanchor="left"))
    if colour_by:  # colour bar and legend side by side
        fig.update_layout(legend=dict(orientation="h", x=0, y=-0.2, yanchor="top", xanchor="left"), margin_b=120)
    return fig


def _bars(names, cur, mx, start, colours, texts, hover_unit, xaxis, max_label="Largest among the scenarios"):
    """Horizontal bars: current value (colour), largest value among all scenarios (grey), start (red tick)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=mx, orientation="h", marker_color=MAX_COLOUR, name=max_label,
                         hovertemplate="%{y}: %{x:.1f}" + hover_unit + "<extra>largest among the scenarios</extra>"))
    fig.add_trace(go.Bar(y=names, x=cur, orientation="h", marker_color=colours, name="Current selection",
                         text=texts, textposition="outside", cliponaxis=False,
                         hovertemplate="%{y}: %{x:.1f}" + hover_unit + "<extra>current selection</extra>"))
    if start is not None:
        fig.add_trace(go.Scatter(y=names, x=start, mode="markers", name="Starting point",
                                 marker=dict(symbol="line-ns-open", size=18, color="#d62728", line=dict(width=3)),
                                 hovertemplate="%{y}: %{x:.1f}" + hover_unit + "<extra>start</extra>"))
    fig.update_layout(height=34 * len(names) + 50, margin=dict(l=10, r=60, t=6, b=36), plot_bgcolor="white",
                      paper_bgcolor="white", showlegend=False, barmode="overlay", bargap=0.3, xaxis=xaxis,
                      yaxis=dict(autorange="reversed", automargin=True))
    return fig


def _mx(store: dict, get) -> float:
    vals = [get(s) for s in store["scen"]]
    return max([v for v in vals if v is not None] or [0])


def sri_panel(c: dict) -> list:
    """KPIs, SRI bars (two sections), cost bars and the list of upgraded services of the current selection."""
    problem, store = c["problem"], c["store"]
    cur, start = current(store), store["scen"][0]
    pct_axis = dict(range=[0, 112], ticksuffix=" %", gridcolor="#dfe3ea")

    # Section 1: total, key functionalities, impact criteria
    g1 = [lambda s: s["sri"]] + [lambda s, i=i: s["kf"][i] for i in range(3)] + \
         [lambda s, k=k: s["imp"][k] for k in range(7)]
    n1 = ["Total SRI"] + KF_SHORT + IMP_SHORT
    col1 = ["#028090"] + ["#1f4e79"] * 3 + ["#3d6fa5"] * 7
    f1 = _bars(n1, [g(cur) for g in g1], [_mx(store, g) for g in g1], [g(start) for g in g1], col1,
               [f"{g(cur):.0f} %" for g in g1], " %", pct_axis)
    # Section 2: domains, then costs and requirements (reddish, % of the largest value among the scenarios)
    g2 = [lambda s, j=j: s["dom"][j] for j in range(len(problem.domains))]
    d_cur = [g(cur) or 0 for g in g2]
    f2 = _bars(problem.domains, d_cur, [_mx(store, g) for g in g2], [g(start) or 0 for g in g2],
               ["#2e75b6"] * len(g2), [f"{v:.0f} %" for v in d_cur], " %", pct_axis)
    keys = ["lcc", "capex", "opex", "reqs"]
    mx = {k: _mx(store, lambda s, k=k: s[k]) for k in keys}
    norm = {k: 100 * cur[k] / mx[k] if mx[k] else 0 for k in keys}
    txt = [f"{cur['lcc']:,.0f} kNOK", f"{cur['capex']:,.0f} kNOK",
           f"{cur['opex']:,.0f} kNOK ({cur['opex_y']:,.1f} kNOK/yr)", f"{cur['reqs']} items"]
    f3 = _bars(["LCC", "CAPEX", "OPEX", "New tech. req."], [norm[k] for k in keys], [100] * 4, None,
               [COST_COLOURS[k] for k in keys], [t.replace(",", " ") for t in txt], " %",
               dict(range=[0, 135], ticksuffix=" %", gridcolor="#dfe3ea",
                    title=dict(text="% of the largest value among the scenarios", font_size=11)))
    f3.update_traces(hovertemplate="%{y}: %{x:.0f} % of the largest<extra></extra>")
    f3.update_layout(height=200)

    def k(label, value, sub, cls="kpi"):
        return html.Div([html.Div(label, className="kpi-label"), html.Div(value, className="kpi-value"),
                         html.Div(sub, className="kpi-sub")], className=cls)

    def nok(x, unit="kNOK"):
        return f"{x:,.0f} {unit}".replace(",", " ")

    kpis = html.Div(className="kpi-mini-row", children=[
        k("Total SRI", f"{cur['sri']:.1f} %", f"{cur['sri'] - start['sri']:+.2f} pt vs start", "kpi kpi-main"),
        k("LCC", nok(cur["lcc"]), f"{problem.horizon:.0f} years, {problem.rate:g} % discount", "kpi kpi-cost"),
        k("CAPEX", nok(cur["capex"]), nok(1e3 * cur["capex"] / problem.area, "NOK/m²"), "kpi kpi-cost"),
        k("OPEX", nok(cur["opex_y"], "kNOK/yr"), f"present value {nok(cur['opex'])}", "kpi kpi-cost"),
        k("New tech. req.", str(cur["reqs"]), "items to install", "kpi kpi-cost"),
    ])
    changes = [(s.code, s.name, s.current, lv) for s, lv in zip(problem.services, cur["lv"]) if lv != s.current]
    upgrades = html.Div([
        html.H4(f"Upgrades in the current selection (#{cur['id']})", className="mini-title"),
        html.Table(className="info-table compare-table", children=html.Tbody([
            html.Tr([html.Td(dcc.Link(code, href=f"/services?code={code}", className="link-strong")),
                     html.Td(dcc.Link(name, href=f"/services?code={code}")), html.Td(f"{a} → {b}", className="num")])
            for code, name, a, b in changes
        ])) if changes else html.Div("No upgrade: the starting point.", className="muted"),
    ], style={"marginTop": "10px"})
    legend = html.Div(className="legend", children=[
        html.Span([html.I(style={"background": "#2e75b6"}), "Current selection"]),
        html.Span([html.I(style={"background": MAX_COLOUR, "height": "10px"}), "Largest among all scenarios"]),
        html.Span([html.I(style={"background": "#d62728", "width": "4px", "height": "14px"}), "Starting point"]),
    ])
    return [kpis, legend, html.Div(className="grid-2 sri-sections", children=[
        html.Div([html.H4("SRI, key functionalities and impact criteria", className="mini-title"),
                  dcc.Graph(figure=f1, config={"displaylogo": False})]),
        html.Div([html.H4("Technical domains", className="mini-title"),
                  dcc.Graph(figure=f2, config={"displaylogo": False}),
                  html.H4("Costs and technical requirements", className="mini-title cost-title"),
                  dcc.Graph(figure=f3, config={"displaylogo": False})]),
    ]), upgrades]


def colour_control(key: str, cid) -> Any:
    """Colour-scale control of a scatter graph: a checkbox (one option) or exclusive radio buttons."""
    opts = SCATTERS[key][2]
    if len(opts) == 1:
        return dcc.Checklist([{"label": f" Colour scale: {METRIC[opts[0]][0].split(' (')[0].lower()}",
                               "value": opts[0]}], [], id=cid, inputStyle=CHECK, className="toggle")
    return dcc.RadioItems([{"label": " No colour scale", "value": ""}] +
                          [{"label": f" {METRIC[o][1]}", "value": o} for o in opts], "", id=cid,
                          inline=True, inputStyle=CHECK, className="toggle radio-inline",
                          labelStyle={"marginRight": "14px"})


def colour_value(v) -> str | None:
    if isinstance(v, list):
        return v[0] if v else None
    return v or None


def expand_link(key: str) -> dcc.Link:
    return dcc.Link("⤢ Full screen", href=f"/analysis?fig={key}", className="expand-link",
                    title="Open this figure in “Detailed analysis”")
