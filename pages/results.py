"""Step 6: upgrade plan of the selected scenario (current selection of "4. Optimization").

Combines the initial SRI assessment, the objectives & constraints and the upgraded scenario: measures with
explanations and a suggested order, technical requirements, distribution of costs per service and domain, CAPEX,
OPEX and LCC, and the check of every active objective and constraint. Export as Excel / JSON or print to PDF.
"""
import dash
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from components import opt_view as ov
from components.exports import export_bar, print_callback
from components.ui import GRAPH_CONFIG, card, info_table, page_head
from edison_sri.plan import IMPACT_NAMES, KF_LABELS, build_plan, plan_json, plan_xlsx

dash.register_page(__name__, path="/results", name="6. Upgrade plan", order=6,
                   title="Upgrade plan · EDISON SRI upgrade tool")

CAPEX_C, OPEX_C, INIT_C, UPG_C = "#bf4342", "#e07a5f", "#9aa7b4", "#1f4e79"
STATUS_CLASS = {"met": "status-met", "not met": "status-not-met", "not evaluated in the draft": "status-na"}

layout = html.Div([
    dcc.Store(id="pl-init", data=1),
    export_bar("pl", [("xlsx", "Export report (Excel)"), ("json", "Export JSON")],
               "Plan of the current selection in “4. Optimization”."),
    dcc.Loading(html.Div(id="pl-body"), type="default"),
])
print_callback("pl")

STATES = [State("store-opt", "data"), State("store-opt-filters", "data"), State("store-sri", "data"),
          State("store-objectives", "data")]


def _plan(store, fstore, stored_sri, stored_obj):
    c = ov.load(stored_sri, stored_obj, store, fstore)
    scen, label = ov.selected(c)
    return build_plan(c["assessment"], c["params"], c["problem"], scen, label)


def _nok(x: float, unit: str = "NOK") -> str:
    return f"{x:,.0f} {unit}".replace(",", " ").strip()


def _fmt(v, unit: str = "") -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return (f"{v:.1f}" if abs(v) < 1000 else f"{v:,.0f}".replace(",", " ")) + (f" {unit}" if unit else "")
    return f"{v} {unit}".strip() if isinstance(v, int) else str(v)


def _layout_fig(fig: go.Figure, height: int, **kw) -> go.Figure:
    kw = {"legend": dict(orientation="h", y=-0.12), "margin": dict(l=10, r=20, t=10, b=40), **kw}
    fig.update_layout(height=height, plot_bgcolor="white", paper_bgcolor="white", **kw)
    fig.update_xaxes(gridcolor="#dfe3ea")
    fig.update_yaxes(gridcolor="#dfe3ea")
    return fig


def _figures(p: dict) -> dict:
    ms = list(reversed(p["measures"]))  # first priority on top
    names = [f"{m['code']} (#{m['priority']})" for m in ms]
    f_services = go.Figure([
        go.Bar(y=names, x=[m["capex"] / 1e3 for m in ms], orientation="h", name="CAPEX", marker_color=CAPEX_C,
               hovertemplate="%{y}: %{x:,.0f} kNOK<extra>CAPEX</extra>"),
        go.Bar(y=names, x=[(m["lcc"] - m["capex"]) / 1e3 for m in ms], orientation="h", name="OPEX (present value)", marker_color=OPEX_C,
               hovertemplate="%{y}: %{x:,.0f} kNOK<extra>OPEX, present value</extra>"),
    ])
    _layout_fig(f_services, 30 * len(ms) + 110, barmode="stack", xaxis_title="kNOK (LCC = CAPEX + OPEX)",
                yaxis=dict(automargin=True), legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                margin=dict(l=10, r=20, t=30, b=40))
    d = p["by_domain"]
    f_domains = go.Figure(go.Pie(labels=[x["domain"] for x in d], values=[x["lcc"] / 1e3 for x in d], hole=0.5,
                                 sort=False, textinfo="percent", hovertemplate="%{label}: %{value:,.0f} kNOK"
                                 "<extra>LCC</extra>"))
    _layout_fig(f_domains, 340, legend=dict(orientation="v", x=1, y=0.5))
    c = p["costs"]
    f_lcc = go.Figure(go.Pie(labels=["CAPEX (investment)", "OPEX (operation, present value)"],
                             values=[c["capex"] / 1e3, c["opex"] / 1e3], hole=0.5, sort=False,
                             marker_colors=[CAPEX_C, OPEX_C], textinfo="percent+value",
                             texttemplate="%{value:,.0f} kNOK<br>%{percent}",
                             hovertemplate="%{label}: %{value:,.0f} kNOK<extra></extra>"))
    _layout_fig(f_lcc, 320, legend=dict(orientation="h", y=-0.05))
    cash = p["cash_flow"]
    f_cash = go.Figure(go.Scatter(x=[x["year"] for x in cash], y=[x["cumulative_cost"] / 1e3 for x in cash],
                                  mode="lines+markers", line=dict(color=CAPEX_C), fill="tozeroy",
                                  fillcolor="rgba(191,67,66,.12)",
                                  hovertemplate="Year %{x}: %{y:,.0f} kNOK<extra></extra>"))
    _layout_fig(f_cash, 320, xaxis_title="Year", yaxis=dict(title="Cumulative discounted cost (kNOK)",
                                                           rangemode="tozero"), showlegend=False)
    i, u = p["initial"], p["upgraded"]
    labels = ["Total SRI"] + KF_LABELS + IMPACT_NAMES + p["domains"]
    vi = [i["sri"]] + i["kf"] + i["imp"] + [v or 0 for v in i["dom"]]
    vu = [u["sri"]] + u["kf"] + u["imp"] + [v or 0 for v in u["dom"]]
    f_scores = go.Figure([
        go.Bar(y=labels, x=vi, orientation="h", name="Initial", marker_color=INIT_C,
               hovertemplate="%{y}: %{x:.1f} %<extra>initial</extra>"),
        go.Bar(y=labels, x=vu, orientation="h", name="Upgraded", marker_color=UPG_C,
               text=[f"{b:.0f} %" + (f" ({b - a:+.1f})" if abs(b - a) > 0.05 else "") for a, b in zip(vi, vu)],
               textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x:.1f} %<extra>upgraded</extra>"),
    ])
    _layout_fig(f_scores, 22 * 2 * len(labels) + 80, barmode="group", bargap=0.25,
                xaxis=dict(range=[0, 118], ticksuffix=" %"), yaxis=dict(autorange="reversed", automargin=True))
    return {"services": f_services, "domains": f_domains, "lcc": f_lcc, "cash": f_cash, "scores": f_scores}


def _measure(m: dict) -> html.Div:
    return html.Div(className="measure", children=[
        html.Div(str(m["priority"]), className="measure-num"),
        html.Div(className="measure-body", children=[
            html.Div(className="measure-head", children=[
                dcc.Link(m["code"], href=f"/services?code={m['code']}", className="link-strong"),
                html.Span(f" {m['service']}", className="measure-title"),
                html.Span(f"level {m['from']} → {m['to']}", className="badge"),
                html.Span(m["domain"], className="badge badge-light"),
            ]),
            html.P(m["explanation"], className="measure-text"),
            html.Div(className="measure-facts", children=[
                html.Span(f"ΔSRI alone {m['d_sri_alone']:+.2f} pt"),
                html.Span(f"CAPEX {_nok(m['capex'])}"), html.Span(f"OPEX {_nok(m['opex_y'], 'NOK/yr')}"),
                html.Span(f"LCC {_nok(m['lcc'])}"),
                html.Span("Key functionalities: " + (", ".join(k.split(" – ")[0].replace("Key functionality ", "KF")
                                                               for k in m["key_functionalities"]) or "–")),
            ]),
            html.Div(["Technical requirements: ", html.Span("; ".join(m["requirements"]) or "none (uses equipment "
                                                            "installed for other upgrades)", className="muted")],
                     className="measure-reqs"),
        ]),
    ])


@callback(Output("pl-body", "children"), Input("pl-init", "data"), *STATES)
def show(_, store, fstore, stored_sri, stored_obj):
    p = _plan(store, fstore, stored_sri, stored_obj)
    i, u, c, st = p["initial"], p["upgraded"], p["costs"], p["settings"]
    ms = p["measures"]
    head = page_head(f"6. Upgrade plan – {p['label']}",
                     f"{p['building']['name']} · decision mode: {st['mode']} · cost database: {st['cost_db']} · "
                     f"{_nok(st['floor_area_m2'], 'm²')}. Draft: dummy technical requirements, prices and operating "
                     "costs.")
    if not ms:
        return html.Div([head, html.Div(["The current selection is the initial assessment: there is nothing to "
                                         "upgrade. Choose a scenario in ",
                                         dcc.Link("4. Optimization", href="/optimization", className="link-strong"),
                                         " (click a point in a graph, or find the optimal solutions)."],
                                        className="msg msg-info")])
    n_met = sum(r["status"] == "met" for r in p["criteria"])
    n_not = sum(r["status"] == "not met" for r in p["criteria"])
    domains = sorted({m["domain"] for m in ms})
    text = (f"The plan upgrades {len(ms)} smart-ready services in {len(domains)} technical domains "
            f"({', '.join(domains)}). It raises the total SRI from {i['sri']:.1f} % (class {i['class']}) to "
            f"{u['sri']:.1f} % (class {u['class']}), {u['sri'] - i['sri']:+.2f} points. It needs "
            f"{len(p['requirements'])} new technical requirements, an investment (CAPEX) of {_nok(c['capex'])} "
            f"({_nok(c['capex_per_m2'], 'NOK/m²')}) and {_nok(c['opex_y'], 'NOK')} per year of operation and "
            f"maintenance (OPEX), i.e. a life-cycle cost of {_nok(c['lcc'])} over {st['lcc_horizon']:.0f} years at a "
            f"{st['discount_rate']:g} % discount rate. Of the active objectives and constraints, {n_met} are met"
            + (f" and {n_not} are not met." if n_not else ".") +
            " Measures are listed in the suggested order: most SRI per NOK of life-cycle cost first.")

    def kpi(lab, val, sub, cls="kpi kpi-cost"):
        return html.Div([html.Div(lab, className="kpi-label"), html.Div(val, className="kpi-value"),
                         html.Div(sub, className="kpi-sub")], className=cls)

    kpis = html.Div(className="kpi-mini-row", children=[
        kpi("Total SRI", f"{i['sri']:.1f} → {u['sri']:.1f} %", f"class {i['class']} → {u['class']}", "kpi kpi-main"),
        kpi("LCC", _nok(c["lcc"] / 1e3, "kNOK"), f"{st['lcc_horizon']:.0f} years, {st['discount_rate']:g} %"),
        kpi("CAPEX", _nok(c["capex"] / 1e3, "kNOK"), _nok(c["capex_per_m2"], "NOK/m²")),
        kpi("OPEX", _nok(c["opex_y"] / 1e3, "kNOK/yr"), f"present value {_nok(c['opex'] / 1e3, 'kNOK')}"),
        kpi("New tech. req.", str(len(p["requirements"])), f"for {len(ms)} upgraded services"),
    ])
    criteria = html.Table(className="info-table compare-table", children=[
        html.Thead(html.Tr([html.Th(x) for x in ("Criterion", "Type", "Target", "Reached", "Status")])),
        html.Tbody([html.Tr([html.Td(r["criterion"]), html.Td(r["kind"]),
                             html.Td(f"{r['operator']} {_fmt(r['target'], r['unit'])}"),
                             html.Td(_fmt(r["reached"], r["unit"] if isinstance(r["reached"], (int, float)) else "")),
                             html.Td(html.Span(r["status"], className=f"status {STATUS_CLASS[r['status']]}"))])
                    for r in p["criteria"]]),
    ]) if p["criteria"] else html.Div("No active objective or constraint.", className="muted")
    req_rows = [{"Technical requirement": r["requirement"], "Used by": ", ".join(r["used_by"]),
                 "CAPEX (NOK)": _nok(r["capex"], ""), "OPEX (NOK/yr)": _nok(r["opex_y"], "")}
                for r in p["requirements"]]
    req_rows.append({"Technical requirement": html.Strong("Total"), "Used by": "",
                     "CAPEX (NOK)": html.Strong(_nok(c["capex"], "")), "OPEX (NOK/yr)": html.Strong(_nok(c["opex_y"], ""))})
    f = _figures(p)
    graph = lambda k: dcc.Graph(figure=f[k], config=GRAPH_CONFIG)  # noqa: E731
    return html.Div(className="plan", children=[
        head,
        card([kpis, html.P(text, className="plan-summary")], title="Summary"),
        card(criteria, title="Objectives & constraints",
             subtitle="Active criteria of “3. Objectives & constraints” and the value reached by the plan."),
        card(html.Div([_measure(m) for m in ms]), title="Upgrade measures",
             subtitle="In the suggested order (SRI gain per NOK of life-cycle cost). ΔSRI alone = gain of the measure "
                      "on its own; the total gain of the plan also includes interactions between measures."),
        html.Div(className="grid-2", children=[
            card(graph("services"), title="Cost per upgraded service",
                 subtitle="Shared equipment is split equally between the services that need it."),
            card(graph("domains"), title="Life-cycle cost per domain"),
        ]),
        html.Div(className="grid-2", children=[
            card(graph("lcc"), title="Life-cycle cost: CAPEX and OPEX",
                 subtitle=f"OPEX = present value of {_nok(c['opex_y'], 'NOK/yr')} over {st['lcc_horizon']:.0f} "
                          f"years at {st['discount_rate']:g} %."),
            card(graph("cash"), title="Cumulative discounted cost",
                 subtitle="Investment in year 0, then operation and maintenance every year."),
        ]),
        card(html.Div(info_table(req_rows), className="table-scroll"), title="Technical requirements to install",
             subtitle="Building-wide list: equipment already in the building is not repeated; shared equipment is "
                      "listed once."),
        card(graph("scores"), title="Scores: initial and upgraded",
             subtitle="Total SRI, key functionalities, impact criteria and technical domains (change in points)."),
    ])


@callback(Output("pl-download", "data"), Input("pl-dl-xlsx", "n_clicks"), Input("pl-dl-json", "n_clicks"),
          *STATES, prevent_initial_call=True)
def download(_x, _j, store, fstore, stored_sri, stored_obj):
    if ctx.triggered_id not in ("pl-dl-xlsx", "pl-dl-json"):
        return no_update
    p = _plan(store, fstore, stored_sri, stored_obj)
    name = f"EDISON_upgrade_plan_{p['label'].split(' (')[0].replace(' ', '_').replace('#', '')}"
    if ctx.triggered_id == "pl-dl-json":
        return dcc.send_bytes(plan_json(p), f"{name}.json")
    return dcc.send_bytes(plan_xlsx(p), f"{name}.xlsx")
