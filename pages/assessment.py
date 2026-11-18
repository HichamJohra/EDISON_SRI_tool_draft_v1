"""Step 1: import the initial (existing) SRI assessment and visualise its results."""
import dash
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from components.sri_report import render
from components.ui import card, page_head
from edison_sri.sri_assessment import IMPORT_METHODS, SRI_NORSK_URL, import_assessment

dash.register_page(__name__, path="/assessment", name="1. Initial SRI assessment", order=1,
                   title="Initial SRI assessment · EDISON SRI upgrade tool")

UPLOAD_HINT = {
    "json": "Drop an EDISON SRI assessment (.json) here, or click to select it.",
    "eu_excel": "Drop the EU SRI calculation sheet (.xlsx, version 4.5) here, or click to select it.",
    "sri_norsk": "Drop the file exported from SRI Norsk here, or click to select it.",
}

layout = html.Div([
    page_head("1. Initial SRI assessment",
              "Import an SRI assessment made with another tool, then check its scores before planning upgrades."),
    card(title="Import an existing SRI assessment", children=[
        html.Div(className="grid-2 import-grid", children=[
            html.Div([
                html.Label("Source of the assessment", className="control-label"),
                dcc.RadioItems([{"label": f" {v}", "value": k} for k, v in IMPORT_METHODS.items()],
                               value="eu_excel", id="imp-method", className="radio",
                               persistence=True, persistence_type="session"),
                html.P(["No assessment yet? Make one with ",
                        html.A("SRI Norsk ↗", href=SRI_NORSK_URL, target="_blank", rel="noopener noreferrer",
                               className="link-strong"),
                        " (Norwegian SRI web tool), then export it and import it here."], className="muted"),
            ]),
            html.Div([
                dcc.Upload(id="imp-upload", className="upload-box", multiple=False,
                           children=html.Div(id="imp-upload-text")),
                html.Button("Import and visualize", id="imp-button", className="btn"),
                html.Div("Draft: whatever the source and file, the import loads the preset assessment of the "
                         "ARV pilot building (Voldsløkka, EU calculation sheet v4.5, Method B).",
                         className="field-hint", style={"marginTop": "8px"}),
            ]),
        ]),
        html.Div(id="imp-msg"),
    ]),
    dcc.Loading(html.Div(id="sri-view"), type="default"),
])


@callback(Output("imp-upload-text", "children"), Input("imp-method", "value"), Input("imp-upload", "filename"))
def upload_text(method, filename):
    if filename:
        return [html.Strong(filename), html.Span(" selected – click “Import and visualize”.")]
    return UPLOAD_HINT.get(method or "json")


# One callback for import AND display. Dash runs a callback when its page is opened if its output (here the
# app-wide store) already exists, even with prevent_initial_call; a separate "render" callback chained on the
# store would then be skipped. So: on page entry → show the stored assessment; on click → import, store, show.
@callback(Output("store-sri", "data"), Output("imp-msg", "children"), Output("sri-view", "children"),
          Input("imp-button", "n_clicks"),
          State("store-sri", "data"), State("imp-method", "value"),
          State("imp-upload", "contents"), State("imp-upload", "filename"))
def import_or_show(n_clicks, stored, method, contents, filename):
    if ctx.triggered_id != "imp-button" or not n_clicks:
        return no_update, no_update, render(stored)
    try:
        data = import_assessment(method or "eu_excel", contents, filename)
    except Exception as exc:  # noqa: BLE001 – show any import problem to the user
        return no_update, html.Div(f"Import failed: {exc}", className="msg msg-error"), no_update
    b, src = data["building"], data["source"]
    msg = (f"Imported “{b['name']}” – {src['tool']} v{src['version']}, Method {data['method']['catalogue']}, "
           f"{len(data['services'])} services.")
    return data, html.Div(msg, className="msg msg-ok"), render(data)
