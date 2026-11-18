"""Home page: goal, method, features and planned development of the EDISON SRI upgrade tool."""
import dash
from dash import dcc, html

from components.ui import card

dash.register_page(__name__, path="/", name="Home", order=0, title="Home · EDISON SRI upgrade tool")

GOALS = [
    ("From score to plan",
     "Turn an SRI assessment into an actionable upgrade plan: which smart-ready services to upgrade, "
     "to which functionality level, at what cost and in which order."),
    ("Two decision modes",
     "Target mode finds the cheapest way to reach a chosen SRI class. Budget mode finds the highest SRI "
     "reachable with a given investment."),
    ("Realistic upgrade costs",
     "Each service level is mapped to the technical requirements it needs. Each requirement is priced once, "
     "so equipment shared by several services is not paid twice, and items already in the building cost nothing."),
    ("Norwegian context",
     "Norwegian prices, building categories and language, designed to plug into SRI Norsk "
     "(NHO Elektro) as a free SINTEF add-on."),
    ("Transparent results",
     "Open method, scoring checked against the official SRI calculation, the full cost–SRI curve and the "
     "maximum feasible SRI of the building."),
]

FEATURES = [
    ("1. SRI assessment", "/assessment",
     "Import an existing SRI assessment (EDISON JSON, EU calculation sheet or SRI Norsk) and view its scores."),
    ("2. Smart services", "/services",
     "Each service's levels, technical requirements, and how SRI, cost and requirements change level by level."),
    ("3. Objectives & constraints", "/objectives",
     "Target mode (SRI class) or budget mode (investment limit), cost database and floor area."),
    ("4. Upgrade plan", "/results",
     "Recommended upgrades with their cost, the SRI after upgrade and the cost–SRI curve."),
]

PLANNED = [
    ("Official SRI engine", "Method A (27 services) and Method B (54 services), with a parity test against the "
                            "EU calculation sheet, the open-source iEPB kernel and SRI Norsk."),
    ("Import of assessments", "EDISON pilot assessments (Excel → JSON) and the SRI Norsk export."),
    ("Technical requirement library", "Requirement list per service level, with Norwegian costs from EDISON partners, "
                                      "ISO 52120-1 and the Statsbygg catalogue."),
    ("Exact optimiser", "Integer programming (MILP) for target and budget modes on the full service catalogues."),
    ("Operating costs and roadmap", "Running costs per m² and a staged upgrade roadmap."),
    ("Reports", "Recommendation text for the SRI certificate and exportable results."),
    ("Energy savings and flexibility", "Energy savings from the energy certificate baseline and value of energy "
                                       "flexibility (later version)."),
    ("Integration in SRI Norsk", "Standalone module with a fixed input and output, offered as a free add-on."),
]


def _img(file: str, alt: str, caption: str) -> html.Figure:
    return html.Figure(className="figure", children=[
        html.Img(src=dash.get_asset_url(f"images/{file}"), alt=alt),
        html.Figcaption(caption),
    ])


layout = html.Div([
    # Banner with the tool's purpose
    html.Div(className="hero", style={"backgroundImage": f"url({dash.get_asset_url('images/edison_banner.jpg')})"},
             children=html.Div(className="hero-text", children=[
                 html.H1("SRI upgrade decision tool"),
                 html.P("Which smart-ready upgrades give a building the most smartness for the money?"),
                 dcc.Link("Start with an assessment →", href="/assessment", className="hero-btn"),
             ])),

    card(title="Goal of the tool", subtitle="Developed in EDISON work package 1 (SINTEF, 2025–2029)", children=[
        dcc.Markdown(
            "The **Smart Readiness Indicator (SRI)** rates how ready a building is to use smart technologies, "
            "but it does not tell an owner or an assessor **what to upgrade next**. Starting from the building's "
            "current SRI assessment and the owner's objectives and constraints, the tool searches the possible "
            "upgrades and returns the list of upgraded services, their investment and operating costs per m² and "
            "the technical requirements to install."),
        _img("upgrade_plan_concept.png", "Concept: initial services and objectives go into an optimiser that returns "
             "upgraded services, costs and technical requirements, plotted on a cost–SRI curve",
             "From the initial list of services to the cheapest upgrade plan on the cost–SRI curve."),
    ]),

    html.H2("Goals", className="section-title"),
    html.Div(className="goal-grid", children=[
        html.Div(className="goal", children=[html.Div(str(i + 1), className="goal-num"),
                                            html.Div([html.H3(t), html.P(d)])])
        for i, (t, d) in enumerate(GOALS)
    ]),

    card(title="Methodology: pricing technical requirements",
         subtitle="Upgrade costs come from the technical requirements that the target service levels need.",
         children=[
             _img("methodology_requirements.png", "Methodology: target service levels map to technical "
                  "requirements; requirements to buy are priced once, those already in the building cost nothing",
                  "The cost of an upgrade is the sum of the requirements not yet in the building; "
                  "the list itself is a second output."),
         ]),

    html.H2("What the draft does today", className="section-title"),
    html.Div(className="grid-4", children=[
        card([html.P(desc, className="muted"), dcc.Link("Open →", href=href, className="link-strong")],
             title=title, className="step-card")
        for title, href, desc in FEATURES
    ]),
    html.Div("Draft: dummy service catalogue, dummy costs and a placeholder SRI formula.",
             className="msg msg-warn"),

    card(title="Planned development", children=html.Ul(className="plan-list", children=[
        html.Li([html.Strong(t), html.Span(f" – {d}")]) for t, d in PLANNED
    ])),

    html.Div(html.Img(src=dash.get_asset_url("logos/edison_logo.png"), alt="EDISON"), className="about-logo"),
])
