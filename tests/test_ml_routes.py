"""Boundary tests keep the optional learning lab separate from live scoring."""

import json

import pytest
from flask import Flask

import ml_lab.routes as routes


class ExampleExperiment:
    report = {"dataset": {"name": "Test fixture"}, "models": []}

    def predict(self, values):
        if "unknown" in values:
            raise ValueError("Unknown feature: unknown")
        return {"prediction": 100000, "lower": 75000, "upper": 125000}


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(routes.ml_blueprint)
    monkeypatch.setattr(routes, "get_experiment", lambda: ExampleExperiment())
    return app.test_client()


def test_report_and_download_contain_same_results(client):
    report = client.get("/api/ml/report")
    download = client.get("/api/ml/report/download")
    assert report.status_code == download.status_code == 200
    assert report.json == json.loads(download.data)
    assert "attachment" in download.headers["Content-Disposition"]


@pytest.mark.parametrize("payload", [[], None, "string", 4])
def test_predict_rejects_non_object(client, payload):
    response = client.post("/api/ml/predict", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.json


def test_predict_rejects_malformed_and_oversized_request(client):
    assert client.post("/api/ml/predict", data="oops").status_code == 400
    assert client.post("/api/ml/predict", data="{", content_type="application/json").status_code == 400
    assert client.post("/api/ml/predict", json={"x": "a" * 16385}).status_code == 413


def test_prediction_validation_errors_are_actionable(client):
    response = client.post("/api/ml/predict", json={"unknown": 1})
    assert response.status_code == 400
    assert response.json == {"error": "Unknown feature: unknown"}
    assert client.post("/api/ml/predict", json={"living_area": 1500}).status_code == 200


@pytest.mark.parametrize("error", [FileNotFoundError(), ImportError(), ValueError("bad data")])
def test_setup_failure_is_recoverable(client, monkeypatch, error):
    def unavailable():
        raise error
    monkeypatch.setattr(routes, "get_experiment", unavailable)
    for method, path, kwargs in [
        (client.get, "/api/ml/report", {}),
        (client.get, "/api/ml/report/download", {}),
        (client.post, "/api/ml/predict", {"json": {"living_area": 1500}}),
    ]:
        response = method(path, **kwargs)
        assert response.status_code == 503
        assert "requirements-ml.txt" in response.json["error"]
