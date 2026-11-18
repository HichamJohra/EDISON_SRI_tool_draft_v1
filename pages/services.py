"""Step 2: smart-ready services – description, technical requirements and level-by-level sensitivity."""
import dash
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from components.ui import GRAPH_CONFIG, card, page_head
from edison_sri.catalogue import DEFAULT_OBJECTIVES
from edison_sri.requirements import COST_DATABASES, price, requirements_at, upgrade
from edison_sri.sri_assessment import load_example
from edison_sri.sri_engine import KF_GROUPS, KF_NAMES, affected, catalogue_by_code, level_sensitivity, load_catalogue

dash.register_page(__name__, path="/services", name="2. Smart services", order=2,
                   title="Smart services · EDISON SRI upgrade tool")

ACCENT, ACCENT_2, HIGHLIGHT, GREY = "#1f4e79", "#2e75b6", "#c8581b", "#9aa7ad"
# One colour per impact criterion and per key functionality (same order as the catalogue)
IMPACT_COLOURS = ["#1f4e79", "#c8581b", "#028090", "#7a5195", "#4c9a2a", "#b8860b", "#d1495b"]
KF_COLOURS = ["#1f4e79", "#028090", "#c8581b"]
KF_SHORT = {"Key functionality 1 - building": "KF1 – building", "Key functionality 2 - user": "KF2 – user",
            "Key functionality 3 - grid": "KF3 – grid"}
IMPACT_SHORT = ["Energy", "Flex.", "Comfort", "Conv.", "Health", "Maint.", "Info."]  # full name on hover
DEFAULT_CODE = "H-1a"


def _options():
    return [{"label": f"{s['code']} – {s['service']}  ({s['domain']})", "value": s["code"]}
            for s in load_catalogue()["services"]]


def layout(code: str | None = None, **_):
    """Page layout; ?code=H-1a in the URL pre-selects a service (links from the SRI assessment page)."""
    if code not in catalogue_by_code():
        code = DEFAULT_CODE
    return html.Div([
        page_head("2. Smart services",
                  "Description, technical requirements and level-by-level effect of each smart-ready service "
                  "(EU service catalogue, calculation sheet v4.5)."),
        card(title="Select a smart-ready service", children=[
            dcc.Dropdown(_options(), value=code, id="svc-select", clearable=False, optionHeight=40),
            html.Div(id="svc-context"),
        ]),
        html.Div(id="svc-detail"),
    ])


def _thousands(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _nok(x: float) -> str:
    return f"{_thousands(x)} NOK"


def _levels_table(svc: dict, assessed: int | None) -> html.Table:
    head = html.Tr([html.Th("Level"), html.Th("Functionality level")] +
                   [html.Th(s, className="num", title=full) for s, full in
                    zip(IMPACT_SHORT, load_catalogue()["impact_criteria"])])
    rows = []
    for lv in svc["levels"]:
        cells = [html.Td(str(lv["level"])), html.Td(lv["description"])]
        for v in lv["impacts"]:
            cls = "num imp-pos" if v > 0 else ("num imp-neg" if v < 0 else "num imp-zero")
            cells.append(html.Td(f"{v:g}", className=cls))
        rows.append(html.Tr(cells, className="row-current" if lv["level"] == assessed else None))
    return html.Table(className="info-table compare-table levels-table", children=[html.Thead(head), html.Tbody(rows)])


def _requirements_table(svc: dict, assessed: int | None, area: float, db: str) -> html.Table:
    levels = [lv["level"] for lv in svc["levels"]]
    reqs = requirements_at(svc["domain"], max(levels))
    have = set(requirements_at(svc["domain"], assessed)) if assessed is not None else set()
    head = html.Tr([html.Th("Technical requirement"), html.Th("Price", className="num")] +
                   [html.Th(f"L{lv}", className="num") for lv in levels])
    body = []
    for r in reqs:
        cells = [html.Td(r), html.Td(_nok(price(r, area, db)), className="num")]
        for lv in levels:
            needed = r in requirements_at(svc["domain"], lv)
            mark = ("0" if r in have else "x") if needed else ""
            cls = "num req-have" if needed and r in have else ("num req-buy" if needed else "num")
            cells.append(html.Td(html.Span(mark, className="req-mark") if mark else "", className=cls))
        body.append(html.Tr(cells))
    return html.Table(className="info-table compare-table req-table", children=[html.Thead(head), html.Tbody(body)])


def _line_fig(levels, series, assessed, ytitle, legend=True):
    """Lines of score (%) against functionality level; series = [(name, values 0–1, colour, dash)]."""
    fig = go.Figure()
    for name, vals, colour, dash in series:
        y = [None if v is None else 100 * v for v in vals]
        fig.add_trace(go.Scatter(x=levels, y=y, name=name, mode="lines+markers", line=dict(color=colour, dash=dash),
                                 marker=dict(size=7), hovertemplate=f"{name}<br>Level %{{x}}: %{{y:.1f}} %<extra></extra>"))
        if assessed is not None and assessed in levels and y[levels.index(assessed)] is not None:
            fig.add_trace(go.Scatter(x=[assessed], y=[y[levels.index(assessed)]], mode="markers", showlegend=False,
                                     marker=dict(size=12, color=HIGHLIGHT, line=dict(color="white", width=1)),
                                     hoverinfo="skip"))
    fig.update_layout(**{**_layout(levels), "showlegend": legend},
                      legend=dict(orientation="h", y=-0.28, x=0, font_size=11),
                      yaxis=dict(title=ytitle, gridcolor="#dfe3ea", ticksuffix=" %"))
    if legend:
        fig.update_layout(height=360, margin=dict(l=55, r=10, t=10, b=95))
    return fig


def _layout(levels):
    return dict(margin=dict(l=55, r=10, t=10, b=45), height=300, plot_bgcolor="white", paper_bgcolor="white",
                showlegend=False, xaxis=dict(title="Functionality level", tickmode="array", tickvals=levels,
                                             gridcolor="#dfe3ea"))


def _figures(svc: dict, assessment: dict, assessed: int | None, area: float, db: str):
    levels = [lv["level"] for lv in svc["levels"]]
    cur = assessed if assessed is not None else 0
    sens = level_sensitivity(assessment, svc["code"])
    aff = affected(svc["code"])
    names = load_catalogue()["impact_criteria"]
    figs = {}
    if sens:
        lv_s = [p["level"] for p in sens]
        figs["sri"] = _line_fig(lv_s, [("Total SRI", [p["total"] for p in sens], ACCENT_2, "solid")], assessed,
                                "Total SRI (%)", legend=False)
        figs["kf"] = _line_fig(lv_s, [
            (KF_SHORT[kf], [p["key_functionalities"][kf] for p in sens], KF_COLOURS[i],
             "solid" if kf in aff["key_functionalities"] else "dot")
            for i, kf in enumerate(KF_GROUPS)], assessed, "Key functionality score (%)")
        figs["imp"] = _line_fig(lv_s, [
            (names[k], [p["impact_criteria"][k] for p in sens], IMPACT_COLOURS[k], "solid")
            for k in aff["impact_criteria"]], assessed, "Impact criterion score (%)")
        figs["dom"] = _line_fig(lv_s, [(svc["domain"], [p["domains"].get(svc["domain"]) for p in sens], ACCENT,
                                         "solid")], assessed, f"{svc['domain']} – domain score (%)", legend=False)
    # Additional investment
    costs = [upgrade(svc["domain"], cur, lv, area, db)["cost"] for lv in levels]
    f_cost = go.Figure(go.Bar(x=levels, y=[c / 1e3 for c in costs],
                              marker_color=[GREY if lv <= cur else ACCENT_2 for lv in levels],
                              hovertemplate="Level %{x}: +%{y:,.0f} kNOK<extra></extra>"))
    f_cost.update_layout(**_layout(levels), yaxis=dict(title="Additional investment (kNOK)", gridcolor="#dfe3ea",
                                                       rangemode="tozero", range=None if any(costs) else [0, 1]))
    if not any(costs):
        f_cost.add_annotation(text="No investment: the assessed level is already the highest one" if cur >= max(levels)
                              else "No additional investment", x=0.5, y=0.5, xref="paper", yref="paper",
                              showarrow=False, font=dict(color="#5d6675", size=13))
    figs["cost"] = f_cost
    # Technical requirements
    have_n = [len([r for r in requirements_at(svc["domain"], lv) if r in requirements_at(svc["domain"], cur)])
              for lv in levels]
    new_n = [len(upgrade(svc["domain"], cur, lv, area, db)["requirements"]) for lv in levels]
    f_req = go.Figure([
        go.Bar(x=levels, y=have_n, name="Already in the building", marker_color=GREY,
               hovertemplate="Level %{x}: %{y} already in place<extra></extra>"),
        go.Bar(x=levels, y=new_n, name="To add", marker_color=ACCENT_2,
               hovertemplate="Level %{x}: %{y} to add<extra></extra>"),
    ])
    f_req.update_layout(**{**_layout(levels), "showlegend": True}, barmode="stack",
                        yaxis=dict(title="Technical requirements (number)", gridcolor="#dfe3ea", dtick=1),
                        legend=dict(orientation="h", y=1.12, x=0))
    figs["req"] = f_req
    return figs


def _graph(title, fig, note=None):
    return html.Div([html.H4(title, className="mini-title"), dcc.Graph(figure=fig, config=GRAPH_CONFIG),
                     html.Div(note, className="field-hint") if note else None])


@callback(Output("svc-context", "children"), Output("svc-detail", "children"),
          Input("svc-select", "value"), State("store-sri", "data"), State("store-objectives", "data"))
def show(code, stored, objectives):
    svc = catalogue_by_code()[code]
    assessment = stored or load_example()
    obj = {**DEFAULT_OBJECTIVES, **(objectives or {})}
    db, area = obj.get("cost_db", "default"), float(obj.get("floor_area_m2") or DEFAULT_OBJECTIVES["floor_area_m2"])
    a_svc = next((s for s in assessment["services"] if s["code"] == code), None)
    counted = bool(a_svc and a_svc["applicable"] and a_svc["in_max_score"])
    assessed = a_svc["level"] if counted else None

    building = assessment["building"]["name"]
    context = [
        html.Div(className="msg msg-info", children=[
            html.Strong("Costs and technical requirements depend on your inputs. "),
            "They are computed with the cost database and building data chosen in ",
            dcc.Link("3. Objectives & constraints", href="/objectives", className="link-strong"),
            f" – now: {COST_DATABASES[db]['name']}, {_thousands(area)} m² heated floor area.",
            html.Br(),
            ("SRI effects use the imported assessment: " if stored else
             "No assessment imported yet – SRI effects shown for the example: "), html.Em(building), ".",
        ]),
    ]
    aff = affected(code)
    names = load_catalogue()["impact_criteria"]
    info = html.Table(className="info-table", children=html.Tbody([
        html.Tr([html.Th("Code"), html.Td(svc["code"])]),
        html.Tr([html.Th("Domain"), html.Td(svc["domain"])]),
        html.Tr([html.Th("Service group"), html.Td(svc["group"] or "–")]),
        html.Tr([html.Th("Service"), html.Td(svc["service"])]),
        html.Tr([html.Th("Reference standard"), html.Td(svc["standard"] or "–")]),
        html.Tr([html.Th("Levels"), html.Td(f"0 to {max(lv['level'] for lv in svc['levels'])}")]),
        html.Tr([html.Th("Key functionalities affected"), html.Td(html.Div(className="badges", children=[
            html.Span(f"{KF_SHORT[kf]}: {KF_NAMES[kf]}", className="badge")
            for kf in aff["key_functionalities"]] or "–"))]),
        html.Tr([html.Th("Impact criteria affected"), html.Td(html.Div(className="badges", children=[
            html.Span(names[k], className="badge badge-light") for k in aff["impact_criteria"]] or "–"))]),
        html.Tr([html.Th("In this building"),
                 html.Td(f"Level {assessed} (assessed)" if counted else
                         "Not applicable or not counted in the score" if a_svc else "Not in the assessment")]),
    ]))
    figs = _figures(svc, assessment, assessed, area, db)
    not_aff = [names[k] for k in range(7) if k not in aff["impact_criteria"]]
    detail = html.Div([
        html.Div(className="grid-1-2", children=[
            card(info, title=f"{svc['code']} – {svc['service']}"),
            card(html.Div(_levels_table(svc, assessed), className="table-scroll"),
                 title="Functionality levels and impact scores",
                 subtitle="Ordinal impact score of each level on the 7 impact criteria (EU catalogue). "
                          "Highlighted row = level assessed in the building."),
        ]),
        card(html.Div(_requirements_table(svc, assessed, area, db), className="table-scroll"),
             title="Technical requirements per level",
             subtitle="x = to buy (priced once), 0 = already in the building at the assessed level. "
                      "Draft: dummy requirement list and dummy prices from the selected cost database."),
        card(title="Local sensitivity: changing only this service",
             subtitle="All other services stay at their assessed level. Orange points / grey bars = assessed level.",
             children=[
                 html.Div(className="grid-2", children=[
                     _graph("Total SRI", figs["sri"]),
                     _graph(f"Technical domain: {svc['domain']}", figs["dom"],
                            "Domain score as in the EU sheet results (impact-weighted mean over its criteria)."),
                 ]) if "sri" in figs else html.Div("This service does not count in this building's score "
                                                   "(not applicable), so it does not change the SRI.",
                                                   className="msg msg-info"),
                 html.Div(className="grid-2 sens-row", children=[
                     _graph("Key functionalities", figs["kf"],
                            "Solid = affected by this service; dotted = not affected (flat)."),
                     _graph("Impact criteria affected", figs["imp"],
                            ("Not affected: " + ", ".join(not_aff) + ".") if not_aff else None),
                 ]) if "sri" in figs else None,
                 html.Div(className="grid-2 sens-row", children=[
                     _graph("Additional investment", figs["cost"]),
                     _graph("Technical requirements", figs["req"]),
                 ]),
                 html.P("SRI, key functionality, impact criterion and domain scores: EU calculation method, "
                        "reproducing the EU calculation sheet. Investment and technical requirements change with the "
                        "cost database and floor area set in “3. Objectives & constraints”; shared equipment with "
                        "other services is not counted here.", className="field-hint"),
             ]),
    ])
    return context, detail
