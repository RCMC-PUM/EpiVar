import os
import sys

import shutil
import requests
from pathlib import Path


def delete_temp_dir(path="temp/"):
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Deleted directory: {path}")
    else:
        print(f"Directory does not exist: {path}")


def download_file(url, save_dir="temp/", filename=None) -> Path | None:
    """
    Downloads a file from a URL and saves it to a specified directory.

    Args:
        url (str): The URL to download the file from.
        save_dir (str): The directory to save the downloaded file.
        filename (str, optional): The name to save the file as. If not provided, the name is extracted from the URL.

    Returns:
        Path: Full path to the saved file.
    """

    # Create the directory if it doesn't exist
    os.makedirs(save_dir, exist_ok=True)

    if filename is None:
        filename = url.split("/")[-1] or "downloaded_file"

    # Full path for saving the file
    file_path = os.path.join(save_dir, filename)

    # Download the file
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an error on bad status

    # Write to file
    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"File downloaded and saved to: {file_path}")
    return Path(file_path)
