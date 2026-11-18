"""Small reusable layout blocks (same helpers and CSS classes as the NSBI web app)."""
from typing import Any

from dash import dcc, html

# Plotly options shared by all graphs (hide the Plotly logo in the mode bar). Typed as Any because dcc.Graph's
# `config` prop is a TypedDict in Dash 3+, which makes IDEs flag a plain dict literal.
# noinspection SpellCheckingInspection
GRAPH_CONFIG: Any = {"displaylogo": False}


def page_head(title: str, subtitle: str = "") -> html.Div:
    return html.Div(className="page-head", children=[html.H1(title), html.P(subtitle)])


def card(children, title: str | None = None, subtitle: str | None = None, className: str = "") -> html.Div:
    head = []
    if title:
        head.append(html.H3(title, className="card-title"))
    if subtitle:
        head.append(html.P(subtitle, className="card-subtitle"))
    return html.Div(head + (children if isinstance(children, list) else [children]), className=f"card {className}")


def control(label: str, component) -> html.Div:
    return html.Div([html.Label(label, className="control-label"), component], className="control")


def kpi_static(label: str, value: str, sub: str = "", description: str = "") -> html.Div:
    """KPI card with a fixed value; `description` is shown on hover."""
    return html.Div([html.Div(label, className="kpi-label"), html.Div(value, className="kpi-value"),
                     html.Div(sub, className="kpi-sub")], className="kpi", title=description or None)


def graph(gid: str, height: int | None = None, **kwargs) -> dcc.Loading:
    style = {"height": f"{height}px"} if height else {}
    return dcc.Loading(dcc.Graph(id=gid, config=GRAPH_CONFIG, style=style, **kwargs), type="default")


def info_table(rows: list[dict]) -> html.Table:
    """Plain HTML table with the NSBI 'info-table' style; rows = list of dicts with the same keys."""
    if not rows:
        return html.Table()
    cols = list(rows[0])
    return html.Table(className="info-table compare-table", children=[
        html.Thead(html.Tr([html.Th(c) for c in cols])),
        html.Tbody([html.Tr([html.Td(r[c]) for c in cols]) for r in rows]),
    ])
