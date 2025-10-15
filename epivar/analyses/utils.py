import pandas as pd
import numpy as np
from statsmodels.stats.multitest import multipletests


def _clean_gsea_table(df: pd.DataFrame, correction_method: str) -> pd.DataFrame:
    # drop default values
    df = df.drop(
        [
            "Adjusted P-value",
            "Combined Score",
        ],
        axis=1,
    )

    # recalculate
    eps = np.nextafter(0, 1)
    _, df["Adjusted P-value"], _, _ = multipletests(
        df["P-value"], method=correction_method, alpha=0.05, is_sorted=False
    )
    df["-log10(Adjusted P-value)"] = df["Adjusted P-value"].map(
        lambda x: -np.log10(x + eps)
    )
    df["Combined Score"] = df["-log10(Adjusted P-value)"] * df["Odds Ratio"]

    return df.sort_values("Odds Ratio", ascending=False)


def _clean_loa_table(df: pd.DataFrame, correction_method: str) -> pd.DataFrame:
    eps = np.nextafter(0, 1)
    _, df["Adjusted P-value"], _, _ = multipletests(
        df["P-value"], method=correction_method, alpha=0.05, is_sorted=False
    )
    df["-log10(Adjusted P-value)"] = df["Adjusted P-value"].map(
        lambda x: -np.log10(x + eps)
    )
    df["Combined Score"] = df["-log10(Adjusted P-value)"] * df["Odds Ratio"]

    return df.sort_values("Odds Ratio", ascending=False)
