"""Step 2: decision mode and constraints."""
import dash
from dash import Input, Output, State, callback, ctx, dcc, html, no_update

from components.ui import card, control, page_head
from edison_sri.catalogue import DEFAULT_OBJECTIVES
from edison_sri.requirements import COST_DATABASES

dash.register_page(__name__, path="/objectives", name="3. Objectives & constraints", order=3,
                   title="Objectives & constraints · EDISON SRI upgrade tool")

layout = html.Div([
    page_head("3. Objectives & constraints", "Choose what the upgrade plan should achieve, and the cost data "
                                           "used for prices and technical requirements."),
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
    card(title="Cost data", subtitle="Used for the prices and technical requirements on “2. Smart services” and "
                                    "for the upgrade plan.", children=html.Div(className="grid-2", children=[
        control("Cost database", dcc.Dropdown(
            [{"label": v["name"], "value": k, "disabled": not v["available"]} for k, v in COST_DATABASES.items()],
            id="o-costdb", clearable=False)),
        control("Heated floor area for cost estimates (m²)",
                # min=0 so that every multiple of the step is valid (with min=1, 5000 would be refused by the browser)
                dcc.Input(id="o-area", type="number", min=0, step=100, className="field-input")),
    ])),
    html.Div([html.Button("Save objectives", id="o-save", className="btn"),
              html.Span(id="o-saved", className="muted", style={"marginLeft": "12px"})], style={"marginTop": "18px"}),
])


@callback(Output("o-class", "disabled"), Output("o-budget", "disabled"), Input("o-mode", "value"))
def toggle(mode):
    return mode != "target", mode != "budget"


# One callback for load AND save (see the note in pages/assessment.py): on page entry → fill the fields from the
# store; on click → save the fields to the store.
@callback(Output("store-objectives", "data"), Output("o-saved", "children"),
          Output("o-mode", "value"), Output("o-class", "value"), Output("o-budget", "value"),
          Output("o-costdb", "value"), Output("o-area", "value"),
          Input("o-save", "n_clicks"),
          State("store-objectives", "data"),
          State("o-mode", "value"), State("o-class", "value"), State("o-budget", "value"),
          State("o-costdb", "value"), State("o-area", "value"))
def load_or_save(n_clicks, stored, mode, cls, budget, cost_db, area):
    if ctx.triggered_id != "o-save" or not n_clicks:
        s = {**DEFAULT_OBJECTIVES, **(stored or {})}  # older sessions may lack the newer keys
        return (no_update, no_update, s["mode"], s["target_class"], s["budget_nok"], s["cost_db"],
                s["floor_area_m2"])
    data = {"mode": mode, "target_class": cls, "budget_nok": budget or 0, "cost_db": cost_db or "default",
            "floor_area_m2": area or DEFAULT_OBJECTIVES["floor_area_m2"]}
    return data, "Saved.", *[no_update] * 5
