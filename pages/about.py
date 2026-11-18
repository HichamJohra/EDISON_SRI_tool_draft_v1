"""About page: what the draft does and what is dummy."""
import dash
from dash import dcc, html

from components.ui import card, page_head

dash.register_page(__name__, path="/about", name="About", order=99, title="About · EDISON SRI upgrade tool")

DRAFT = """
* **Dummy catalogue** of 8 services and dummy cost matrices (NOK/m² plus a fixed cost per upgrade).
* **Placeholder SRI**: weighted mean of normalised levels per domain – not the EU method.
* **Exact selection** by exhaustive search; to be replaced by an optimisation solver (MILP) for the full
  27- or 54-service catalogues.
* **Not yet included**: energy savings, running costs, roadmap, shared equipment between services.
"""

layout = html.Div([
    page_head("About", "EDISON SRI upgrade decision tool – draft v1"),
    card(dcc.Markdown(DRAFT), title="What this draft does"),
    card(html.P(["SINTEF – EDISON project, Research Council of Norway project 357860. ",
                 html.A("Project page", href="https://www.sintef.no/en/projects/2025/edison/", target="_blank",
                        rel="noopener noreferrer", className="link-strong")]),
         title="Project"),
    html.Div(html.Img(src=dash.get_asset_url("logos/edison_logo.png"), alt="EDISON"), className="about-logo"),
])
