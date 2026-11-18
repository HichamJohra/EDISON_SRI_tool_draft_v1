"""Step 2: decision mode and constraints."""
import dash
from dash import Input, Output, State, callback, dcc, html, no_update

from components.ui import card, control, page_head

dash.register_page(__name__, path="/objectives", name="2. Objectives", order=2,
                   title="Objectives · EDISON SRI upgrade tool")

layout = html.Div([
    page_head("2. Objectives and constraints", "Choose what the upgrade plan should achieve."),
    html.Div(className="grid-2", children=[
        card(title="Decision mode", children=dcc.RadioItems(
            [{"label": " Target mode – reach an SRI class at the lowest cost", "value": "target"},
             {"label": " Budget mode – highest SRI within a budget", "value": "budget"}],
            id="o-mode", className="radio")),
        card(title="Constraints", subtitle="Energy savings and running costs come in later versions.", children=[
            control("Target SRI class", dcc.Dropdown(list("ABCDEF"), id="o-class", clearable=False)),
            control("Budget (NOK, investment)",
                    dcc.Input(id="o-budget", type="number", min=0, step=10_000, className="field-input")),
        ]),
    ]),
    html.Div([html.Button("Save objectives", id="o-save", className="btn"),
              html.Span(id="o-saved", className="muted", style={"marginLeft": "12px"})], style={"marginTop": "18px"}),
])


@callback(Output("o-mode", "value"), Output("o-class", "value"), Output("o-budget", "value"),
          Input("store-objectives", "data"))
def load(data):
    return data["mode"], data["target_class"], data["budget_nok"]


@callback(Output("o-class", "disabled"), Output("o-budget", "disabled"), Input("o-mode", "value"))
def toggle(mode):
    return mode != "target", mode != "budget"


@callback(Output("store-objectives", "data"), Output("o-saved", "children"),
          Input("o-save", "n_clicks"),
          State("o-mode", "value"), State("o-class", "value"), State("o-budget", "value"),
          prevent_initial_call=True)
def save(n_clicks, mode, cls, budget):
    if not n_clicks or not mode:  # guard against a firing when the page is inserted
        return no_update, no_update
    return {"mode": mode, "target_class": cls, "budget_nok": budget or 0}, "Saved."
