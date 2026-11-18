"""SRI report: KPIs, building and assessment tables, impact / domain bars, heat map and service list.

Used by "1. Initial SRI assessment" (imported assessment) and "5. SRI upgrade assessment" (a scenario).
"""
from typing import Any

import dash_ag_grid as dag
import plotly.graph_objects as go
from dash import dcc, html

from components.ui import GRAPH_CONFIG, card, kpi_static

ACCENT, ACCENT_2, MUTED = "#1f4e79", "#2e75b6", "#5d6675"
KF_LABELS = {"Key functionality 1 - building": ("Energy performance and operation", "Key functionality 1 – building"),
             "Key functionality 2 - user": ("Response to user needs", "Key functionality 2 – user"),
             "Key functionality 3 - grid": ("Energy flexibility", "Key functionality 3 – grid")}

# Typed as Any because dash-ag-grid declares these props as TypedDicts (IDE warnings on plain dicts)
SERVICE_COLUMNS: Any = [
    {"field": "domain", "headerName": "Domain", "width": 170, "filter": True},
    # Code and service link to the Smart services page (markdown links: [text](/services?code=…))
    {"field": "code_link", "headerName": "Code", "width": 95, "cellRenderer": "markdown"},
    {"field": "service_link", "headerName": "Service", "flex": 2, "minWidth": 220, "cellRenderer": "markdown",
     "tooltipField": "service"},
    {"field": "level_txt", "headerName": "Level", "width": 115, "type": "rightAligned"},
    {"field": "level_description", "headerName": "Functionality level (as assessed)", "flex": 3, "minWidth": 260,
     "tooltipField": "level_description"},
    {"field": "applicable_txt", "headerName": "Applicable", "width": 115, "filter": True},
]
GRID_DEFAULT_COLDEF: Any = {"sortable": True, "resizable": True, "floatingFilter": False}
GRID_OPTIONS: Any = {"pagination": True, "paginationPageSize": 20, "enableCellTextSelection": True,
                     "tooltipShowDelay": 300}
GRID_STYLE: Any = {"height": "620px", "width": "100%"}

# ---------- visualisation ----------
def _pct(v) -> str:
    return "n/a" if v is None else f"{100 * v:.1f} %"


def _bar(values: dict, title: str) -> go.Figure:
    names = list(values)[::-1]  # first item on top
    vals = [100 * (values[n] or 0) for n in names]
    fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=ACCENT_2,
                           text=[f"{v:.0f} %" for v in vals], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f} %<extra></extra>"))
    fig.update_layout(margin=dict(l=10, r=40, t=10, b=30), height=34 * len(names) + 60, plot_bgcolor="white",
                      paper_bgcolor="white", xaxis=dict(range=[0, 105], ticksuffix=" %", gridcolor="#dfe3ea"),
                      yaxis=dict(automargin=True), showlegend=False, title=None)
    return fig


def _wrap(label: str, width: int = 16) -> str:
    """Break a long axis label into lines of about `width` characters (Plotly uses <br>)."""
    lines, cur = [], ""
    for w in label.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return "<br>".join(lines + [cur])


def _heatmap(detail: dict) -> go.Figure:
    domains = list(detail)
    impacts = list(next(iter(detail.values())))
    z = [[None if detail[d][i] is None else 100 * detail[d][i] for i in impacts] for d in domains]
    text = [["–" if v is None else f"{v:.0f}" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(z=z, x=[_wrap(i) for i in impacts], y=domains, text=text, texttemplate="%{text}", zmin=0, zmax=100,
                               colorscale="Blues", colorbar=dict(title="%", ticksuffix=" %"),
                               hovertemplate="%{y} · %{x}: %{z:.1f} %<extra></extra>", xgap=2, ygap=2))
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420, plot_bgcolor="#f3f5f9",
                      paper_bgcolor="white", yaxis=dict(autorange="reversed", automargin=True, showgrid=False, zeroline=False),
                      xaxis=dict(side="top", automargin=True, tickangle=0, showgrid=False, zeroline=False))
    return fig


def _delta(v, v0) -> str:
    return "" if v is None or v0 is None else f" · {100 * (v - v0):+.2f} pt"


def render(data, start: dict | None = None):
    """The SRI report of an assessment; with `start` (the original assessment), changes are shown against it."""
    if not data:
        return html.Div("No assessment imported yet: choose a source above and click “Import and visualize”.",
                        className="msg msg-info")
    b, m, r = data["building"], data["method"], data["results"]
    r0 = start["results"] if start else None
    kfs = r["key_functionalities"]
    kpis = html.Div(className="kpi-row kpi-row-4", children=[
        kpi_static("Total SRI", _pct(r["total"]),
                   f"Class: {r['class']}" + (_delta(r["total"], r0["total"]) + f" (start: {r0['class']})" if r0 else ""),
                   "Total smart readiness score (EU method).", main=True),
        *[kpi_static(KF_LABELS[k][1], _pct(v),
                     KF_LABELS[k][0] + (_delta(v, r0["key_functionalities"][k]) if r0 else ""))
          for k, v in kfs.items()],
    ])
    building = info_table_vertical([
        ("Building", b["name"]), ("Description", b.get("description")), ("Type / usage", b.get("usage")),
        ("Location / climate zone", f"{b.get('location')} · {b.get('climate_zone')}"),
        ("Useful floor area", b.get("floor_area_class")), ("Year of construction", b.get("construction_year")),
        ("Building state", b.get("state")),
    ])
    assessment = info_table_vertical([
        ("Source", f"{data['source']['tool']} v{data['source']['version']}"),
        ("File", data["source"].get("file")),
        ("Service catalogue", f"Method {m['catalogue']}"), ("Weightings", m["weightings"]),
        ("Assessment date", data.get("assessment_date")),
        ("Services", f"{sum(s['applicable'] for s in data['services'])} applicable of {len(data['services'])}"),
    ])
    start_lv = {s["code"]: s["level"] for s in start["services"]} if start else {}
    rows = [{**s, "level_txt": (f"{start_lv[s['code']]} → " if start_lv.get(s["code"], s["level"]) != s["level"]
                                else "") + f"{s['level']} / {s['max_level']}",
             "changed": start_lv.get(s["code"], s["level"]) != s["level"],
             "code_link": f"[{s['code']}](/services?code={s['code']})",
             "service_link": f"[{s['service']}](/services?code={s['code']})",
             "applicable_txt": "Yes" if s["applicable"] else "No"} for s in data["services"]]
    return html.Div([
        kpis,
        html.Div(className="grid-2", children=[card(building, title="Building"),
                                                card(assessment, title="Assessment")]),
        html.Div(className="grid-2", children=[
            card(dcc.Graph(figure=_bar(r["impact_criteria"], "Impact criteria"), config=GRAPH_CONFIG),
                 title="Impact criteria", subtitle="Score per impact criterion, all domains together."),
            card(dcc.Graph(figure=_bar(r["domains"], "Domains"), config=GRAPH_CONFIG),
                 title="Technical domains", subtitle="Score per domain, all impact criteria together."),
        ]),
        card(dcc.Graph(figure=_heatmap(r["domain_impact"]), config=GRAPH_CONFIG),
             title="Domain × impact criterion",
             subtitle="Score in % for each domain and impact criterion; – = no service of that domain affects "
                      "this criterion."),
        card(dag.AgGrid(rowData=sorted(rows, key=lambda x: not x["changed"]) if start else rows,
                        columnDefs=SERVICE_COLUMNS, defaultColDef=GRID_DEFAULT_COLDEF,
                        dashGridOptions=GRID_OPTIONS, style=GRID_STYLE,
                        rowClassRules={"row-changed": "params.data.changed"}),
             title="Smart-ready services",
             subtitle="Functionality level found by the assessor and the highest level of each service. "
                      "Click a code or service name to see its details in “2. Smart services”."),
    ])


def info_table_vertical(pairs: list[tuple[str, Any]]) -> html.Table:
    return html.Table(className="info-table", children=html.Tbody([
        html.Tr([html.Th(k), html.Td(v if v not in (None, "") else "–")]) for k, v in pairs
    ]))
