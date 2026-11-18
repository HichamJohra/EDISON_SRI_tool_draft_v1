"""Step 1: building data and current service levels (editable grid)."""
from typing import Any

import dash
import dash_ag_grid as dag
from dash import Input, Output, State, callback, dcc, html, no_update

from components.ui import card, control, kpi_static, page_head
from edison_sri.catalogue import BUILDING_CATEGORIES, SERVICES, SERVICE_BY_CODE
from edison_sri.scoring import sri_class, sri_score

dash.register_page(__name__, path="/assessment", name="1. Assessment", order=1,
                   title="Assessment · EDISON SRI upgrade tool")

MAX_LEVEL = max(s.max_level for s in SERVICES)
# Typed as Any because dash-ag-grid declares these props as TypedDicts (IDE warnings on plain dicts)
COLUMN_DEFS: Any = [
    {"field": "code", "headerName": "Code", "width": 100},
    {"field": "name", "headerName": "Service", "flex": 2},
    {"field": "domain", "headerName": "Domain", "flex": 1},
    {"field": "max_level", "headerName": "Max level", "width": 110},
    {"field": "level", "headerName": "Current level ✎", "width": 150, "editable": True,
     "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": list(range(MAX_LEVEL + 1))},
     "cellStyle": {"backgroundColor": "#eef3fa", "fontWeight": 600}},
]
GRID_DEFAULT_COLDEF: Any = {"sortable": True, "resizable": True}
GRID_STYLE: Any = {"height": "360px", "width": "100%"}


def _levels(rows: list[dict]) -> dict:
    """Levels from the grid, clipped to each service's maximum level."""
    return {r["code"]: min(int(r["level"] or 0), SERVICE_BY_CODE[r["code"]].max_level) for r in rows}


layout = html.Div([
    page_head("1. Building and SRI assessment",
              "Enter the building and the current functionality level of each service (dummy catalogue)."),
    html.Div(className="grid-2", children=[
        card(title="Building", children=[
            control("Name", dcc.Input(id="b-name", type="text", className="field-input")),
            control("Category", dcc.Dropdown(BUILDING_CATEGORIES, id="b-category", clearable=False)),
            control("Heated floor area (m²)", dcc.Input(id="b-area", type="number", min=1, className="field-input")),
            control("SRI method", dcc.RadioItems(
                [{"label": " Method A (27 services)", "value": "A"},
                 {"label": " Method B (54 services)", "value": "B"}], id="b-method", className="radio")),
        ]),
        card(title="Current score", subtitle="Updated live from the levels below (placeholder SRI method).",
             children=html.Div(id="a-score")),
    ]),
    card(title="Services", subtitle="Double-click a level to edit it. Levels above a service's maximum are capped.",
         children=[
             dag.AgGrid(id="a-grid", columnDefs=COLUMN_DEFS, defaultColDef=GRID_DEFAULT_COLDEF, style=GRID_STYLE,
                        dashGridOptions={"singleClickEdit": True}),
             html.Div([html.Button("Save assessment", id="a-save", className="btn"),
                       html.Span(id="a-saved", className="muted", style={"marginLeft": "12px"})],
                      style={"marginTop": "12px"}),
         ]),
])


@callback(
    Output("b-name", "value"), Output("b-category", "value"), Output("b-area", "value"),
    Output("b-method", "value"), Output("a-grid", "rowData"),
    Input("store-assessment", "data"),
)
def load(data):
    b, lv = data["building"], data["levels"]
    rows = [{"code": s.code, "name": s.name, "domain": s.domain, "max_level": s.max_level,
             "level": lv.get(s.code, 0)} for s in SERVICES]
    return b["name"], b["category"], b["floor_area_m2"], b["method"], rows


@callback(Output("a-score", "children"), Input("a-grid", "rowData"), Input("a-grid", "cellValueChanged"))
def live_score(rows, _):
    if not rows:
        return "–"
    score = sri_score(_levels(rows))
    return kpi_static("SRI (placeholder)", f"{score:.1f} %", f"Class {sri_class(score)}",
                      "Weighted mean of normalised service levels per domain – not the EU method.")


@callback(
    Output("store-assessment", "data"), Output("a-saved", "children"),
    Input("a-save", "n_clicks"),
    State("b-name", "value"), State("b-category", "value"), State("b-area", "value"),
    State("b-method", "value"), State("a-grid", "rowData"),
    prevent_initial_call=True,
)
def save(n_clicks, name, category, area, method, rows):
    # Guard: Dash can fire this when the page is inserted, before the grid has data
    if not n_clicks or not rows:
        return no_update, no_update
    data = {
        "building": {"name": name, "category": category, "floor_area_m2": area or 1, "method": method},
        "levels": _levels(rows),
    }
    return data, "Saved."
