/* Property ML Lab: dependency-free presentation of the reproducible backend report. */
(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);
  const money = (value) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
  const number = (value, digits = 0) => new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
  const percent = (value, digits = 1) => `${number(value * 100, digits)}%`;
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  let report = null;
  let exampleIndex = 0;
  let activeExample = null;
  let lastExampleValues = null;
  let predictionController = null;
  let predictionVersion = 0;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function getJSON(url, options = {}) {
    const response = await fetch(url, { ...options, headers: { Accept: 'application/json', ...(options.headers || {}) } });
    let data;
    try {
      data = await response.json();
    } catch (_) {
      throw new Error(`The server returned an unreadable response (${response.status}). Please try again.`);
    }
    if (!response.ok || data.error) throw new Error(data.error || `The request failed (${response.status}). Please try again.`);
    return data;
  }

  function renderModels(models) {
    const comparison = byId('model-comparison');
    const body = byId('model-table-body');
    comparison.replaceChildren();
    body.replaceChildren();
    const maximum = Math.max(1, ...models.map((model) => Math.max(model.mae_ci[1], model.mae))) * 1.13;

    models.forEach((model, index) => {
      const row = element('div', `model-row${index > 0 ? ' featured' : ''}`);
      const heading = element('div', 'model-row-heading');
      heading.append(element('span', '', model.label), element('strong', '', money(model.mae)));
      const track = element('div', 'comparison-track');
      track.setAttribute('aria-hidden', 'true');
      const bar = element('span', 'comparison-bar');
      bar.style.width = `${clamp(model.mae / maximum * 100, 0, 100)}%`;
      const ci = element('span', 'comparison-ci');
      ci.style.left = `${clamp(model.mae_ci[0] / maximum * 100, 0, 100)}%`;
      ci.style.width = `${clamp((model.mae_ci[1] - model.mae_ci[0]) / maximum * 100, 0, 100)}%`;
      const point = element('span', 'comparison-point');
      point.style.left = `${clamp(model.mae / maximum * 100, 0, 100)}%`;
      track.append(bar, ci, point);
      row.append(heading, track, element('p', 'ci-caption', `95% confidence interval: ${money(model.mae_ci[0])}–${money(model.mae_ci[1])}`));
      comparison.append(row);

      const tableRow = element('tr');
      [model.label, money(model.mae), money(model.rmse), number(model.r2, 3)].forEach((value) => tableRow.append(element('td', '', value)));
      body.append(tableRow);
    });

    const axis = element('div', 'comparison-axis');
    axis.setAttribute('aria-hidden', 'true');
    [0, maximum / 2, maximum].forEach((value) => axis.append(element('span', '', money(value))));
    comparison.append(axis);
    const baseline = models.find((model) => /baseline|median|dummy/i.test(model.key)) || models[0];
    const ridge = models.find((model) => /ridge/i.test(model.key)) || models[1];
    const finding = byId('improvement-note');
    finding.hidden = !(baseline && ridge && baseline.mae > 0);
    if (!finding.hidden) {
      const improvement = (baseline.mae - ridge.mae) / baseline.mae;
      finding.textContent = improvement >= 0
        ? `Ridge reduced average test error by ${percent(improvement)} compared with the median baseline on this split.`
        : `Ridge had ${percent(-improvement)} more average test error than the median baseline on this split.`;
    }
  }

  function renderCoverage(interval) {
    byId('coverage-value').textContent = percent(interval.coverage);
    byId('coverage-description').textContent = `${number(interval.covered)} of ${number(interval.total)} test sale prices fell inside their prediction intervals.`;
    byId('coverage-bar').style.width = `${clamp(interval.coverage * 100, 0, 100)}%`;
    document.querySelector('.coverage-target').style.left = `${clamp(interval.level * 100, 0, 100)}%`;
    byId('coverage-target-label').textContent = `${percent(interval.level, 0)} target`;
    byId('coverage-ci').textContent = `95% coverage confidence interval: ${percent(interval.coverage_ci[0])}–${percent(interval.coverage_ci[1])}.`;
  }

  function renderSplit(split) {
    const track = byId('split-track');
    const details = byId('split-details');
    track.replaceChildren();
    details.replaceChildren();
    const total = split.train + split.calibration + split.test;
    const parts = [
      ['train', 'Training', 'Learn the medians, scaling, and model weights.'],
      ['calibration', 'Calibration', 'Set the prediction interval width using separate errors.'],
      ['test', 'Test', 'Measure final error and coverage on unseen houses.'],
    ];
    parts.forEach(([key, label, explanation]) => {
      const segment = element('span', `split-segment ${key}`);
      segment.style.flexGrow = split[key];
      track.append(segment);
      const detail = element('div', 'split-detail');
      const heading = element('h4', '', label);
      heading.append(element('span', '', `${number(split[key])} rows · ${percent(split[key] / total, 0)}`));
      detail.append(heading, element('p', '', explanation));
      details.append(detail);
    });
    byId('split-seed').textContent = `Fixed random seed: ${split.seed}`;
  }

  function renderMissingness(features) {
    const body = byId('missing-table-body');
    body.replaceChildren();
    [...features].sort((a, b) => b.missing_count - a.missing_count).forEach((feature) => {
      const row = element('tr');
      const label = element('td', 'feature-name', feature.label);
      if (feature.unit) label.append(element('span', 'feature-unit', ` (${feature.unit})`));
      const rateCell = element('td');
      const rate = element('div', 'missing-rate');
      const track = element('span', 'missing-mini-track');
      track.setAttribute('aria-hidden', 'true');
      const fill = element('span', 'missing-mini-fill');
      fill.style.width = `${clamp(feature.missing_pct, 0, 100)}%`;
      track.append(fill);
      rate.append(track, element('span', '', `${number(feature.missing_pct, 2)}%`));
      rateCell.append(rate);
      row.append(label, element('td', '', number(feature.missing_count)), rateCell, element('td', '', number(feature.train_median, 2)));
      body.append(row);
    });
  }

  function renderCompleteCase(comparison) {
    if (!comparison || comparison.available === false || !Array.isArray(comparison.models)) {
      byId('complete-case-audit').hidden = true;
      return;
    }
    byId('complete-case-audit').hidden = false;
    byId('complete-case-summary').textContent = `Dropping incomplete rows would discard ${number(comparison.discarded_train_rows)} training houses and leave ${number(comparison.excluded_test_rows)} test houses without predictions. Imputation lets the model use and serve those rows.`;
    byId('complete-case-caption').textContent = `Both approaches evaluated on the same ${number(comparison.test_rows)} complete test houses.`;
    const body = byId('complete-case-body');
    body.replaceChildren();
    comparison.models.forEach((model) => {
      const row = element('tr');
      const label = model.key === 'ridge' ? 'Median imputation + Ridge' : 'Complete rows + Ridge';
      [label, money(model.mae), `${money(model.mae_ci[0])}–${money(model.mae_ci[1])}`].forEach((value) => row.append(element('td', '', value)));
      body.append(row);
    });
  }

  function renderForm(features) {
    const fields = byId('feature-fields');
    fields.replaceChildren();
    features.forEach((feature, index) => {
      const container = element('div', 'input-field');
      const id = `feature-${index}`;
      const label = element('label', '', feature.label);
      label.htmlFor = id;
      if (feature.unit) label.append(element('span', '', ` (${feature.unit})`));
      const input = element('input');
      input.type = 'number';
      input.name = feature.key;
      input.id = id;
      input.step = feature.integer ? '1' : 'any';
      input.inputMode = feature.integer ? 'numeric' : 'decimal';
      input.autocomplete = 'off';
      input.placeholder = 'Unknown → training median';
      if (Number.isFinite(feature.min)) input.min = feature.min;
      if (Number.isFinite(feature.max)) input.max = feature.max;
      input.value = feature.default ?? '';
      input.setAttribute('aria-describedby', `${id}-hint`);
      const hint = element('p', 'field-range', `${number(feature.min, 2)}–${number(feature.max, 2)} · blank = unknown`);
      hint.id = `${id}-hint`;
      container.append(label, input, hint);
      fields.append(container);
    });
    const frontage = features.find((feature) => /frontage/i.test(`${feature.key} ${feature.label}`)) || features.find((feature) => feature.missing_count > 0) || features[0];
    byId('clear-feature').textContent = `2. Clear ${/frontage/i.test(frontage.label) ? 'frontage' : frontage.label.toLowerCase()}`;
    byId('clear-feature').dataset.feature = frontage.key;
    byId('load-example').disabled = !report.examples?.length;
  }

  function readValues() {
    const values = {};
    report.features.forEach((feature) => {
      const input = byId('prediction-form').elements.namedItem(feature.key);
      values[feature.key] = input.value.trim() === '' ? null : Number(input.value);
    });
    return values;
  }

  function invalidatePrediction() {
    predictionVersion += 1;
    predictionController?.abort();
    predictionController = null;
    byId('prediction-output').hidden = true;
    byId('prediction-empty').hidden = false;
    byId('prediction-error').hidden = true;
    byId('predict-button').disabled = false;
    byId('predict-button').textContent = 'Estimate sale price ↗';
    document.querySelector('.prediction-result').setAttribute('aria-busy', 'false');
  }

  function loadExample() {
    if (!report?.examples?.length) return;
    invalidatePrediction();
    // Start with a measured frontage so the clear-field action demonstrates a
    // visible change. Missing examples remain available when cycling profiles.
    const examples = [...report.examples].sort((a, b) => Number(a.values.lot_frontage == null) - Number(b.values.lot_frontage == null));
    activeExample = examples[exampleIndex % examples.length];
    exampleIndex += 1;
    report.features.forEach((feature) => {
      byId('prediction-form').elements.namedItem(feature.key).value = activeExample.values[feature.key] ?? '';
    });
    lastExampleValues = readValues();
    byId('example-status').textContent = `Loaded test house ${activeExample.id}. Its observed historical sale price was ${money(activeExample.actual)}. Clear a field to test how the model handles a gap.`;
  }

  function clearFeature() {
    if (!report) return;
    invalidatePrediction();
    const key = byId('clear-feature').dataset.feature;
    const field = report.features.find((feature) => feature.key === key);
    const input = byId('prediction-form').elements.namedItem(key);
    input.value = '';
    input.focus({ preventScroll: true });
    byId('example-status').textContent = `${field.label} is now unknown. Run the prediction to see its training-median replacement (${number(field.train_median, 2)}${field.unit ? ` ${field.unit}` : ''}).`;
  }

  function renderPrediction(result, values) {
    byId('predicted-price').textContent = money(result.prediction);
    byId('prediction-level').textContent = `${percent(result.interval_level, 0)} prediction interval`;
    byId('prediction-lower').textContent = money(result.lower);
    byId('prediction-upper').textContent = money(result.upper);
    const range = result.upper - result.lower;
    byId('prediction-marker').style.left = `${range > 0 ? clamp((result.prediction - result.lower) / range * 100, 0, 100) : 50}%`;
    const fields = byId('imputed-fields');
    fields.replaceChildren();
    result.imputed_fields.forEach((field) => {
      const feature = report.features.find((item) => item.key === field.key);
      const row = element('li');
      row.append(element('span', '', field.label), element('strong', '', `${number(field.value, 2)}${feature?.unit ? ` ${feature.unit}` : ''}`));
      fields.append(row);
    });
    byId('imputation-title').textContent = `Values filled in (${result.imputed_fields.length})`;
    byId('no-imputation').hidden = result.imputed_fields.length > 0;
    const warnings = byId('prediction-warnings');
    warnings.replaceChildren();
    (result.warnings || []).forEach((warning) => warnings.append(element('li', '', warning)));
    warnings.hidden = !warnings.childElementCount;
    const actual = byId('actual-comparison');
    // Compare with a historical outcome only while the observed features still
    // describe that house. Blanking a feature is allowed; changing one is not.
    const sameHouse = activeExample && lastExampleValues && report.features.every((feature) => values[feature.key] === null || values[feature.key] === lastExampleValues[feature.key]);
    actual.hidden = !sameHouse;
    if (sameHouse) {
      const inside = activeExample.actual >= result.lower && activeExample.actual <= result.upper;
      actual.textContent = `Observed sale: ${money(activeExample.actual)} · ${inside ? 'inside' : 'outside'} this interval. Absolute error: ${money(Math.abs(activeExample.actual - result.prediction))}.`;
    }
    byId('prediction-empty').hidden = true;
    byId('prediction-output').hidden = false;
  }

  async function predict(event) {
    event.preventDefault();
    if (!report || !byId('prediction-form').reportValidity()) return;
    const button = byId('predict-button');
    const error = byId('prediction-error');
    const values = readValues();
    predictionController?.abort();
    predictionController = new AbortController();
    const version = ++predictionVersion;
    button.disabled = true;
    button.textContent = 'Estimating…';
    error.hidden = true;
    document.querySelector('.prediction-result').setAttribute('aria-busy', 'true');
    try {
      const result = await getJSON('/api/ml/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values), signal: predictionController.signal });
      if (version !== predictionVersion) return;
      renderPrediction(result, values);
    } catch (failure) {
      if (failure.name === 'AbortError' || version !== predictionVersion) return;
      error.textContent = failure.message;
      error.hidden = false;
    } finally {
      if (version === predictionVersion) {
        button.disabled = false;
        button.textContent = 'Estimate sale price ↗';
        document.querySelector('.prediction-result').setAttribute('aria-busy', 'false');
      }
    }
  }

  async function loadReport() {
    byId('load-state').hidden = false;
    byId('load-error').hidden = true;
    byId('report-content').hidden = true;
    byId('retry-button').disabled = true;
    try {
      report = await getJSON('/api/ml/report');
      byId('dataset-rows').textContent = number(report.dataset.rows);
      byId('feature-count').textContent = number(report.features.length);
      byId('missing-rows').textContent = number(report.dataset.missing_rows);
      byId('test-rows').textContent = number(report.split.test);
      byId('missing-cell-count').textContent = `${number(report.dataset.missing_cells)} missing feature values`;
      byId('dataset-provenance').textContent = `${report.dataset.name} · ${number(report.dataset.rows)} sales · fixed seed ${report.split.seed}. Evaluation metrics come from this run’s held-out test split.`;
      byId('dataset-hash').textContent = report.dataset.sha256;
      renderModels(report.models);
      renderCoverage(report.interval);
      renderSplit(report.split);
      renderMissingness(report.features);
      renderCompleteCase(report.complete_case_comparison);
      renderForm(report.features);
      byId('report-content').hidden = false;
      byId('load-state').hidden = true;
    } catch (failure) {
      byId('load-state').hidden = true;
      byId('load-error-message').textContent = failure.message || 'Check that the local server is running, then try again.';
      byId('load-error').hidden = false;
    } finally {
      byId('retry-button').disabled = false;
    }
  }

  byId('retry-button').addEventListener('click', loadReport);
  byId('load-example').addEventListener('click', loadExample);
  byId('clear-feature').addEventListener('click', clearFeature);
  byId('prediction-form').addEventListener('submit', predict);
  byId('prediction-form').addEventListener('input', () => {
    invalidatePrediction();
    byId('example-status').textContent = 'Features updated. Run the prediction to calculate a new estimate.';
  });
  loadReport();
})();
