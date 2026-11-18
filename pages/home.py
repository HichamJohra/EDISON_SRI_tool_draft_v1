"""Home page: purpose of the tool and links to the three steps."""
import dash
from dash import dcc, html

from components.ui import card, page_head

dash.register_page(__name__, path="/", name="Home", order=0, title="Home · EDISON SRI upgrade tool")

STEPS = [
    ("1. Building and assessment", "/assessment",
     "Building data and the current functionality level of each smart-ready service."),
    ("2. Objectives", "/objectives",
     "Target mode (cheapest way to reach an SRI class) or budget mode (highest SRI for a given budget)."),
    ("3. Upgrade plan", "/results",
     "Recommended upgrades with their cost, the SRI after upgrade, and the cost–SRI curve."),
]

layout = html.Div([
    page_head("SRI upgrade decision tool",
              "Draft of the EDISON tool: from an SRI assessment, recommend which smart-ready services to upgrade, "
              "to which level and at what cost. All data are dummy values."),
    html.Div(className="grid-3", children=[
        card([html.P(desc, className="muted"), dcc.Link("Open →", href=href, className="link-strong")],
             title=title, className="step-card")
        for title, href, desc in STEPS
    ]),
    html.Div(html.Img(src=dash.get_asset_url("logos/edison_logo.png"), alt="EDISON"), className="about-logo"),
])
