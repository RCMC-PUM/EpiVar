import numpy as np
import pandas as pd
import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go
import dash_bio as dashbio


def qq(
        path: str,
        pval_column: str = "p-value",
        name_col: str = "name",
        sample: int = 25_000,
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

    fig.add_trace(
        go.Scatter(
            x=[1.5],
            y=[3],
            mode="text",
            name="λ=Inflation factor",
            text=[f"λ={inflation_factor:2f}"],
            textposition="top center",
        )
    )

    fig.update_layout(
        xaxis_title="-log10(Expected p-value)",
        yaxis_title="-log10(Observed p-value)",
        template="plotly_white",
    )

    return pio.to_json(fig, validate=True)


def prepare_for_manhattan(path: str, n: int = 25_000) -> pd.DataFrame:
    """
    Prepare GWAS-style TSV/CSV into dataframe for dash_bio.ManhattanPlot.
    Required columns → CHR:int (1-25), BP:int, P:float
    Optional extras (e.g. name, es) are merged into annotation text.
    """
    df = pd.read_csv(path, sep="\t").dropna()
    df = df.sample(n=n, random_state=101)

    # Rename columns to expected
    col_map = {"#chrom": "CHR", "start": "BP", "p-value": "P"}
    df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})

    # Map chromosomes to numeric (X=23, Y=24, MT=25)
    chrom_map = {str(i): i for i in range(1, 23)}
    chrom_map.update({"X": 23, "Y": 24, "MT": 25, "M": 25})
    df["CHR"] = df["CHR"].astype(str).map(chrom_map)

    # Ensure correct types
    df = df.dropna(subset=["CHR", "BP", "P"]).copy()
    df["CHR"] = df["CHR"].astype(int)
    df["BP"] = df["BP"].astype(int)
    df["P"] = df["P"].astype(float)

    # Build hover/annotation text
    parts = []
    if "name" in df.columns:
        parts.append("name: " + df["name"].astype(str))
    if "P" in df.columns:
        parts.append("p-value: " + df["P"].map("{:.2e}".format))
    if "es" in df.columns:
        parts.append("effect size: " + df["es"].map("{:.3f}".format))

    if parts:
        df["name"] = pd.concat(parts, axis=1).agg(" | ".join, axis=1)
    else:
        df["name"] = df.index.astype(str)

    # Sort so traces are created in natural order
    df = df.sort_values(["CHR", "BP"]).reset_index(drop=True)
    return df[["CHR", "BP", "P", "name"]]


def relabel_from_traces(fig):
    """
    Read x-ranges from traces, compute chromosome midpoints,
    and relabel axis ticks as chr1..chr22, chrX, chrY, chrMT.
    """
    tickvals, ticktext = [], []

    for tr in fig.data:
        if not hasattr(tr, "x") or tr.x is None or len(tr.x) == 0:
            continue

        mid = (min(tr.x) + max(tr.x)) / 2
        tickvals.append(mid)

        name = tr.name if hasattr(tr, "name") else ""
        label = name
        if isinstance(name, str) and name.lower().startswith("chr"):
            try:
                n = int(name[3:])
                if 1 <= n <= 22:
                    label = f"chr{n}"
                elif n == 23:
                    label = "chrX"
                elif n == 24:
                    label = "chrY"
                elif n == 25:
                    label = "chrMT"
            except ValueError:
                pass
        ticktext.append(label)

    fig.update_layout(
        xaxis=dict(
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext
        )
    )
    return fig


def manhattan(path: str, n: int = 25_000):
    """
    Build and show a Manhattan plot from a GWAS-style file.
    """
    df = prepare_for_manhattan(path, n)
    fig = dashbio.ManhattanPlot(
        dataframe=df,
        snp=None,
        gene=None,
        title=None,
        annotation="name",  # hover/annotation text
        showlegend=False,
        genomewideline_value=-np.log10(5e-8),
        suggestiveline_value=None,
    )
    fig = relabel_from_traces(fig)
    return fig.to_json(validate=True)


def violin(
        path: str,
        chr_col: str = "#chrom",
        value_col: str = "me",
        sample: int = 25_000,
):
    """
    Boxplot plotly.express.

    Parameters
    ----------
    path : str
        Path to TSV file.
    chr_col : str
        Chromosome column name.
    value_col : str
        Column with numeric values (mean).
    sample : int
        Number of points to subsample for plotting.
    """
    usecols = [chr_col, value_col]
    df = pd.read_csv(path, sep="\t", usecols=usecols, engine="pyarrow").dropna()

    # Downsample if needed
    if len(df) > sample:
        df = df.sample(n=sample, random_state=101)

    # Standardize chromosome labels with "chr" prefix
    df[chr_col] = df[chr_col].astype(str)
    df[chr_col] = df[chr_col].map(lambda x: f"chr{x}")

    # Define correct chromosome order
    chr_order = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY", "chrMT"]

    # Restrict to chromosomes we know
    df = df[df[chr_col].isin(chr_order)]

    # Make column categorical with correct order
    df[chr_col] = pd.Categorical(df[chr_col], categories=chr_order, ordered=True)

    # Plot violin
    fig = px.violin(df, box=True, x=chr_col, y=value_col, category_orders={chr_col: chr_order})
    fig.update_layout(
        xaxis=dict(
            title="Chromosome",
        ),
        yaxis=dict(title="Mean values"),
        template="plotly_white",
        showlegend=False,
        margin=dict(l=60, r=20, t=20, b=60),
    )
    return fig.to_json(validate=True)


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
