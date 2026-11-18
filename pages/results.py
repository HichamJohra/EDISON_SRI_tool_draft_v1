"""Step 3: recommended package, KPIs and cost–SRI curve."""
import dash
import plotly.graph_objects as go
from dash import Input, Output, callback, html

from components.ui import card, graph, info_table, kpi_static, page_head
from edison_sri.optimiser import best_package, package_table, pareto_front
from edison_sri.scoring import sri_class, sri_score

dash.register_page(__name__, path="/results", name="3. Upgrade plan", order=3,
                   title="Upgrade plan · EDISON SRI upgrade tool")

ACCENT, ACCENT_2, HIGHLIGHT = "#1f4e79", "#2e75b6", "#c8581b"

layout = html.Div([
    page_head("3. Upgrade plan", "Computed from the saved assessment and objectives."),
    html.Div(id="r-kpis", className="kpi-row"),
    html.Div(className="grid-2", children=[
        card(title="Recommended upgrades", subtitle="Sorted by cost per SRI point of each step on its own.",
             children=html.Div(id="r-table")),
        card(title="Cost–SRI curve", subtitle="Cheapest package for each reachable SRI; orange = recommended.",
             children=graph("r-curve", height=380)),
    ]),
])


def _nok(x: float) -> str:
    return f"{x:,.0f} NOK".replace(",", " ")


@callback(Output("r-kpis", "children"), Output("r-table", "children"), Output("r-curve", "figure"),
          Input("store-assessment", "data"), Input("store-objectives", "data"))
def compute(assessment, objectives):
    levels = assessment["levels"]
    area = assessment["building"]["floor_area_m2"]
    base = sri_score(levels)
    front = pareto_front(levels, area)
    pkg = best_package(levels, area, objectives["mode"], objectives["target_class"], objectives["budget_nok"])

    fig = go.Figure(go.Scatter(x=[p["cost"] / 1e6 for p in front], y=[p["sri"] for p in front],
                               mode="lines+markers", line={"shape": "hv", "color": ACCENT_2},
                               marker={"color": ACCENT}, name="Cheapest package",
                               hovertemplate="%{x:.2f} MNOK<br>SRI %{y:.1f} %<extra></extra>"))
    fig.update_layout(margin=dict(l=50, r=10, t=10, b=45), xaxis_title="Investment (MNOK)", yaxis_title="SRI (%)",
                      plot_bgcolor="white", paper_bgcolor="white", showlegend=False)
    fig.update_xaxes(gridcolor="#dfe3ea")
    fig.update_yaxes(gridcolor="#dfe3ea", range=[0, 100])

    max_kpi = kpi_static("Maximum feasible SRI", f"{front[-1]['sri']:.1f} %", _nok(front[-1]["cost"]),
                         "Highest SRI reachable with the services in the catalogue, and its cost.")
    base_kpi = kpi_static("Current SRI", f"{base:.1f} %", f"Class {sri_class(base)}")
    if pkg is None:
        return ([base_kpi, kpi_static("After upgrade", "–", "No package meets the objective"), max_kpi],
                html.Div("Raise the budget or lower the target class.", className="msg msg-error"), fig)

    fig.add_trace(go.Scatter(x=[pkg["cost"] / 1e6], y=[pkg["sri"]], mode="markers",
                             marker={"size": 14, "color": HIGHLIGHT}, name="Recommended",
                             hovertemplate="Recommended<br>%{x:.2f} MNOK<br>SRI %{y:.1f} %<extra></extra>"))
    rows = package_table(levels, pkg["levels"], area)
    for r in rows:
        r["Cost (NOK)"] = _nok(r["Cost (NOK)"]).replace(" NOK", "")
    table = info_table(rows) if rows else html.Div("No upgrade needed.", className="msg msg-ok")
    after = kpi_static("After upgrade", f"{pkg['sri']:.1f} %", f"Class {sri_class(pkg['sri'])} · {_nok(pkg['cost'])}")
    return [base_kpi, after, max_kpi], table, fig
