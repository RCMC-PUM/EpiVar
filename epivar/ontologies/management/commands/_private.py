import os
import tempfile
from pathlib import Path

import pandas as pd
import requests
from pandas.errors import ParserError
from urllib.parse import urlsplit


def _download_file(
    url: str,
    dest: os.PathLike | str | None = None,
    timeout: int = 30,
    chunk_size: int = 8192,
) -> Path:
    """
    Download a file from `url` and return its local Path.

    - If `dest` is provided, the file is saved exactly there (creating parent dirs).
    - If `dest` is None, a persistent temporary directory is created and the file is
      saved inside it. The caller is responsible for cleaning it up later.
    """
    # Derive a filename from URL if needed
    url_path = urlsplit(url).path
    default_name = (url_path.rsplit("/", 1)[-1]) or "downloaded_file"

    if dest is None:
        tmpdir = Path(tempfile.mkdtemp(prefix="download_"))
        dest_path = tmpdir / default_name
    else:
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download file from {url!r}") from e

    return dest_path


# Keep a stable order for columns
EXPECTED_COLUMNS = ["AS/1", "AS/1/ID", "CT/1", "CT/1/ID"]


def _parse_asct_table(
    path: os.PathLike | str,
    max_skip_rows: int = 25,
) -> pd.DataFrame:
    """
    Try to parse an ASCT+ table CSV, skipping up to `max_skip_rows` lines
    to find the header containing EXPECTED_COLUMNS.

    Returns a DataFrame with only EXPECTED_COLUMNS (in that order) and
    rows with all-NaN removed.

    Raises:
        ValueError if no matching header is found.
    """
    path = Path(path)
    last_error: Exception | None = None

    for skip in range(max_skip_rows):
        try:
            df = pd.read_csv(path, skiprows=skip)
        except ParserError as e:
            last_error = e
            continue

        if set(EXPECTED_COLUMNS).issubset(df.columns):
            # Keep a stable column order
            df = df[EXPECTED_COLUMNS]
            df = df.dropna()
            return df

    raise ValueError(
        f"Expected columns {EXPECTED_COLUMNS} not found in the CSV file "
        f"after checking the first {max_skip_rows} header positions."
    ) from last_error
