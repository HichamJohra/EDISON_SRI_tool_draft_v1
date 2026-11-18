"""Detailed analysis: one figure of "4. Optimization" in full screen (same scenarios, limits and selection)."""
import dash
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from components import opt_view as ov
from components.ui import GRAPH_CONFIG

dash.register_page(__name__, path="/analysis", name="Detailed analysis", order=90, nav=False,
                   title="Detailed analysis · EDISON SRI upgrade tool")

COLOUR_OPTIONS = [{"label": " No colour scale", "value": ""}] + \
                 [{"label": f" {ov.METRIC[k][1]}", "value": k} for k in ("reqs", "lcc", "capex", "opex")]
DEFAULT_COLOUR = {"lcc": "reqs", "req": "lcc", "capex": "reqs", "opex": "reqs"}


def layout(fig: str = "pc", **_):
    fig = fig if fig in ov.FIGURES else "pc"
    return html.Div(className="analysis-page", children=[
        html.Div(className="analysis-bar", children=[
            dcc.Link("← 4. Optimization", href="/optimization", className="btn btn-outline"),
            html.H1("Detailed analysis", className="analysis-title"),
            dcc.Dropdown([{"label": v, "value": k} for k, v in ov.FIGURES.items()], fig, id="an-fig",
                         clearable=False, searchable=False, className="analysis-select"),
            html.Div(dcc.RadioItems(COLOUR_OPTIONS, DEFAULT_COLOUR.get(fig, ""), id="an-colour", inline=True,
                                    inputStyle=ov.CHECK, labelStyle={"marginRight": "12px"}, className="toggle"),
                     id="an-colour-box"),
        ]),
        html.Div(id="an-status", className="status-line-opt"),
        html.Div(id="an-hint", className="field-hint"),
        html.Div(dcc.Graph(id="an-graph", config=GRAPH_CONFIG, className="pc-graph",
                           style={"height": "calc(100vh - 220px)", "minHeight": "520px"}), id="an-graph-box"),
        html.Div(id="an-sri", className="card"),
    ])


@callback(Output("store-opt", "data", allow_duplicate=True), Output("store-opt-filters", "data", allow_duplicate=True),
          Output("an-status", "children"), Output("an-hint", "children"), Output("an-graph", "figure"),
          Output("an-graph-box", "className"), Output("an-graph", "style"), Output("an-sri", "children"),
          Output("an-sri", "style"), Output("an-colour-box", "style"),
          Input("an-fig", "value"), Input("an-colour", "value"), Input("an-graph", "clickData"),
          Input("an-graph", "restyleData"),
          State("store-opt", "data"), State("store-opt-filters", "data"), State("store-sri", "data"),
          State("store-objectives", "data"), State("an-graph", "style"), prevent_initial_call="initial_duplicate")
def show(fig, colour, click, restyle, store, fstore, stored_sri, stored_obj, style):
    trig = ctx.triggered_id
    c = ov.load(stored_sri, stored_obj, store, fstore)
    if trig == "an-graph" and ctx.triggered[0]["prop_id"].endswith("restyleData") and fig == "pc":
        c["fstore"] = {**c["fstore"], "f": ov.parse_restyle(restyle, c["dims"], c["fstore"]["f"])}
        return c["store"], c["fstore"], ov.status(c, ov.valid_ids(c)), *([no_update] * 7)
    if trig == "an-graph" and fig in ov.SCATTERS:
        sid = ov.click_id(click)
        if sid is not None and any(s["id"] == sid for s in c["store"]["scen"]):
            c["store"]["current"] = sid
    valid = ov.valid_ids(c)
    hidden, shown = {"display": "none"}, {}
    style = {**(style or {}), "minWidth": f"{ov.pc_width(c)}px" if fig == "pc" else "0"}
    if fig == "sri":
        return (c["store"], c["fstore"], ov.status(c, valid), "", no_update, "", {**style, "display": "none"},
                ov.sri_panel(c), shown, hidden)
    style.pop("display", None)
    if fig == "pc":
        hint = ("Drag along an axis to set limits; click a service code (axis title) for its details. "
                "Scroll sideways for more axes.")
        figure, box, colour_style = ov.pc_figure(c, full=True), "pc-scroll", hidden
    else:
        hint = ov.CLICK_HINT
        figure, box, colour_style = ov.scatter(c, valid, fig, colour or None, full=True), "", shown
    return c["store"], c["fstore"], ov.status(c, valid), hint, figure, box, style, "", hidden, colour_style
