---
name: scikit-learn-modeling
description: Cross-validated tabular ML pipelines, preprocessing without data leakage, model comparison, and reproducible evaluation metrics using installed `scikit-learn`.
---
# Scikit-Learn Modeling & Pipeline Discipline

For data-driven modeling, surrogate approximation, classification, regression, forecasting, and clustering tasks in OR-Path (`scikit-learn` + `pandas` + `numpy`).

1. **Leakage-Free Pipelines Only**:
   - Wrap ALL imputation (`SimpleImputer`), scaling (`StandardScaler`/`RobustScaler`), and categorical encoding (`OneHotEncoder(handle_unknown='ignore')`) inside `ColumnTransformer` + `sklearn.pipeline.Pipeline` fit **strictly inside cross-validation folds** — never call `fit_transform` on the full dataset before splitting!
2. **Split Structure & Reproducibility**:
   - Use `StratifiedKFold` for imbalanced classification, `GroupKFold` when observations cluster by entity, and `TimeSeriesSplit` for temporal forecasting (never random-shuffle future leakage into training!).
   - Fix `random_state=42` everywhere (`KFold`, `RandomForest*`, `HistGradientBoosting*`, train/test split) so independent validation reproduces exact scores.
3. **Model Progression & Validation Metrics**:
   - Establish a transparent baseline first (`DummyRegressor`/`DummyClassifier` or `Ridge`/`LogisticRegression` linear baseline), then benchmark tree ensembles (`RandomForest*` / `HistGradientBoosting*`) via cross-validated OOF predictions (`cross_val_predict`).
   - Report full metric suite (`RMSE`, `MAE`, `R^2` or `ROC-AUC`, `F1`, balanced accuracy) computed strictly from out-of-fold / held-out predictions.
