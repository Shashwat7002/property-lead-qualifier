"""Optional, read-only educational ML endpoints, isolated from lead scoring."""

import json
import threading
from functools import lru_cache
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request


ml_blueprint = Blueprint("ml_lab", __name__)
_TRAINING_LOCK = threading.Lock()
_DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data/ml/AmesHousing.tsv"
_SETUP = (
    "Set up the lab with: python3 -m venv .venv; "
    ".venv/bin/python -m pip install -r requirements-ml.txt; "
    ".venv/bin/python scripts/train_property_ml.py --download. "
    "Then start Sprint with .venv/bin/python app.py."
)


@lru_cache(maxsize=2)
def _train_cached(path, modified_ns, size):
    # Import only on demand: the existing lead workspace needs no ML packages.
    from ml_lab.core import train_experiment

    return train_experiment(path)


def get_experiment():
    path = Path(current_app.config.get("ML_DATA_PATH", _DEFAULT_DATA)).resolve()
    stat = path.stat()
    # Two simultaneous first visits must not both train the same experiment.
    with _TRAINING_LOCK:
        return _train_cached(str(path), stat.st_mtime_ns, stat.st_size)


def _unavailable(error):
    current_app.logger.warning("ML lab unavailable: %s", type(error).__name__)
    return jsonify(error="The educational model is not ready. " + _SETUP), 503


@ml_blueprint.get("/ml-lab")
def lab_page():
    return render_template("ml_lab.html")


@ml_blueprint.get("/api/ml/report")
def lab_report():
    try:
        return jsonify(get_experiment().report)
    except (OSError, ImportError, ValueError) as error:
        return _unavailable(error)


@ml_blueprint.get("/api/ml/report/download")
def lab_report_download():
    try:
        payload = json.dumps(get_experiment().report, indent=2, allow_nan=False)
    except (OSError, ImportError, ValueError) as error:
        return _unavailable(error)
    return Response(
        payload + "\n",
        mimetype="application/json",
        headers={"Content-Disposition": 'attachment; filename="sprint-ml-report.json"'},
    )


@ml_blueprint.post("/api/ml/predict")
def lab_predict():
    if request.content_length and request.content_length > 16384:
        return jsonify(error="The example is too large."), 413
    if not request.is_json:
        return jsonify(error="Send a JSON object containing the home features."), 400
    values = request.get_json(silent=True)
    if not isinstance(values, dict):
        return jsonify(error="Send a JSON object containing the home features."), 400
    try:
        experiment = get_experiment()
    except (OSError, ImportError, ValueError) as error:
        return _unavailable(error)
    try:
        return jsonify(experiment.predict(values))
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error)), 400
