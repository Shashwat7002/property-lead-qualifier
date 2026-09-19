"""Statistical invariants: no leakage, honest missingness, and real uncertainty."""

import csv
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
import pytest

from ml_lab.core import (
    FEATURES, Dataset, bootstrap_mean_ci, conformal_half_width,
    load_dataset, make_pipeline, split_dataset, train_experiment, wilson_interval,
)
from ml_lab import data as data_download


def write_fixture(path: Path, *, duplicate_pids: bool = False, missing_target: bool = False):
    rng = np.random.default_rng(123)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["PID", "SalePrice"] + [f.column for f in FEATURES], delimiter="\t")
        writer.writeheader()
        for i in range(150):
            area = float(rng.integers(650, 3500))
            quality = int(rng.integers(2, 10))
            row = {
                "PID": str(i // 2 if duplicate_pids else i),
                "SalePrice": 45000 + 70 * area + 12000 * quality + float(rng.normal(0, 14000)),
                "Lot Frontage": "" if i % 5 == 0 else float(rng.integers(30, 120)),
                "Gr Liv Area": area, "Lot Area": float(rng.integers(3000, 25000)),
                "Overall Qual": quality, "Year Built": int(rng.integers(1900, 2011)),
                "Full Bath": int(rng.integers(1, 4)), "Bedroom AbvGr": int(rng.integers(1, 6)),
                "Garage Area": "NA" if i == 2 else (0 if i % 7 == 0 else 450),
            }
            if missing_target and i == 3:
                row["SalePrice"] = "NA"
            writer.writerow(row)
    return path


@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    path = write_fixture(tmp_path_factory.mktemp("ames-fixture") / "ames.tsv")
    return train_experiment(path, bootstrap_samples=200)


def test_parser_distinguishes_unknown_from_observed_zero(tmp_path):
    data = load_dataset(write_fixture(tmp_path / "ames.tsv", missing_target=True))
    assert data.raw_rows == 150
    assert data.excluded_missing_targets == 1
    assert len(data.y) == 149
    assert np.isnan(data.X[0, 0])  # Actual blank frontage.
    assert data.X[0, 7] == 0  # A known absence of a garage.
    assert np.isnan(data.X[2, 7])  # Unknown garage area, not a zero.
    assert np.isfinite(data.y).all()


def test_split_is_disjoint_complete_and_reproducible(experiment):
    split = experiment.split_indices
    assert [len(split[k]) for k in ("train", "calibration", "test")] == [90, 30, 30]
    concatenated = np.concatenate(list(split.values()))
    assert len(np.unique(concatenated)) == len(experiment.dataset.y)
    assert sorted(concatenated) == list(range(150))
    again = split_dataset(experiment.dataset)
    for key in split:
        np.testing.assert_array_equal(split[key], again[key])


def test_repeated_properties_cannot_cross_partitions(tmp_path):
    data = load_dataset(write_fixture(tmp_path / "repeated.tsv", duplicate_pids=True))
    split = split_dataset(data)
    groups = {key: set(data.property_ids[idx]) for key, idx in split.items()}
    assert not groups["train"] & groups["calibration"]
    assert not groups["train"] & groups["test"]
    assert not groups["calibration"] & groups["test"]
    assert set.union(*groups.values()) == set(data.property_ids)


def test_medians_and_scaler_are_learned_only_from_training(experiment):
    X = experiment.dataset.X
    train = experiment.split_indices["train"]
    expected = np.nanmedian(X[train], axis=0)
    np.testing.assert_allclose(experiment.model.named_steps["imputer"].statistics_, expected)
    imputed_train = experiment.model.named_steps["imputer"].transform(X[train])
    np.testing.assert_allclose(experiment.model.named_steps["scaler"].mean_, imputed_train.mean(axis=0))


def test_heldout_mutations_do_not_change_trained_transform_or_model(experiment):
    data = experiment.dataset
    train = experiment.split_indices["train"]
    mutated = data.X.copy()
    heldout = np.concatenate([experiment.split_indices["calibration"], experiment.split_indices["test"]])
    mutated[heldout] = 1e9
    labels = data.y.copy()
    labels[heldout] = 1e12
    refit = make_pipeline().fit(mutated[train], labels[train])
    np.testing.assert_allclose(refit.named_steps["imputer"].statistics_, experiment.model.named_steps["imputer"].statistics_)
    np.testing.assert_allclose(refit.named_steps["ridge"].coef_, experiment.model.named_steps["ridge"].coef_)


def test_empty_training_column_preserves_feature_positions():
    X = np.array([[np.nan, 1], [np.nan, 2], [np.nan, 3]], dtype=float)
    pipeline = make_pipeline().fit(X, np.array([10, 20, 30]))
    imputed = pipeline.named_steps["imputer"].transform([[4, 5]])
    assert imputed.shape == (1, 3)  # Two original features plus one missing flag.
    assert imputed[0, 0] == 4
    assert imputed[0, 1] == 5
    assert imputed[0, 2] == 0


def test_conformal_uses_finite_sample_order_statistic():
    residuals = np.arange(1, 587, dtype=float)
    width, rank = conformal_half_width(residuals)
    assert rank == math.ceil(587 * 0.9) == 529
    assert width == 529
    assert width != np.quantile(residuals, 0.9)
    with pytest.raises(ValueError, match="Too few"):
        conformal_half_width(np.array([1, 2, 3]))


def test_interval_width_comes_only_from_calibration(experiment):
    cal = experiment.split_indices["calibration"]
    residuals = np.abs(experiment.dataset.y[cal] - experiment.model.predict(experiment.dataset.X[cal]))
    expected, rank = conformal_half_width(residuals)
    assert experiment.half_width == expected
    assert experiment.report["interval"]["calibration_rank"] == rank


def test_bootstrap_reproducible_and_preserves_paired_differences():
    errors = np.array([2.0, 3.0, 6.0, 15.0])
    first = bootstrap_mean_ci(errors, samples=500)
    assert first == bootstrap_mean_ci(errors, samples=500)
    assert first[0] < errors.mean() < first[1]
    baseline_errors = errors + 5
    assert bootstrap_mean_ci(baseline_errors - errors, samples=500) == [5, 5]


def test_wilson_interval_is_bounded_and_non_degenerate_at_extremes():
    low, high = wilson_interval(90, 100)
    assert 0 < low < 0.9 < high < 1
    low, high = wilson_interval(0, 100)
    assert low == 0 and 0 < high < 1
    low, high = wilson_interval(100, 100)
    assert 0 < low < 1 and high == 1


@pytest.mark.parametrize("value", [True, "1250", "abc", float("nan"), float("inf"), 10 ** 1000, [], {}])
def test_prediction_rejects_invalid_numeric_types(experiment, value):
    with pytest.raises(ValueError, match="finite number"):
        experiment.predict({"living_area": value})


@pytest.mark.parametrize("values", [{}, {"living_area": None}, {"living_area": " "}, {"living_area": 99}, {"year_built": 2026}, {"bedrooms": 2.5}, {"unexpected": 123}])
def test_prediction_rejects_empty_out_of_bounds_or_extra_inputs(experiment, values):
    with pytest.raises(ValueError):
        experiment.predict(values)


def test_prediction_exposes_imputation_and_preserves_zero(experiment):
    values = {feature["key"]: feature["default"] for feature in experiment.report["features"]}
    values.update({"lot_frontage": None, "garage_area": 0})
    result = experiment.predict(values)
    assert result["lower"] < result["prediction"] < result["upper"]
    assert result["interval_level"] == 0.90
    assert result["imputed_fields"] == [{"key": "lot_frontage", "label": "Lot frontage", "value": experiment.report["features"][0]["train_median"]}]
    assert result["upper"] - result["prediction"] == pytest.approx(experiment.half_width)


def test_end_to_end_report_is_finite_and_comparisons_share_cohorts(experiment):
    json.dumps(experiment.report, allow_nan=False)
    report = experiment.report
    assert report["dataset"]["missing_cells"] == 31
    assert report["dataset"]["canonical_source_verified"] is False
    assert report["models"][0]["test_rows"] == report["models"][1]["test_rows"] == 30
    comparison = report["complete_case_comparison"]
    assert {model["test_rows"] for model in comparison["models"]} == {comparison["test_rows"]}
    assert comparison["discarded_train_rows"] > 0
    assert comparison["test_rows"] + comparison["excluded_test_rows"] == 30
    assert report["models"][1]["mae"] < report["models"][0]["mae"]
    assert report["interval"]["coverage"] == report["interval"]["covered"] / 30
    assert len(experiment.prediction_rows()) == 30


def test_download_rejects_changed_content_without_overwriting_existing_file(tmp_path, monkeypatch):
    path = tmp_path / "dataset.tsv"
    path.write_bytes(b"previous trusted file")
    monkeypatch.setattr(data_download, "urlopen", lambda *args, **kwargs: io.BytesIO(b"unexpected data"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        data_download.download_ames(path, force=True)
    assert path.read_bytes() == b"previous trusted file"
    assert list(tmp_path.iterdir()) == [path]


def test_download_checks_existing_file_and_never_fetches_silently(tmp_path, monkeypatch):
    path = tmp_path / "dataset.tsv"
    path.write_bytes(b"local altered file")

    def unexpected_network(*args, **kwargs):
        pytest.fail("The downloader must not fetch without explicit replacement.")

    monkeypatch.setattr(data_download, "urlopen", unexpected_network)
    with pytest.raises(ValueError, match="Use --force"):
        data_download.download_ames(path)
    assert path.read_bytes() == b"local altered file"


def test_download_writes_only_verified_content_and_reuses_it(tmp_path, monkeypatch):
    content = b"test-only known reference content\n"
    path = tmp_path / "nested" / "dataset.tsv"
    monkeypatch.setattr(data_download, "SOURCE_SHA256", hashlib.sha256(content).hexdigest())
    calls = []

    def fetch(*args, **kwargs):
        calls.append(True)
        return io.BytesIO(content)

    monkeypatch.setattr(data_download, "urlopen", fetch)
    assert data_download.download_ames(path) == path
    assert path.read_bytes() == content
    assert data_download.download_ames(path) == path
    assert len(calls) == 1
    assert list(path.parent.iterdir()) == [path]
