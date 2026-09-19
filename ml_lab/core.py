"""A small regression lab with honest missing-data and uncertainty evaluation.

There are three disjoint partitions. Only training rows fit transformations and
models, calibration rows set the conformal interval, and test rows evaluate both.
The test set does not select features, hyperparameters, or examples by accuracy.
"""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import SOURCE_SHA256, SOURCE_URL

SEED = 42
INTERVAL_LEVEL = 0.90
RIDGE_ALPHA = 10.0  # Predeclared, deliberately not selected using the test set.
SOURCE_PAPER = "https://jse.amstat.org/v19n3/decock.pdf"
MISSING_TOKENS = {"", "NA", "N/A", "NULL", "NAN"}


@dataclass(frozen=True)
class Feature:
    key: str
    column: str
    label: str
    unit: str
    minimum: float
    maximum: float
    integer: bool = False


# Bounds are fixed plausible input limits, not learned from the held-out set.
FEATURES = (
    Feature("lot_frontage", "Lot Frontage", "Lot frontage", "ft", 0, 500),
    Feature("living_area", "Gr Liv Area", "Above-ground living area", "sq ft", 100, 10000),
    Feature("lot_area", "Lot Area", "Lot area", "sq ft", 100, 500000),
    Feature("overall_quality", "Overall Qual", "Overall quality", "1–10", 1, 10, True),
    Feature("year_built", "Year Built", "Year built", "year", 1800, 2010, True),
    Feature("full_baths", "Full Bath", "Full bathrooms", "count", 0, 6, True),
    Feature("bedrooms", "Bedroom AbvGr", "Above-ground bedrooms", "count", 0, 12, True),
    Feature("garage_area", "Garage Area", "Garage area", "sq ft", 0, 5000),
)


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    property_ids: np.ndarray
    source_rows: np.ndarray
    raw_rows: int
    excluded_missing_targets: int
    sha256: str


def _parse_numeric(value: str | None, column: str, line: int) -> float:
    token = "" if value is None else value.strip()
    if token.upper() in MISSING_TOKENS:
        return float("nan")
    try:
        number = float(token)
    except ValueError as exc:
        raise ValueError(f"Invalid number in {column}, source line {line}.") from exc
    if not math.isfinite(number):
        raise ValueError(f"Non-finite number in {column}, source line {line}.")
    return number


def load_dataset(data_path: str | Path) -> Dataset:
    """Read numeric blanks/NA as missing; never invent a missing outcome."""
    path = Path(data_path)
    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    features, targets, property_ids, source_rows = [], [], [], []
    raw_rows = excluded = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {feature.column for feature in FEATURES} | {"PID", "SalePrice"}
        absent = required - set(reader.fieldnames or [])
        if absent:
            raise ValueError(f"Dataset is missing columns: {', '.join(sorted(absent))}.")
        for line, row in enumerate(reader, start=2):
            raw_rows += 1
            target = _parse_numeric(row["SalePrice"], "SalePrice", line)
            if math.isnan(target):
                excluded += 1
                continue
            if target <= 0:
                raise ValueError(f"SalePrice must be positive, source line {line}.")
            property_id = (row["PID"] or "").strip()
            if not property_id:
                raise ValueError(f"PID is required to check property overlap, source line {line}.")
            features.append([_parse_numeric(row[f.column], f.column, line) for f in FEATURES])
            targets.append(target)
            property_ids.append(property_id)
            source_rows.append(line - 1)
    if len(targets) < 50:
        raise ValueError("At least 50 labeled rows are required for this experiment.")
    return Dataset(
        X=np.asarray(features, dtype=float), y=np.asarray(targets, dtype=float),
        property_ids=np.asarray(property_ids), source_rows=np.asarray(source_rows),
        raw_rows=raw_rows, excluded_missing_targets=excluded, sha256=sha256,
    )


def split_dataset(dataset: Dataset, seed: int = SEED) -> dict[str, np.ndarray]:
    """Split 60/20/20, grouping repeated PIDs so a property cannot leak."""
    indices = np.arange(len(dataset.y))
    if len(np.unique(dataset.property_ids)) == len(indices):
        train, remaining = train_test_split(indices, train_size=0.60, random_state=seed)
        calibration, test = train_test_split(remaining, test_size=0.50, random_state=seed)
    else:
        if len(np.unique(dataset.property_ids)) < 10:
            raise ValueError("At least 10 distinct properties are required for grouped splitting.")
        splitter = GroupShuffleSplit(n_splits=1, train_size=0.60, random_state=seed)
        train, remaining = next(splitter.split(indices, groups=dataset.property_ids))
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=seed)
        calibration_rel, test_rel = next(
            splitter.split(remaining, groups=dataset.property_ids[remaining])
        )
        calibration, test = remaining[calibration_rel], remaining[test_rel]
    return {"train": train, "calibration": calibration, "test": test}


def make_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=RIDGE_ALPHA)),
    ])


def bootstrap_mean_ci(values: np.ndarray, samples: int = 2000, seed: int = SEED) -> list[float]:
    """Percentile CI conditional on the fitted model and held-out cohort.

    Passing paired per-row error differences preserves the pairing. Models and
    transformations are intentionally not refitted inside this test bootstrap.
    """
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Bootstrap values must be a nonempty finite vector.")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 100 <= samples <= 50000:
        raise ValueError("Bootstrap samples must be an integer between 100 and 50000.")
    rng = np.random.default_rng(seed)
    means = np.empty(samples)
    # Small batches keep memory bounded even for a larger replacement dataset.
    for start in range(0, samples, 100):
        count = min(100, samples - start)
        indices = rng.integers(0, len(values), size=(count, len(values)))
        means[start:start + count] = values[indices].mean(axis=1)
    return [float(v) for v in np.quantile(means, [0.025, 0.975])]


def conformal_half_width(residuals: np.ndarray, level: float = INTERVAL_LEVEL) -> tuple[float, int]:
    """Finite-sample split-conformal order statistic, with one-based rank."""
    residuals = np.asarray(residuals, dtype=float)
    if residuals.ndim != 1 or not len(residuals) or not np.isfinite(residuals).all():
        raise ValueError("Calibration residuals must be a nonempty finite vector.")
    if (residuals < 0).any() or not 0 < level < 1:
        raise ValueError("Residuals must be nonnegative and interval level between zero and one.")
    rank = math.ceil((len(residuals) + 1) * level)
    if rank > len(residuals):
        raise ValueError("Too few calibration rows for a finite interval at this coverage level.")
    return float(np.sort(residuals)[rank - 1]), rank


def wilson_interval(covered: int, total: int) -> list[float]:
    """Wilson 95% binomial interval for empirical interval coverage."""
    if total < 1 or not 0 <= covered <= total:
        raise ValueError("Coverage counts are invalid.")
    z = 1.959963984540054
    p = covered / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [0.0 if covered == 0 else max(0.0, center - half_width),
            1.0 if covered == total else min(1.0, center + half_width)]


def _metrics(key: str, label: str, actual: np.ndarray, predicted: np.ndarray, samples: int) -> dict:
    return {
        "key": key, "label": label, "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
        "mae_ci": bootstrap_mean_ci(np.abs(actual - predicted), samples), "test_rows": len(actual),
    }


@dataclass
class Experiment:
    report: dict[str, Any]
    model: Pipeline
    dataset: Dataset
    split_indices: dict[str, np.ndarray]
    half_width: float

    def predict(self, values: dict) -> dict:
        """Validate a hypothetical historical Ames home and expose imputation."""
        if not isinstance(values, dict):
            raise ValueError("Prediction inputs must be a JSON object.")
        unknown = set(values) - {f.key for f in FEATURES}
        if unknown:
            raise ValueError("Unknown input fields: " + ", ".join(sorted(str(k) for k in unknown)) + ".")
        row, imputed_fields, warnings = [], [], []
        indicators = set(self.model.named_steps["imputer"].indicator_.features_)
        for index, feature in enumerate(FEATURES):
            value = values.get(feature.key)
            missing = value is None or (isinstance(value, str) and not value.strip())
            metadata = self.report["features"][index]
            if missing:
                row.append(float("nan"))
                imputed_fields.append({"key": feature.key, "label": feature.label, "value": metadata["train_median"]})
                if index not in indicators:
                    warnings.append(f"{feature.label} had no missing training values; this missing-input pattern was not learned.")
                continue
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"{feature.label} must be a finite number, or blank if unknown.")
            try:
                value = float(value)
            except (OverflowError, ValueError) as exc:
                raise ValueError(f"{feature.label} must be a finite number, or blank if unknown.") from exc
            if not math.isfinite(value):
                raise ValueError(f"{feature.label} must be a finite number, or blank if unknown.")
            if not feature.minimum <= value <= feature.maximum:
                raise ValueError(f"{feature.label} must be between {feature.minimum:g} and {feature.maximum:g}.")
            if feature.integer and not value.is_integer():
                raise ValueError(f"{feature.label} must be a whole number.")
            if metadata["train_min"] is not None and not metadata["train_min"] <= value <= metadata["train_max"]:
                warnings.append(f"{feature.label} is outside the observed training range.")
            row.append(value)
        if len(imputed_fields) == len(FEATURES):
            raise ValueError("Enter at least one observed property feature.")
        prediction = float(self.model.predict(np.asarray([row]))[0])
        # Do not silently clip: these are symmetric conformal intervals, and the
        # educational linear model can extrapolate to implausible dollar values.
        if prediction < 0 or prediction - self.half_width < 0:
            warnings.append("The linear model produced a negative price or interval endpoint; treat this as a model limitation.")
        if len(imputed_fields) > 2:
            warnings.append("Several features are unknown; the overall coverage target does not guarantee coverage for this input pattern.")
        return {
            "prediction": prediction, "lower": prediction - self.half_width,
            "upper": prediction + self.half_width, "interval_level": INTERVAL_LEVEL,
            "imputed_fields": imputed_fields, "warnings": warnings,
        }

    def prediction_rows(self) -> list[dict]:
        """Export only held-out predictions with anonymous source-row references."""
        test = self.split_indices["test"]
        predicted = self.model.predict(self.dataset.X[test])
        return [{
            "source_row": int(self.dataset.source_rows[index]), "actual": float(actual),
            "predicted": float(estimate), "lower": float(estimate - self.half_width),
            "upper": float(estimate + self.half_width), "absolute_error": float(abs(actual - estimate)),
            "has_missing_features": bool(np.isnan(self.dataset.X[index]).any()),
        } for index, actual, estimate in zip(test, self.dataset.y[test], predicted)]


def train_experiment(data_path: str | Path, bootstrap_samples: int = 2000) -> Experiment:
    dataset = load_dataset(data_path)
    X, y = dataset.X, dataset.y
    split = split_dataset(dataset)
    train, calibration, test = (split[key] for key in ("train", "calibration", "test"))
    if len(calibration) < 9 or len(test) < 10:
        raise ValueError("The split needs at least 9 calibration and 10 test rows.")
    model = make_pipeline().fit(X[train], y[train])
    baseline = DummyRegressor(strategy="median").fit(X[train], y[train])
    predicted, baseline_predicted = model.predict(X[test]), baseline.predict(X[test])
    residuals = np.abs(y[calibration] - model.predict(X[calibration]))
    half_width, rank = conformal_half_width(residuals)
    errors = np.abs(y[test] - predicted)
    covered = int((errors <= half_width).sum())
    missing = np.isnan(X)
    imputer = model.named_steps["imputer"]
    features = []
    for index, feature in enumerate(FEATURES):
        observed_train = X[train, index][~np.isnan(X[train, index])]
        median = float(imputer.statistics_[index])
        features.append({
            "key": feature.key, "label": feature.label, "column": feature.column, "unit": feature.unit,
            "min": feature.minimum, "max": feature.maximum, "integer": feature.integer,
            "default": median, "train_median": median, "missing_count": int(missing[:, index].sum()),
            "missing_pct": float(missing[:, index].mean() * 100),
            "train_missing_count": int(missing[train, index].sum()),
            "train_min": float(observed_train.min()) if len(observed_train) else None,
            "train_max": float(observed_train.max()) if len(observed_train) else None,
            "empty_training_feature": not bool(len(observed_train)),
        })
    examples = []
    # Include one missing-input case first, then the first other test rows. This
    # selection depends only on missingness/order, never on prediction quality.
    missing_test = np.flatnonzero(missing[test].any(axis=1))
    example_positions = ([int(missing_test[0])] if len(missing_test) else [])
    example_positions.extend(i for i in range(len(test)) if i not in example_positions)
    for position in example_positions[:6]:
        index = test[position]
        estimate = float(predicted[position])
        examples.append({
            "id": f"ames-{int(dataset.source_rows[index])}",
            "values": {f.key: None if math.isnan(X[index, j]) else float(X[index, j]) for j, f in enumerate(FEATURES)},
            "actual": float(y[index]), "predicted": estimate,
            "lower": estimate - half_width, "upper": estimate + half_width,
        })
    repeated_properties = len(dataset.property_ids) - len(np.unique(dataset.property_ids))
    property_sets = [set(dataset.property_ids[split[key]]) for key in ("train", "calibration", "test")]
    property_overlap = len(property_sets[0] & property_sets[1] | property_sets[0] & property_sets[2] | property_sets[1] & property_sets[2])
    if property_overlap:
        raise ValueError("Property identity overlap detected between dataset partitions.")
    coefficient_names = [(f.key, f.label, False) for f in FEATURES]
    coefficient_names += [
        (FEATURES[i].key + "_missing", FEATURES[i].label + " missing", True)
        for i in imputer.indicator_.features_
    ]
    report = {
        "schema_version": 1,
        "dataset": {
            "name": "Ames Housing", "rows": len(y), "raw_rows": dataset.raw_rows,
            "source_url": SOURCE_URL, "paper_url": SOURCE_PAPER, "sha256": dataset.sha256,
            "canonical_sha256": SOURCE_SHA256, "canonical_source_verified": dataset.sha256 == SOURCE_SHA256,
            "attribution": "Dean De Cock (2011), Ames, Iowa: Alternative to the Boston Housing Data as an End of Semester Regression Project, Journal of Statistics Education 19(3).",
            "period": "2006–2010", "location": "Ames, Iowa", "currency": "historical USD",
            "excluded_missing_targets": dataset.excluded_missing_targets,
            "missing_rows": int(missing.any(axis=1).sum()), "missing_cells": int(missing.sum()),
            "unique_properties": int(len(np.unique(dataset.property_ids))),
            "duplicate_pid_rows": int(repeated_properties),
        },
        "split": {
            "train": len(train), "calibration": len(calibration), "test": len(test), "seed": SEED,
            "strategy": "grouped by PID" if repeated_properties else "random rows; all PIDs unique",
            "property_overlap": property_overlap,
            "index_sha256": {key: hashlib.sha256(indices.astype("<i8").tobytes()).hexdigest() for key, indices in split.items()},
        },
        "features": features,
        "models": [
            _metrics("median_baseline", "Training-median baseline", y[test], baseline_predicted, bootstrap_samples),
            _metrics("ridge", "Ridge + median imputation", y[test], predicted, bootstrap_samples),
        ],
        "paired_improvement": {
            "label": "Baseline MAE minus Ridge MAE (positive favors Ridge)",
            "value": float((np.abs(y[test] - baseline_predicted) - errors).mean()),
            "ci": bootstrap_mean_ci(np.abs(y[test] - baseline_predicted) - errors, bootstrap_samples),
        },
        "interval": {
            "level": INTERVAL_LEVEL, "half_width": half_width, "coverage": covered / len(test),
            "covered": covered, "total": len(test), "coverage_ci": wilson_interval(covered, len(test)),
            "calibration_rows": len(calibration), "calibration_rank": rank,
            "method": "Split conformal; ceil((n_calibration + 1) × 0.90) absolute-residual order statistic",
        },
        "bootstrap": {"samples": bootstrap_samples, "seed": SEED, "level": 0.95, "method": "paired row-resampled percentile bootstrap; fitted models held fixed"},
        "model_config": {"algorithm": "Ridge", "alpha": RIDGE_ALPHA, "imputation": "training median + missingness indicators", "scaling": "training mean and standard deviation", "target": "SalePrice in historical dollars"},
        "software": {"numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "examples": examples,
        "coefficients": [
            {"key": key, "label": label, "coefficient": float(value), "is_missing_indicator": indicator}
            for (key, label, indicator), value in zip(coefficient_names, model.named_steps["ridge"].coef_)
        ],
        "coefficient_units": "Historical USD per one training-set standard deviation of the transformed feature, with other features held fixed. Missing indicators are scaled too. Associations, not causal effects.",
        "methodology": [
            "A fixed seed partitions labeled rows 60% training, 20% interval calibration, 20% final testing. Repeated property IDs are grouped if present.",
            "Numeric blanks and NA are unknown. Observed zero garage area means no garage and stays zero; unknown garage area stays missing until imputation.",
            "Only training rows determine feature medians, missingness indicators, scaling, and model weights. Calibration rows set interval width; test rows report performance.",
            "Eight features and Ridge alpha=10 are predeclared. No test-driven feature selection, outlier removal, or hyperparameter tuning is performed.",
            "The baseline always predicts the training-set median sale price. Both main models are evaluated on every test row.",
            "A 95% bootstrap confidence interval describes uncertainty in average test error for a fixed trained model. A 90% conformal prediction interval describes a new outcome; these are different quantities.",
        ],
        "limitations": [
            "This is a historical Ames, Iowa learning exercise. It has not been validated for current Georgia prices or lead prioritization.",
            "Bootstrap MAE intervals condition on these trained models and this split; they omit model-training and split variability.",
            "Split-conformal coverage assumes exchangeable calibration and future examples. Its 90% target is marginal over examples, not a promise for each home or subgroup.",
            "Random splitting mixes sale years and neighborhoods; a future-year or new-market deployment needs fresh temporal and geographic validation.",
            "Median imputation preserves rows but does not explain why values are missing. Missingness may be informative, and newly missing fields may lack a learned indicator.",
            "Linear predictions and symmetric intervals can be implausible on unusual inputs. Coefficients are associations, not causal effects.",
        ],
        "sources": [
            {"title": "De Cock (2011): Ames Housing dataset and teaching paper", "url": SOURCE_PAPER},
            {"title": "Original Ames Housing data", "url": SOURCE_URL},
            {"title": "scikit-learn: avoiding data leakage", "url": "https://scikit-learn.org/stable/common_pitfalls.html#data-leakage"},
            {"title": "Angelopoulos and Bates: A Gentle Introduction to Conformal Prediction", "url": "https://arxiv.org/abs/2107.07511"},
        ],
    }
    # A complete-case model cannot evaluate incomplete rows without imputation.
    # Compare it with the primary model on exactly the same complete test rows.
    complete_train = train[~missing[train].any(axis=1)]
    complete_test_positions = np.flatnonzero(~missing[test].any(axis=1))
    if len(complete_train) >= 20 and len(complete_test_positions) >= 10:
        complete_test = test[complete_test_positions]
        complete_model = Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=RIDGE_ALPHA))])
        complete_model.fit(X[complete_train], y[complete_train])
        report["complete_case_comparison"] = {
            "train_rows": len(complete_train), "discarded_train_rows": len(train) - len(complete_train),
            "test_rows": len(complete_test), "excluded_test_rows": len(test) - len(complete_test),
            "models": [
                _metrics("ridge", "Imputation model on complete test rows", y[complete_test], predicted[complete_test_positions], bootstrap_samples),
                _metrics("complete_case", "Ridge trained only on complete rows", y[complete_test], complete_model.predict(X[complete_test]), bootstrap_samples),
            ],
            "note": "Both models use the same complete test cohort; these subset metrics must not be compared directly with full-test metrics.",
        }
    else:
        report["complete_case_comparison"] = {"available": False, "reason": "Too few complete rows for a meaningful comparison."}
    slices = []
    for label, mask in (("Any feature missing", missing[test].any(axis=1)), ("All features observed", ~missing[test].any(axis=1))):
        count = int(mask.sum())
        if count:
            slice_covered = int((errors[mask] <= half_width).sum())
            slices.append({"label": label, "rows": count, "mae": float(errors[mask].mean()), "coverage": slice_covered / count, "coverage_ci": wilson_interval(slice_covered, count)})
    report["missingness_slices"] = slices
    if repeated_properties:
        report["limitations"].append("Repeated PIDs were kept within a single partition. Row-level bootstrap and conformal uncertainty still require independence/exchangeability assumptions; repeated sales can violate them.")
    return Experiment(report=report, model=model, dataset=dataset, split_indices=split, half_width=half_width)
