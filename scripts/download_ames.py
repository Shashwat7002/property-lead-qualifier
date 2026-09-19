#!/usr/bin/env python3
"""Fetch the original Ames teaching dataset; raw data is not checked into git."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_lab.data import SOURCE_SHA256, download_ames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/ml/AmesHousing.tsv")
    parser.add_argument("--force", action="store_true", help="Explicitly replace an existing differing file.")
    args = parser.parse_args()
    try:
        path = download_ames(args.output, force=args.force)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Download failed: {exc}\n")
    print(f"Verified Ames Housing: {path}\nSHA-256: {SOURCE_SHA256}")


if __name__ == "__main__":
    main()
