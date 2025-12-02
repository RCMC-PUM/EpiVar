import os
import requests
from pathlib import Path
from pybedtools import BedTool

from django.core.exceptions import ValidationError


def _download_file(url, save_dir=None, filename=None) -> Path | None:
    """
    Downloads a file from a URL and saves it to a specified directory.

    Args:
        url (str): The URL to download the file from.
        save_dir (str): The directory to save the downloaded file.
        filename (str) [OPTIONAL]: The name to save the file as. If not provided, the name is extracted from the URL.

    Returns:
        Path: Full path to the saved file.
    """
    if save_dir is None:
        raise Exception("Output directory (save_dir) has to be provided.")

    if filename is None:
        filename = url.split("/")[-1]

    # Full path for saving the file
    file_path = os.path.join(save_dir, filename)

    # Download the file
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an error on bad status

    # Write to file
    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return Path(file_path)


def _validate_against_chrom_sizes(bed_file: str, chrom_size_file: str):
    bed_file = BedTool(bed_file)
    chrom_size_file = BedTool(chrom_size_file)

    intersection = bed_file.intersect(chrom_size_file).count()
    if intersection < bed_file.count():
        raise ValidationError(f"Records within BED file are not subset of declared reference genome.")
