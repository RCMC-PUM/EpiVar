import os
import sys
import shutil
import requests

from pandas.errors import ParserError
import pandas as pd
from pathlib import Path


def delete_temp_dir(path="temp/"):
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Deleted directory: {path}")
    else:
        print(f"Directory does not exist: {path}")


def download_file(url, save_dir="temp/", filename=None):
    # Create the directory if it doesn't exist
    os.makedirs(save_dir, exist_ok=True)

    if filename is None:
        filename = url.split("/")[-1] or "downloaded_file"

    # Full path for saving the file
    file_path = os.path.join(save_dir, filename)

    # Download the file
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error on bad status

        # Write to file
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"File downloaded and saved to: {file_path}")
        return Path(file_path)

    except requests.RequestException as e:
        print(f"Failed to download file: {e}")
        sys.exit(-1)


def parse_asct_table(path):
    expected_columns = {"AS/1", "AS/1/ID", "CT/1", "CT/1/ID"}
    max_skip_rows = 25

    for skip in range(max_skip_rows):
        try:
            asct_table = pd.read_csv(path, skiprows=skip)
            if expected_columns.issubset(set(asct_table.columns)):
                asct_table = asct_table[list(expected_columns)]
                break
        except ParserError:
            pass
    else:
        raise ValueError(
            "Expected columns not found in the CSV file after checking multiple headers."
        )

    asct_table = asct_table.dropna()
    return asct_table.iterrows()
