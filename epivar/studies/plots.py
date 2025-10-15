import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


def qq(
        path: str,
        pval_column: str = "p-value",
        name_col: str = "name",
        sample: int = 10_000,
) -> str:
    """
    Load a TSV file, extract the p-value column, draw a QQ-plot
    against Uniform(0,1) on the -log10 scale, and return an HTML string.
    """
    # Load and sort
    usecols = [pval_column, name_col]
    df = pd.read_csv(
        path,
        sep="\t",
        usecols=usecols,
        engine="pyarrow",
        dtype={
            "name_col": "string",
            "pval_column": "float64",
        },
    ).dropna()

    df = df.sample(n=sample, random_state=101)
    df = df.sort_values(pval_column, ascending=True)

    # Expected vs observed
    n = len(df)
    obs = df[pval_column].values
    exp = (np.arange(1, n + 1) - 0.5) / n

    # Transform to -log10
    x = -np.log10(exp)
    y = -np.log10(obs)

    # Inflation factor
    inflation_factor = np.median(y) / np.median(x)

    # Reference line
    max_xy = float(max(x.max(), y.max()))

    # Plot
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=x,
            y=y,
            mode="markers",
            name="Observed",
            text=df[name_col],
            hovertemplate=(
                "%{text}<br>"
                "-log10(Expected): %{x:.3f}<br>"
                "-log10(Observed): %{y:.3f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scattergl(
            x=[0, max_xy],
            y=[0, max_xy],
            mode="lines",
            name="Expected",
            line=dict(dash="dash"),
        )
    )

    fig.add_trace(go.Scatter(
        x=[1.5],
        y=[3],
        mode="text",
        name="λ=Inflation factor",
        text=[f"λ={inflation_factor:2f}"],
        textposition="top center"
    ))

    fig.update_layout(
        xaxis_title="-log10(Expected p-value)",
        yaxis_title="-log10(Observed p-value)",
        template="plotly_white",
    )

    return pio.to_json(fig, validate=True)


def manhattan(
        path: str,
        chr_col: str = "#chrom",
        pos_col: str = "start",
        name_col: str = "name",
        value_col: str = "-log10(p-value)",
        metric: str = "-log10(p-value)",  # "me" | "se" | "-log10(p-value)"
        genomewide_line: float | None = -np.log10(5e-08),
        sample: int = 25_000,
) -> str:
    """
    Manhattan-style scatter plot.

    Parameters
    ----------
    path : str
        Path to TSV file.
    chr_col : str
        Chromosome column name.
    pos_col : str
        Position column name.
    value_col : str
        Column with numeric values.
    name_col : str
        Column with labels (hover text).
    metric : str
        Which metric to plot on y-axis:
        - "me" → log(mean values)
        - "se"   → log(Standard Error)
        - "-log10(p-value)" → classic Manhattan
    genomewide_line : float | None
        Y-value for genome-wide significance line (only for p-values).
    sample : int
        Number of points to subsample for plotting.
    """
    usecols = [chr_col, pos_col, value_col, name_col]
    df = pd.read_csv(
        path,
        sep="\t",
        usecols=usecols,
        engine="pyarrow",
        dtype={
            "chr_col": "string",
            "pos_col": "int64",
            "value_col": "float64",
            "name_col": "string",
        },
    ).dropna()

    if len(df) > sample:
        df = df.sample(n=sample, random_state=101)

    # Normalize chromosome column
    df[chr_col] = df[chr_col].astype(str).replace({"X": 23, "Y": 24, "MT": 25})
    df[chr_col] = pd.to_numeric(df[chr_col], errors="coerce")
    df = df.dropna(subset=[chr_col, pos_col, value_col]).copy()
    df = df.sort_values([chr_col, pos_col])

    # Compute Y values
    if metric == "me":
        y_title = "Mean value"
        hover_y = "Mean value: %{y:.2f}"
        df["yval"] = df[value_col]

    elif metric == "se":
        y_title = "-log10(standard error)"
        hover_y = "-log10(standard error): %{y:.2f}"
        df["yval"] = -np.log(df[value_col])

    elif metric == "-log10(p-value)":
        y_title = "-log10(p-value)"
        hover_y = "-log10(p): %{y:.2f}"
        df["yval"] = -np.log(df[value_col])

    else:
        raise ValueError("metric must be 'mean', 'se', or '-log10(p-value)'")

    # Compute cumulative positions
    ticks, labels, offsets = [], [], {}
    cumulative = 0
    for chrom in sorted(df[chr_col].unique()):
        offsets[chrom] = cumulative
        chrom_max = df.loc[df[chr_col] == chrom, pos_col].max()
        ticks.append(cumulative + chrom_max / 2)
        labels.append(int(chrom))
        cumulative += chrom_max

    df["pos_cum"] = df.apply(lambda r: r[pos_col] + offsets[r[chr_col]], axis=1)
    mapper = {23: "X", 24: "Y", 25: "MT"}

    # Plot
    fig = go.Figure()
    for i, chrom in enumerate(labels):
        dff = df[df[chr_col] == chrom]
        chrom_label = mapper.get(chrom, chrom)

        fig.add_trace(
            go.Scattergl(
                x=dff["pos_cum"],
                y=dff["yval"],
                mode="markers",
                marker=dict(color="blue" if i % 2 == 0 else "gray", size=4),
                name=f"chr{chrom_label}",
                text=dff[name_col],
                hovertemplate=(
                    "%{text}<br>"
                    f"chr{chrom_label}<br>"
                    "Position: %{x}<br>"
                    f"{hover_y}"
                ),
            )
        )

    labels = [f"chr{mapper[x]}" if x in mapper else f"chr{int(x)}" for x in labels]

    fig.update_layout(
        xaxis=dict(
            title="Chromosome",
            tickmode="array",
            tickvals=ticks,
            ticktext=labels,
            showticklabels=True,
        ),
        yaxis=dict(title=y_title),
        template="plotly_white",
        showlegend=False,
        margin=dict(l=60, r=20, t=20, b=60),
    )

    # Genome-wide significance line (only for p-value metric)
    if metric == "-log10(p-value)" and genomewide_line is not None:
        fig.add_hline(
            y=genomewide_line,
            line=dict(color="red", dash="dash"),
            annotation_text="5 × 10⁻⁸",
            annotation_position="top left",
        )

    return pio.to_json(fig, validate=True)


def heatmap(
    path: str,
    chr_col: str = "#chrom",
    pos_col: str = "start",
    name_col: str = "name",
    value_col: str = "pval",
    metric: str = "me",
    sample: int = 25_000,
):
    """
    Manhattan-style plot using plotly.express.

    Parameters
    ----------
    path : str
        Path to TSV file.
    chr_col : str
        Chromosome column name.
    pos_col : str
        Position column name.
    value_col : str
        Column with numeric values (pval, mean, or SE).
    name_col : str
        Column with labels (hover text).
    metric : str
        Which metric to plot on y-axis:
        - "me" → mean values
        - "se" → -log(standard error)
        - "-log10(p-value)" → classic Manhattan
    genomewide_line : float | None
        Y-value for genome-wide significance line (only for p-values).
    sample : int
        Number of points to subsample for plotting.
    """

    usecols = [chr_col, pos_col, value_col, name_col]
    df = pd.read_csv(path, sep="\t", usecols=usecols, engine="pyarrow").dropna()

    if len(df) > sample:
        df = df.sample(n=sample, random_state=101)

    # Normalize chromosome identifiers
    df[chr_col] = df[chr_col].astype(str).replace({"X": 23, "Y": 24, "MT": 25})
    df[chr_col] = pd.to_numeric(df[chr_col], errors="coerce")
    df = df.dropna(subset=[chr_col, pos_col, value_col]).copy()
    df = df.sort_values([chr_col, pos_col])

    df["yval"] = df[value_col]

    # Compute cumulative positions
    ticks, labels, offsets = [], [], {}
    cumulative = 0
    for chrom in sorted(df[chr_col].unique()):
        offsets[chrom] = cumulative
        chrom_max = df.loc[df[chr_col] == chrom, pos_col].max()
        ticks.append(cumulative + chrom_max / 2)
        labels.append(int(chrom))
        cumulative += chrom_max

    df["pos_cum"] = df.apply(lambda r: r[pos_col] + offsets[r[chr_col]], axis=1)
    df["chrom_label"] = df[chr_col].fillna(df[chr_col].astype(int).astype(str))

    # Plot using plotly.express
    fig = px.scatter(
        df,
        x="pos_cum",
        y="yval",
        color="chrom_label",
        hover_data={name_col: True, pos_col: True, chr_col: True},
        title="Manhattan Plot",
        labels={"yval": y_title, "pos_cum": "Genomic position"},
    )

    # Adjust layout
    fig.update_traces(marker=dict(size=4), selector=dict(mode="markers"))
    fig.update_layout(
        xaxis=dict(
            tickmode="array",
            tickvals=ticks,
            ticktext=[f"chr{mapper.get(x, int(x))}" for x in labels],
            title="Chromosome"
        ),
        yaxis=dict(title=y_title),
        template="plotly_white",
        showlegend=False,
        margin=dict(l=60, r=20, t=20, b=60),
    )

    # Genome-wide significance line
    if metric == "-log10(p-value)" and genomewide_line is not None:
        fig.add_hline(
            y=genomewide_line,
            line=dict(color="red", dash="dash"),
            annotation_text="5 × 10⁻⁸",
            annotation_position="top left",
        )

    return fig


def bar(data: dict[str, int], title: str = "") -> str:
    """
    Create a horizontal bar plot from a dictionary {name: count},
    ordered descending, and return an embeddable HTML string.
    """
    # Sort descending by count
    items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)
    names, counts = zip(*items) if items else ([], [])

    # Plot (Bar, orientation='h')
    fig = go.Figure(
        go.Bar(
            y=counts,
            x=names,
            text=names,
            hovertemplate=(
                "%{text}<br>"  # name on top
                "Count: %{y}<extra></extra>"
            ),
            marker=dict(color="steelblue"),
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="",
        yaxis_title="",
        template="plotly_white",
        margin=dict(l=100, r=40, t=40, b=40),
    )

    return pio.to_json(fig, validate=True)


def plotly_html_from_json(
        fig_json,
        *,
        full_html: bool = False,
        include_plotlyjs="cdn",
        div_id=None,
        default_width="100%",
        default_height=450,
        config=None,
) -> str | None:
    """
    Convert a JSON-serialized Plotly figure to HTML.

    Parameters
    ----------
    fig_json :
        The JSON figure as a string or dict (e.g., output of `fig.to_json()`).
    full_html :
        If True, returns a complete HTML document. If False (default), returns a
        standalone <div> you can embed in an existing page.
    include_plotlyjs :
        Controls inclusion of the Plotly JS bundle. Options:
          - True:  embed the full bundle inline
          - False: assume it's already loaded on the page
          - "cdn": load from Plotly's CDN (recommended for snippets)
    div_id :
        Optional ID for the root <div>. If None, Plotly auto-generates one.
    default_width, default_height :
        Dimensions used if the figure layout doesn't specify them.
        Width may be a CSS string (e.g. "100%") or an integer pixel value.
    config :
        Optional Plotly config dict (e.g., {"responsive": True, "displaylogo": False}).

    Returns
    -------
    str
        HTML string containing the figure.
    """
    # Accept dicts or JSON strings
    if isinstance(fig_json, str):
        fig = pio.from_json(fig_json)
    else:
        return None

    html = pio.to_html(
        fig,
        full_html=full_html,
        include_plotlyjs=include_plotlyjs,
        div_id=div_id,
        default_width=default_width,
        default_height=default_height,
        config=config,
    )
    return html
