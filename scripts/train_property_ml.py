#!/usr/bin/env python3
"""Train and evaluate the reproducible, historical Ames Housing learning lab."""

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_lab.core import train_experiment
from ml_lab.data import download_ames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/ml/AmesHousing.tsv")
    parser.add_argument("--download", action="store_true", help="Download and checksum-verify Ames data if needed.")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/ml_report.json")
    parser.add_argument("--predictions", type=Path, help="Optional CSV path for held-out predictions.")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args()
    try:
        if args.download:
            download_ames(args.data)
        experiment = train_experiment(args.data, bootstrap_samples=args.bootstrap_samples)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Experiment failed: {exc}\n")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(experiment.report, indent=2, allow_nan=False) + "\n")
    if args.predictions:
        rows = experiment.prediction_rows()
        args.predictions.parent.mkdir(parents=True, exist_ok=True)
        with args.predictions.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    report = experiment.report
    print(f"Ames Housing: {report['dataset']['rows']} rows; split {report['split']['train']}/{report['split']['calibration']}/{report['split']['test']}")
    for model in report["models"]:
        low, high = model["mae_ci"]
        print(f"{model['label']}: MAE ${model['mae']:,.0f}, 95% CI [${low:,.0f}, ${high:,.0f}], R² {model['r2']:.3f}")
    interval = report["interval"]
    print(f"90% prediction interval: ±${interval['half_width']:,.0f}; test coverage {interval['coverage']:.1%} ({interval['covered']}/{interval['total']})")
    print(f"Report: {args.report}")
    print("Educational historical results; not a current-market valuation or lead score.")


if __name__ == "__main__":
    main()
