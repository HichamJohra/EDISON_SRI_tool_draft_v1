"""EDISON SRI upgrade decision tool – draft multi-page Dash web app.

Run locally:  python app.py   ->  http://127.0.0.1:8050
Layout and style follow the NSBI Smart Building Mapping web app.
"""
import dash
from dash import Dash, dcc, html

from edison_sri.catalogue import DEFAULT_ASSESSMENT, DEFAULT_OBJECTIVES

app = Dash(
    __name__,
    use_pages=True,  # every module in ./pages registering itself becomes a page
    title="EDISON SRI upgrade tool",
    suppress_callback_exceptions=True,
)
server = app.server  # WSGI entry point for later deployment (gunicorn app:server)
# The browser-tab icon is assets/favicon.ico (SINTEF), picked up automatically by Dash.

# Logos shown at the top right of every page (files in assets/logos/): (file, name, link, extra CSS class)
LOGOS = [
    ("logos/edison_logo.png", "EDISON project", "https://www.sintef.no/en/projects/2025/edison/", "nav-logo-light"),
    ("logos/sintef_logo.png", "SINTEF Community", "https://www.sintef.no/en/community/", ""),
]


def navbar() -> html.Header:
    links = [
        dcc.Link(page["name"], href=page["relative_path"], className="nav-link")
        for page in dash.page_registry.values()
    ]
    logos = [html.A(html.Img(src=app.get_asset_url(path), alt=name, className=f"nav-logo {extra}".strip()),
                    href=url, target="_blank", rel="noopener noreferrer", title=f"{name} – {url}")
             for path, name, url, extra in LOGOS]
    return html.Header(
        className="navbar",
        children=[
            html.Div("EDISON SRI upgrade tool", className="brand"),
            html.Div(className="nav-right", children=[html.Nav(links), html.Div(logos, className="nav-logos")]),
        ],
    )


# Shared state between pages. storage_type="session" = the browser's sessionStorage: kept while moving between
# pages and on reload, separate for every browser tab, cleared when the tab is closed.
app.layout = html.Div([
    dcc.Store(id="store-assessment", storage_type="session", data=DEFAULT_ASSESSMENT),
    dcc.Store(id="store-objectives", storage_type="session", data=DEFAULT_OBJECTIVES),
    navbar(),
    html.Main(dash.page_container, className="container"),
])


if __name__ == "__main__":
    app.run(debug=True)
