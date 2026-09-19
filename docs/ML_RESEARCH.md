# Property ML Lab: research and analysis contract

This lab asks a predictive question: **How well can a small, explainable model predict historical house sale prices when some property measurements are missing?** It demonstrates data preparation, a baseline, regression, held-out evaluation, and two different kinds of uncertainty. It does not estimate the causal effect of improving a house.

## Why this belongs in Sprint Lead Generation

An inspection of the local outcome store during development found 3,424 stored scores and zero recorded outcome events. Those scores are heuristic outputs, not observed conversion labels. Training a conversion model against them would primarily teach it to reproduce an existing scoring rule. It would not establish that the model predicts replies, appointments, or closed business.

The lab therefore uses a public housing benchmark with observed sale prices. The methods are relevant to incomplete property records, but the benchmark remains a separate educational experiment. A future conversion model needs prospect features recorded before outreach, dated outcomes, an explicit observation window, and a split that prevents the same prospect appearing in both training and evaluation.

## Data and provenance

The Ames Housing dataset contains 2,930 residential-sale records from Ames, Iowa, during 2006–2010. Dean De Cock assembled it from assessor records for teaching regression; the published version retains the latest sale for repeatedly sold properties and excludes nonresidential transactions. Its historical prices and geographic coverage limit transfer to other places or years. [Original research paper](https://jse.amstat.org/v19n3/decock.pdf)

- Raw source: [AmesHousing.txt](https://jse.amstat.org/v19n3/decock/AmesHousing.txt), a tab-separated file with 82 columns, including two identifiers.
- Download SHA-256 verified during development: `6cfe6cb525ba437de428653a1040e2aed7d696640bf75203786a6d7a0e67cfcc`.
- Field definitions: [original data dictionary](https://jse.amstat.org/v19n3/decock/DataDocumentation.txt). That file uses Windows-1252 characters; a strict UTF-8 reader may fail.
- Attribution: Dean De Cock (2011), *Ames, Iowa: Alternative to the Boston Housing Data as an End of Semester Regression Project*, Journal of Statistics Education, 19(3).

The canonical host makes the data available for educational analysis, but an explicit dataset redistribution license was not verified. The article has a separate copyright notice. The project links to the source and downloads a local cache instead of assigning a new license to or committing the raw dataset. Project code licensing does not establish ownership of the source data.

## Deliberately small feature set

All eight inputs are numeric and understandable without a specialist real-estate background. The target is `SalePrice`, in historical US dollars. `Order`, parcel identifiers, and the target never enter the feature matrix.

| Application field | Source field | Meaning |
| --- | --- | --- |
| `lot_frontage` | `Lot Frontage` | Feet of street frontage |
| `living_area` | `Gr Liv Area` | Above-ground living area, square feet |
| `lot_area` | `Lot Area` | Lot area, square feet |
| `overall_quality` | `Overall Qual` | Recorded overall material/finish rating, 1–10 |
| `year_built` | `Year Built` | Original construction year |
| `full_baths` | `Full Bath` | Full bathrooms above ground |
| `bedrooms` | `Bedroom AbvGr` | Bedrooms above ground |
| `garage_area` | `Garage Area` | Garage area, square feet |

This selection keeps the demonstration readable. Excluding neighborhood, renovations, and other predictors can leave systematic errors; simplicity is a teaching choice, not evidence that those omitted variables are unimportant.

## Missing data: unknown is different from absent

In the downloaded file, `Lot Frontage` contains 490 blank values and `Garage Area` contains one. Other selected inputs are complete. The lab preserves rows and fills unknown numeric values with the corresponding **training-set median**. Missing-value indicators are learned for columns with missing values in training: frontage and garage area in this run. They let the model distinguish an imputed value from an originally observed value. They are predictive features, not proof that missingness itself causes a price difference. A user can also leave another input blank, but that column has no learned missingness indicator; the simulator flags this unfamiliar input pattern.

An observed garage area of zero stays zero. In other, excluded columns, the dictionary uses the literal category `NA` to mean no basement, no fireplace, or no garage. Those are recorded absences, not generic unknowns. A future categorical extension must preserve that meaning instead of blindly treating every `NA` as a missing measurement. [Data dictionary](https://jse.amstat.org/v19n3/decock/DataDocumentation.txt)

Median imputation creates a usable input; it does not recover the true missing value or prove that missingness is random. If frontage is missing more often for unusual lots, that process could affect both prediction and generalization. The report audits observed missingness, but cannot identify the missing-data mechanism from the observed values alone.

## Model and split choices

The design fixes seed 42, an approximately 60%/20%/20% random split, and Ridge penalty `alpha=10` before assessing test performance. For the complete canonical dataset, the partitions contain 1,758 training, 586 calibration, and 586 test rows.

| Partition | Permitted use |
| --- | --- |
| Training | Estimate imputation medians, scaling parameters, coefficients, and baseline price |
| Calibration | Compute the absolute-residual quantile for the prediction interval |
| Test | Report final errors and prediction-interval coverage |

The baseline always predicts the median training sale price. The main pipeline imputes missing measurements, records missingness, standardizes inputs, and fits Ridge regression. Ridge is a linear model whose objective penalizes large coefficients as well as prediction error. Scaling makes that penalty meaningful across inputs measured in feet, years, and counts. The chosen penalty is a fixed teaching setting, not a claimed optimum. [Ridge reference](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)

No imputer, scaler, or model is fitted on calibration or test data. Preprocessing is part of the fitted pipeline. If model tuning is added later, it belongs inside the training partition, using cross-validation there; calibration and test sets must stay separate. [Scikit-learn guidance on leakage](https://scikit-learn.org/stable/common_pitfalls.html)

A complete-case comparison is a sensitivity exercise: train another Ridge model only on complete training rows and evaluate both approaches on the same complete test rows. The report states how many records were excluded. That comparison describes a selected population and cannot establish that deleting missing rows works for records that have missing values.

The displayed coefficients are in dollars per **one training standard deviation** of a transformed input, holding the other transformed inputs fixed. They are not dollars per original square foot, bedroom, or year. The same scaling applies to missingness indicators. Correlated inputs and regularization affect the coefficients, so their signs and magnitudes should not be interpreted as causal returns or a universal ranking of feature importance.

## Two intervals, two questions

### 95% bootstrap confidence interval for mean absolute error

Mean absolute error (MAE) is the mean of `abs(actual price - predicted price)` over the held-out test rows. It is measured in dollars and treats overestimates and underestimates equally.

The percentile bootstrap repeatedly samples test-row indices with replacement, calculates MAE for each resample, and takes the 2.5th and 97.5th percentiles. For a comparison of two models, use the same resampled indices for both, or equivalently bootstrap their rowwise error differences. The default is 2,000 resamples with seed 42; the saved report records these settings. [SciPy bootstrap reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)

Interpretation: this is an approximate interval for the **average error of the already fitted model on comparable data**. It captures uncertainty associated with the test cases under an independent, representative-row assumption. It does not include refitting variability, uncertainty about the missing-data mechanism, or future market changes. It is not an interval containing 95% of individual sale prices. Percentile intervals are easy to explain but can be imperfect for skewed errors or small samples.

An improvement interval should use `baseline absolute error - Ridge absolute error`, averaged over paired rows. Positive values mean Ridge has lower MAE. Practical importance still depends on the size of the dollar improvement, not merely whether the interval excludes zero.

### 90% split-conformal prediction interval

After fitting the model, calculate each calibration absolute residual `r = abs(y - prediction)`. With `m` calibration rows and target miscoverage `a=0.10`, choose the one-based order statistic `k = ceil((m+1)*(1-a))`. For 586 calibration rows, `k=529`. The 529th smallest residual is `q`; the interval is `prediction ± q`. Using an interpolated ordinary 90th percentile can miss this finite-sample correction. If `k > m`, this implementation rejects the request because the data cannot supply a finite interval at that level. It never silently caps the rank.

The coverage statement is **marginal** and requires exchangeability between calibration observations and the new case. It is not a guarantee within every neighborhood or price band. Report actual test coverage as the fraction of held-out prices inside their intervals, alongside interval width. Arbitrary user-entered profiles or a new pattern of omitted inputs can violate the similarity assumption. [Angelopoulos and Bates, conformal-prediction introduction](https://arxiv.org/abs/2107.07511)

This teaching version has one shared residual radius, so it does not adapt its uncertainty width to the property's price or completeness. A narrower MAE confidence interval and a wider individual prediction interval can both be reasonable: they answer different questions.

The report also gives a 95% Wilson interval around observed test coverage. This describes binomial sampling uncertainty, treating evaluation cases as independent and the fitted interval rule as fixed. It does not establish subgroup coverage or protect against market changes.

## Reproduced benchmark results

The canonical download, fixed seed 42, `alpha=10`, and 2,000 bootstrap resamples produced these results on the same 586 test rows:

| Model | Mean absolute error | 95% bootstrap confidence interval |
| --- | --- | --- |
| Training-median baseline | $58,677 | $53,799–$63,852 |
| Ridge with median imputation | $22,991 | $21,071–$25,008 |

The paired mean reduction in absolute error was **$35,686**, with a 95% bootstrap interval of **$31,708–$39,652**. This supports a substantial improvement over the constant baseline on comparable historical cases; it does not show present-day valuation accuracy.

The 90% prediction intervals used a half-width of **$46,924** and contained **536 of 586** test prices: **91.47% observed coverage**, with a 95% Wilson interval of **88.93%–93.47%**. The nominal target is 90%; the observed fraction need not equal it exactly.

Complete-case training retained 1,449 rows and discarded 309. On the same 493 complete test rows, MAE was **$23,519** for the imputation model and **$23,584** for the complete-case model. These point estimates are very close; the project does not claim a general accuracy benefit from imputation. Its demonstrated practical benefit is retaining incomplete training records and producing predictions for the 93 incomplete test records, which the deletion-only pipeline cannot serve directly.

The saved `reports/ml_report.json` is the exact machine-readable result. These rounded figures describe this particular version and split. An independent calculation checked partition disjointness, training-only medians, both bootstrap intervals, the calibration rank, and coverage against the report.

## What the results can support

The result can show that a simple model learns useful predictive associations on a held-out part of this benchmark and can produce inspectable uncertainty summaries. It cannot establish accurate current valuations, causal renovation returns, improved lead conversion, or reliability across all neighborhoods.

The most important limitations are:

1. The dataset represents one historical city market; random splitting measures interpolation within that mix, not forecasting into a new market.
2. Nearby homes and sales from related periods may be dependent, weakening naive row-level uncertainty calculations.
3. Median imputation compresses information and does not solve informative missingness.
4. The linear model may miss nonlinear relationships and has fewer features than a valuation model would normally use.
5. Unusual and partial sales remain in the benchmark; a good average error can hide large mistakes.
6. One fixed split supports a reproducible demonstration, not a claim that the model's ranking is stable across every split.
7. Changing features, seeds, or methods after viewing test results would turn subsequent test comparisons into exploratory findings. A new final evaluation set would then be needed for an independent confirmation.

Useful next studies would be a time-based evaluation, neighborhood-specific residual checks with adequate sample sizes, and a documented comparison of missing-data strategies using training-only cross-validation. Actual lead conversion requires its own labels and validation design.

Sources were checked on 2026-09-19. Statistical definitions describe the methods; the executable report remains the source of truth for the current model's measured results.
