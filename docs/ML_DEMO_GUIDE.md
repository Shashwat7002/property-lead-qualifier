# Property ML Lab: a three-minute demo you can explain

The strongest demonstration is understanding each choice, reproducing the result, and being honest about what it shows. Use the prompts below in your own words after running the app.

## Before the demo

From the Sprint Lead Generation repository, install the optional ML dependencies and rebuild the experiment:

```bash
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python scripts/train_property_ml.py --download
```

Start the application using the repository's normal development command, then open `/ml-lab`. Keep [the research notes](ML_RESEARCH.md) and the training script available. Read the generated metrics rather than memorizing values from an older run. The first download requires network access; later runs can use the local data cache.

Check that you can point to the split, the median imputer, the Ridge estimator, the bootstrap, and the calibration quantile in the source. Be ready to explain what each does without reading the code aloud.

## The walkthrough

### 0:00–0:30 — State the problem

“This is a small ML lab inside Sprint Lead Generation. It predicts historical house sale prices using eight understandable property measurements. I wanted to show the full process: handling missing values, comparing against a simple baseline, and reporting how uncertain the evaluation is.”

“The app's lead scores do not yet have observed conversion outcomes to train against. The housing benchmark provides real labels, so this demonstration has an outcome I can actually evaluate.”

### 0:30–1:10 — Show the missingness audit

Point to lot frontage and explain that an unknown measurement is different from a known zero. It has 490 missing measurements; its training median is 67 feet in the reference run.

“I keep these rows. The model fills an unknown measurement using a median calculated from training rows, and records missingness for columns that had missing training values. The median is a practical substitute, not the recovered truth. A garage area of zero remains zero because it describes an observed absence.”

Show the split counts: 1,758 training, 586 calibration, and 586 test rows. Explain why test data cannot contribute to the median or scaling parameters. For the complete-case comparison, explain its narrower evaluation cohort before comparing its errors. The two approaches have very similar errors on that subset; the clear benefit of imputation here is keeping records and accepting incomplete inputs.

### 1:10–1:50 — Explain the baseline and model

“The baseline predicts the same training median price for every house. Ridge regression combines the features in a linear formula, with a penalty that discourages excessively large coefficients. I fixed the penalty for this teaching version.”

Read the baseline and Ridge test MAEs. Interpret them in dollars: an MAE of a given amount is the average absolute miss on the held-out houses. It is not the largest miss, and it is not an accuracy percentage.

Reference run: baseline MAE **$58,677**; Ridge MAE **$22,991**; paired reduction **$35,686**, with a 95% bootstrap interval of **$31,708–$39,652**. Use the live report if your code or settings have changed.

### 1:50–2:30 — Explain the two intervals

Point to the interval around MAE:

“The 95% bootstrap confidence interval summarizes uncertainty in the model's average error on comparable cases. The model stays fixed while I resample test cases.”

Then show a house prediction and its range:

“This 90% prediction interval concerns one sale price. Its width comes from residuals on a separate calibration set. Under the similarity assumption, the method targets coverage across cases overall; it doesn't promise the same coverage for every kind of house.”

Read the actual held-out coverage. An observed coverage percentage can differ from the nominal target, so describe what happened rather than claiming the target was achieved exactly.

Reference run: the intervals contain **536/586 test prices (91.47%)**, with a **95% Wilson interval of 88.93%–93.47%**. The interval radius is about **$46,924**. The confidence interval for Ridge's average error is much narrower, **$21,071–$25,008**, because it concerns an average rather than an individual outcome.

### 2:30–3:00 — Show one interaction and one limitation

Change one property input or leave an allowed measurement blank, and inspect the updated prediction and imputation explanation.

“The sandbox demonstrates the fitted pipeline. An invented combination of inputs may not resemble the historical evaluation data. These Ames prices come from 2006–2010; this is not a tested valuation tool for Athens today.”

Close by naming the next experiment you understand: testing a time-based holdout, checking errors across price bands, or collecting real outreach outcomes before building a conversion model.

## A small worked example

Suppose three held-out prices are $100,000, $150,000, and $200,000, and the model predicts $110,000, $140,000, and $180,000. The absolute errors are $10,000, $10,000, and $20,000. MAE is $40,000 / 3, or about $13,333.

These invented numbers explain the arithmetic; they are not results from this project. A bootstrap could sample error values with replacement, such as $10,000, $20,000, $20,000, and recompute the mean. Repeating that process approximates how variable the reported average error might be across comparable test samples.

## Terms to know

| Term | Plain-language explanation |
| --- | --- |
| Feature | An input known when making a prediction, such as floor area |
| Target or label | The outcome to predict, here the observed sale price |
| Training | Estimating model and preprocessing parameters from examples |
| Test set | Cases held aside for final evaluation |
| Calibration set | Separate cases used to set the prediction-interval radius |
| Imputation | Filling an unknown value using a stated rule |
| Missingness indicator | A flag that records whether an input was missing |
| Leakage | Letting information unavailable at prediction time influence training or model choices |
| Regression | Predicting a numerical outcome |
| Regularization | Penalizing model complexity; Ridge penalizes squared coefficient sizes |
| Residual | Actual value minus predicted value |
| MAE | Average absolute prediction error, in the target's units |
| Bootstrap | Repeated resampling with replacement to estimate variability |
| Confidence interval | An interval for an aggregate quantity such as mean error, constructed by a procedure with an intended repeated-sampling coverage rate |
| Prediction interval | A range for a new outcome, such as one future sale price |
| Exchangeability | The assumption that calibration cases and the new case can be treated as coming from the same underlying process without their order mattering |
| Overfitting | Learning details of training examples that fail to generalize |

## Questions worth practicing

**Why a median baseline?** It is easy to audit and uses no property features. The sample median minimizes absolute error among constant predictions on training data. Beating it demonstrates that features add predictive information on the held-out cases.

**Why Ridge instead of a complex model?** It keeps the relationship between features and prediction inspectable and introduces regularization with little additional machinery. A more complicated model would need evidence that its improved performance justified its complexity.

**Why not delete every row with a missing value?** Deletion discards usable observations and changes which properties are represented. It may be reasonable in some designs, but its error on complete rows does not tell us how it would perform on incomplete ones.

**Why not calculate the median before splitting?** That would let the evaluation cases affect training. The held-out result would no longer evaluate a pipeline trained solely on the training sample.

**Why use three splits?** Training learns the prediction rule. Calibration estimates the prediction-interval radius. Test measures performance without doing either job. This sacrifices some training data to make the responsibilities easy to inspect.

**Is a 95% confidence interval a 95% chance the true MAE is in this particular interval?** That is not the frequentist claim. Under the assumptions, the procedure aims to include the population quantity in approximately 95% of repeated samples. Here the bootstrap is approximate and the fitted model is treated as fixed.

**Does the 90% prediction interval guarantee 90% coverage for this house?** No. Its theoretical target averages over exchangeable calibration and new cases. Coverage may differ for expensive properties or other subgroups, and changes in place, year, or missingness can break that assumption.

**Does the MAE confidence interval include uncertainty about training the model?** No. This version resamples evaluation cases while retaining the same fitted model. A study of retraining variability would need additional resampling and refitting.

**Is `R² = 0.8` the same as 80% accuracy?** No. R² measures improvement in squared error relative to a mean-prediction reference on the evaluation data. It is not the proportion of correctly predicted houses; regression does not have a natural exact-match accuracy measure.

**Does a positive floor-area coefficient prove an extension raises value by that amount?** No. This is observational prediction. Location, condition, and other correlated features can explain part of that association. A renovation's causal return is a different question.

**What do the coefficient units mean?** Inputs are standardized. A coefficient is the change in the model's predicted dollars for a one-training-standard-deviation change in that transformed input, holding other transformed inputs fixed. It is not a dollar change per original square foot or bedroom. A coefficient on a missingness flag is also standardized.

**What if the baseline wins?** Report it. Check the pipeline for errors and investigate new ideas within training data. Repeatedly trying models against the same test set until one wins would weaken the evaluation.

**What would make this a lead-conversion model?** Observed outcomes with timestamps, an agreed prediction moment and outcome window, enough positive and negative cases, and evaluation on prospects the model has never seen. Existing heuristic scores alone are not those labels.

## Show ownership honestly

This project was developed with AI assistance. Describe what you personally ran, checked, changed, and can explain; do not claim you independently wrote or validated parts you have not reviewed. Credibility comes from understanding the result and recognizing a mistake when one appears.

Before presenting, answer these without assistance:

1. Which exact rows can affect the imputation median?
2. Where is the target excluded from the feature matrix?
3. How does a missing value move through the pipeline?
4. How is the conformal rank different from taking an ordinary percentile?
5. What does the bootstrap resample, and what stays fixed?
6. Which result would change your view of the model's usefulness?
7. What would you collect next to evaluate the actual business problem?

If you cannot explain a component, say so and walk through the relevant code before using it in the interview. Use [the research notes and linked primary sources](ML_RESEARCH.md) for the derivations and limitations.
