"""Step 3: decision mode, cost data and the table of objectives and constraints; save, import and export."""
from typing import Any

import dash
import dash_ag_grid as dag
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from components.ui import card, control, page_head
from edison_sri.parameters import (EXPORT_FORMATS, ParameterError, defaults, export_bytes, from_grid, grid_rows,
                                   import_upload, validate)
from edison_sri.requirements import COST_DATABASES

dash.register_page(__name__, path="/objectives", name="3. Objectives & constraints", order=3,
                   title="Objectives & constraints · EDISON SRI upgrade tool")

# Typed as Any because dash-ag-grid declares these props as TypedDicts (IDE warnings on plain dicts)
COLUMNS: Any = [
    {"field": "active", "headerName": "Active", "width": 90, "editable": True, "cellDataType": "boolean"},
    {"field": "category", "headerName": "Category", "width": 210, "filter": True},
    {"field": "label", "headerName": "Objective / constraint", "flex": 3, "minWidth": 280, "tooltipField": "help",
     "wrapText": True, "autoHeight": True},
    {"field": "kind", "headerName": "Type", "width": 110},
    {"field": "op", "headerName": "", "width": 80, "cellStyle": {"textAlign": "center", "fontWeight": 600}},
    {"field": "value", "headerName": "Value ✎", "width": 140, "editable": True, "cellDataType": False,
     "cellEditorSelector": {"function": "valueEditor(params)"},  # dropdown for classes and yes/no (assets JS)
     "cellStyle": {"backgroundColor": "#eef3fa", "fontWeight": 600}},
    {"field": "unit", "headerName": "Unit", "width": 100},
    {"field": "status", "headerName": "Status", "width": 115, "filter": True,
     "headerTooltip": "Used now = taken into account by the draft upgrade plan; Planned = later versions"},
]
DEFAULT_COLDEF: Any = {"resizable": True, "sortable": False}
GRID_OPTIONS: Any = {"singleClickEdit": True, "stopEditingWhenCellsLoseFocus": True, "tooltipShowDelay": 300,
                     "animateRows": False}
ROW_STYLE: Any = {"styleConditions": [
    {"condition": "params.data.status === 'Planned' && !params.data.active", "style": {"color": "#8a93a0"}},
    {"condition": "params.data.active", "style": {"backgroundColor": "#f2f8f3"}},
]}

layout = html.Div([
    page_head("3. Objectives & constraints",
              "What the upgrade plan should achieve and which limits it must respect, plus the cost data used for "
              "prices and technical requirements."),
    card(title="Save, import and export", subtitle="Save keeps the parameters for this browser tab. Export writes "
         "them to a file you can keep, share or edit; import reads such a file back (JSON, YAML or Excel).",
         children=[
             html.Div(className="action-bar", children=[
                 html.Button("Save objectives", id="o-save", className="btn"),
                 html.Span(className="action-sep"),
                 dcc.Upload(html.Button("Import file…", className="btn btn-outline"), id="o-import", multiple=False,
                            accept=".json,.yaml,.yml,.xlsx"),
                 html.Span(className="action-sep"),
                 dcc.Dropdown([{"label": v, "value": k} for k, v in EXPORT_FORMATS.items()], value="xlsx",
                              id="o-export-format", clearable=False, searchable=False, className="export-format"),
                 html.Button("Export", id="o-export", className="btn btn-outline"),
                 dcc.Download(id="o-download"),
             ]),
             html.Div(id="o-saved"),
             html.Div(id="o-export-msg"),
         ]),
    html.Div(className="grid-2", children=[
        card(title="Decision mode", children=dcc.RadioItems(
            [{"label": " Target mode – reach the active targets at the lowest investment", "value": "target"},
             {"label": " Budget mode – highest total SRI within the investment budget and other constraints",
              "value": "budget"}],
            id="o-mode", className="radio")),
        card(title="Cost data", subtitle="Used for prices and technical requirements on “2. Smart services” and for "
                                        "the upgrade plan.", children=[
            control("Cost database", dcc.Dropdown(
                [{"label": v["name"], "value": k, "disabled": not v["available"]} for k, v in COST_DATABASES.items()],
                id="o-costdb", clearable=False)),
            control("Heated floor area for cost estimates (m²)",
                    # min=0 so every multiple of the step is valid (with min=1 the browser would refuse 5000)
                    dcc.Input(id="o-area", type="number", min=0, step=100, className="field-input")),
        ]),
    ]),
    card(title="Objectives and constraints",
         subtitle="Tick “Active” to apply a row and edit its value (click the blue cell). Objectives are targets to "
                  "reach; constraints are limits the plan must respect. Hover a name for details.",
         children=[
             dag.AgGrid(id="o-grid", columnDefs=COLUMNS, defaultColDef=DEFAULT_COLDEF, dashGridOptions=GRID_OPTIONS,
                        getRowStyle=ROW_STYLE, style={"height": "720px", "width": "100%"}),
             html.Div([html.Strong("Used now: "), "the draft upgrade plan uses the SRI class (target mode), the "
                       "total investment budget (budget mode) and “never lower a service level”. ",
                       html.Strong("Planned: "), "stored, exported and imported already; the optimiser will use "
                       "them in later versions."], className="field-hint", style={"marginTop": "8px"}),
         ]),
])


def _current(stored) -> dict:
    """Stored parameters, upgraded to the current format (older sessions)."""
    try:
        return validate(stored or {})[0]
    except ParameterError:
        return defaults()


def _outputs(p: dict) -> tuple:
    return p["mode"], p["cost_db"], p["floor_area_m2"], grid_rows(p)


# One callback for load, save AND import (see the note in pages/assessment.py): on page entry → fill the page from
# the store; Save → check and store; Import → read the file, check it, fill the page and store it.
@callback(Output("store-objectives", "data"), Output("o-saved", "children"),
          Output("o-mode", "value"), Output("o-costdb", "value"), Output("o-area", "value"),
          Output("o-grid", "rowData"), Output("o-import", "contents"),
          Input("o-save", "n_clicks"), Input("o-import", "contents"),
          State("o-import", "filename"), State("store-objectives", "data"),
          State("o-mode", "value"), State("o-costdb", "value"), State("o-area", "value"), State("o-grid", "rowData"))
def load_save_import(n_clicks, contents, filename, stored, mode, cost_db, area, rows):
    keep = [no_update] * 4
    if ctx.triggered_id == "o-import" and contents:
        try:
            params, warnings = import_upload(contents, filename)
        except ParameterError as exc:
            return no_update, html.Div(f"Import failed ({filename}): {exc}", className="msg msg-error"), *keep, None
        msg = [html.Strong(f"Imported and saved: {filename}.")]
        if warnings:
            msg.append(html.Ul([html.Li(w) for w in warnings[:12]]))
        return params, html.Div(msg, className="msg msg-ok"), *_outputs(params), None
    if ctx.triggered_id == "o-save" and n_clicks:
        try:
            params, _ = validate({"mode": mode, "cost_db": cost_db, "floor_area_m2": area,
                                  "criteria": from_grid(rows)})
        except ParameterError as exc:
            return no_update, html.Div(f"Not saved: {exc}", className="msg msg-error"), *keep, no_update
        n_active = sum(v["active"] for v in params["criteria"].values())
        return (params, html.Div(f"Saved ({n_active} active objectives and constraints).", className="msg msg-ok"),
                *keep[:3], grid_rows(params), no_update)
    return no_update, no_update, *_outputs(_current(stored)), no_update  # page entry


@callback(Output("o-download", "data"), Output("o-export-msg", "children"),
          Input("o-export", "n_clicks"),
          State("o-export-format", "value"), State("o-mode", "value"), State("o-costdb", "value"),
          State("o-area", "value"), State("o-grid", "rowData"),
          prevent_initial_call=True)
def export(n_clicks, fmt, mode, cost_db, area, rows):
    if not n_clicks:
        return no_update, no_update
    try:
        params, _ = validate({"mode": mode, "cost_db": cost_db, "floor_area_m2": area, "criteria": from_grid(rows)})
        content, name = export_bytes(params, fmt)
    except ParameterError as exc:
        return no_update, html.Div(f"Not exported: {exc}", className="msg msg-error")
    except ImportError as exc:
        return no_update, html.Div(f"Export to {fmt} needs the package {exc.name} (uv add {exc.name}).",
                                   className="msg msg-error")
    return dcc.send_bytes(content, name), None
