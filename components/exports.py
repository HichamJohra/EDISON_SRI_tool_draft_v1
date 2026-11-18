"""Export bar shared by "5. SRI upgrade assessment" and "6. Upgrade plan": download buttons and a print button
(the browser's print dialog with the print layout of assets/style.css → "Save as PDF")."""
from dash import Input, Output, clientside_callback, dcc, html


def export_bar(prefix: str, formats: list[tuple[str, str]], note: str) -> html.Div:
    """Download buttons and 'Print / save as PDF' (the browser's print dialog, with a print layout)."""
    return html.Div(className="action-bar export-bar no-print", children=[
        dcc.Link("← 4. Optimization", href="/optimization", className="btn btn-outline"),
        html.Span(className="action-sep"),
        *[html.Button(label, id=f"{prefix}-dl-{fmt}", className="btn") for fmt, label in formats],
        html.Button("Print / save as PDF", id=f"{prefix}-print", className="btn btn-outline"),
        html.Span(note, className="field-hint"),
        dcc.Download(id=f"{prefix}-download"),
    ])


def print_callback(prefix: str) -> None:
    clientside_callback("function(n) { if (n) { if (window.edisonBeforePrint) { window.edisonBeforePrint(); } "
                        "setTimeout(function () { window.print(); }, 400); } "
                        "return window.dash_clientside.no_update; }",
                        Output(f"{prefix}-print", "title"), Input(f"{prefix}-print", "n_clicks"),
                        prevent_initial_call=True)
