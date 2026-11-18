"""Step 5: SRI upgrade assessment – full SRI report of one scenario (default: the current selection of
"4. Optimization"), compared with the initial assessment, with its upgraded services, the technical requirements
to install and their costs. Export as JSON (same format as an imported assessment) or Excel, or print to PDF."""
import dash
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from components import opt_view as ov
from components.exports import export_bar, print_callback
from components.sri_report import render
from components.ui import card, info_table, page_head
from edison_sri.plan import assessment_json, assessment_xlsx, upgraded_assessment

dash.register_page(__name__, path="/upgraded-assessment", name="5. SRI upgrade assessment", order=5,
                   title="SRI upgrade assessment · EDISON SRI upgrade tool")


def layout(id=None, **_):  # noqa: A002 – query parameter name in the URL (?id=12)
    return html.Div([
        dcc.Store(id="sc-id", data=id),
        export_bar("sc", [("json", "Download JSON"), ("xlsx", "Download Excel")],
                   "JSON can be imported again in “1. Initial SRI assessment”."),
        dcc.Loading(html.Div(id="sc-body"), type="default"),
    ])


print_callback("sc")


def _nok(x: float, unit: str = "NOK") -> str:
    return f"{x:,.0f} {unit}".replace(",", " ").strip()


def _scenario_data(sid, store, fstore, stored_sri, stored_obj):
    c = ov.load(stored_sri, stored_obj, store, fstore)
    scen, label = ov.selected(c, sid)
    if scen is None:
        return c, None, label, None
    data = upgraded_assessment(c["assessment"], dict(zip(c["problem"].codes, scen["lv"])), label, scen)
    return c, scen, label, data


STATES = [State("sc-id", "data"), State("store-opt", "data"), State("store-opt-filters", "data"),
          State("store-sri", "data"), State("store-objectives", "data")]


@callback(Output("sc-body", "children"), Input("sc-id", "data"), *STATES[1:])
def show(sid, store, fstore, stored_sri, stored_obj):
    c, scen, label, data = _scenario_data(sid, store, fstore, stored_sri, stored_obj)
    if scen is None:
        return html.Div("Scenario not found: generate scenarios in “4. Optimization” first.",
                        className="msg msg-warning")
    problem, start = c["problem"], c["store"]["scen"][0]
    changes = [(s, lv) for s, lv in zip(problem.services, scen["lv"]) if lv != s.current]
    reqs = problem.new_requirements(scen["lv"])
    src = ov.SRC_STYLE[scen["src"]][0]

    def kpi(lab, val, sub, cls="kpi kpi-cost"):
        return html.Div([html.Div(lab, className="kpi-label"), html.Div(val, className="kpi-value"),
                         html.Div(sub, className="kpi-sub")], className=cls)

    kpis = html.Div(className="kpi-mini-row", children=[
        kpi("Total SRI", f"{scen['sri']:.1f} %", f"{scen['sri'] - start['sri']:+.2f} pt vs initial", "kpi kpi-main"),
        kpi("LCC", _nok(scen["lcc"], "kNOK"), f"{problem.horizon:.0f} years, {problem.rate:g} % discount"),
        kpi("CAPEX", _nok(scen["capex"], "kNOK"), _nok(1e3 * scen["capex"] / problem.area, "NOK/m²")),
        kpi("OPEX", _nok(scen["opex_y"], "kNOK/yr"), f"present value {_nok(scen['opex'], 'kNOK')}"),
        kpi("New tech. req.", str(scen["reqs"]), "items to install"),
    ])
    services = html.Table(className="info-table compare-table", children=[
        html.Thead(html.Tr([html.Th("Code"), html.Th("Service"), html.Th("Domain"), html.Th("Level")])),
        html.Tbody([html.Tr([html.Td(dcc.Link(s.code, href=f"/services?code={s.code}", className="link-strong")),
                             html.Td(dcc.Link(s.name, href=f"/services?code={s.code}")), html.Td(s.domain),
                             html.Td(f"{s.current} → {lv}", className="num")]) for s, lv in changes]),
    ]) if changes else html.Div("No upgrade: this is the initial assessment.", className="muted")
    req_rows = [{"Technical requirement": r["requirement"], "CAPEX (NOK)": _nok(r["capex"], ""),
                 "OPEX (NOK/yr)": _nok(r["opex_y"], "")} for r in reqs]
    if req_rows:
        req_rows.append({"Technical requirement": html.Strong("Total"),
                         "CAPEX (NOK)": html.Strong(_nok(1e3 * scen["capex"], "")),
                         "OPEX (NOK/yr)": html.Strong(_nok(1e3 * scen["opex_y"], ""))})
    requirements = info_table(req_rows) if req_rows else html.Div("Nothing to install.", className="muted")

    return html.Div([
        page_head(f"5. SRI upgrade assessment – {label}",
                  f"{src} · {len(changes)} upgraded services · SRI {start['sri']:.1f} % → {scen['sri']:.1f} %. "
                  "Draft: dummy technical requirements, prices and operating costs."),
        card(kpis, title="Scenario summary"),
        html.Div(className="grid-2", children=[
            card(services, title="Upgraded services", subtitle="Click a service for its details."),
            card(html.Div(requirements, className="table-scroll"), title="Technical requirements to install",
                 subtitle="Building-wide: equipment shared by several services is counted once."),
        ]),
        html.H2("SRI report of the upgraded building", className="section-title"),
        render(data, start=c["assessment"]),
    ])


@callback(Output("sc-download", "data"), Input("sc-dl-json", "n_clicks"), Input("sc-dl-xlsx", "n_clicks"),
          *STATES, prevent_initial_call=True)
def download(_j, _x, sid, store, fstore, stored_sri, stored_obj):
    if ctx.triggered_id not in ("sc-dl-json", "sc-dl-xlsx"):
        return no_update
    _, scen, label, data = _scenario_data(sid, store, fstore, stored_sri, stored_obj)
    if data is None:
        return no_update
    name = f"SRI_upgrade_assessment_{label.split(' (')[0].replace(' ', '_').replace('#', '')}"
    if ctx.triggered_id == "sc-dl-json":
        return dcc.send_bytes(assessment_json(data), f"{name}.json")
    return dcc.send_bytes(assessment_xlsx(data), f"{name}.xlsx")
