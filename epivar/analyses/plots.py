import plotly.express as px


def bubble_plot(
    df,
    x="Odds Ratio",
    y="-log10(Adjusted P-value)",
    color="Combined Score",
    size="Overlap fraction",
    hover="Term",
):
    """Return Plotly HTML div for a single collection subset."""
    fig = px.scatter(
        df, x=x, y=y, size=size, color=color, hover_name=hover, template="plotly_white"
    )
    return fig.to_html(include_plotlyjs=False, full_html=False)
