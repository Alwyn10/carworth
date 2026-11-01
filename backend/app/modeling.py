"""Training: compare several models fairly, pick the best one, and measure how wrong it is."""
from __future__ import annotations

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import CATEGORICAL, FEATURES, NUMERIC

BASELINE = "Baseline (always the median price)"
INTERVAL_LEVEL = 0.8  # the price range should hold for about 80% of cars


def build_pipeline(estimator):
    """Prices are skewed, so the model learns log(price) and converts back to rupees."""
    prep = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])
    return TransformedTargetRegressor(
        regressor=Pipeline([("prep", prep), ("model", estimator)]), func=np.log, inverse_func=np.exp
    )


def candidates(quick: bool = False) -> dict:
    trees, iters = (40, 60) if quick else (300, 300)
    return {
        BASELINE: DummyRegressor(strategy="median"),
        "Ridge regression": Ridge(alpha=1.0),
        "Random forest": RandomForestRegressor(n_estimators=trees, min_samples_leaf=2, random_state=0, n_jobs=-1),
        "Gradient boosting": HistGradientBoostingRegressor(max_iter=iters, learning_rate=0.06, random_state=0),
    }


def score(y_true, y_pred) -> dict:
    err = np.abs(np.asarray(y_true) - np.asarray(y_pred))
    return {"mae": float(err.mean()), "mdape": float(np.median(err / np.asarray(y_true)))}


def category_options(df: pd.DataFrame, min_count: int = 10) -> dict:
    out = {}
    for col in CATEGORICAL:
        counts = df[col].value_counts()
        keep = counts[counts >= min_count]
        values = (keep if len(keep) else counts.head(5)).index.tolist()
        out[col] = sorted(values) if col == "brand" else values  # others: most common first
    return out


def train_model(df: pd.DataFrame, cleaning: dict, source: str, demo: bool = False, quick: bool = False, seed: int = 42) -> dict:
    if len(df) < 100:
        raise ValueError("Need at least 100 clean rows to train a model.")
    X, y = df[FEATURES], df["selling_price"].to_numpy(dtype=float)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=seed)

    rows, oof, fitted = [], {}, {}
    for name, est in candidates(quick).items():
        pipe = build_pipeline(est)
        oof[name] = cross_val_predict(pipe, X_tr, y_tr, cv=5)  # honest predictions on rows each model never saw
        fitted[name] = build_pipeline(est).fit(X_tr, y_tr)
        cv, test = score(y_tr, oof[name]), score(y_te, fitted[name].predict(X_te))
        rows.append({"model": name, "cv_mae": cv["mae"], "cv_mdape": cv["mdape"], "test_mae": test["mae"], "test_mdape": test["mdape"]})

    best = min((r for r in rows if r["model"] != BASELINE), key=lambda r: r["cv_mdape"])["model"]

    # Price range: how far off was the model on cars it hadn't seen? Use the middle 80% of those errors.
    ratios = y_tr / oof[best]
    lo, hi = np.quantile(ratios, [(1 - INTERVAL_LEVEL) / 2, 1 - (1 - INTERVAL_LEVEL) / 2])
    pred_te = fitted[best].predict(X_te)
    coverage = float(np.mean((y_te >= lo * pred_te) & (y_te <= hi * pred_te)))  # checked on the untouched test set

    final = build_pipeline(candidates(quick)[best]).fit(X, y)  # ship a model that has seen all the data

    typical = {"age": int(df.age.median()), "km_driven": int(df.km_driven.median())}
    typical.update({c: str(df[c].mode()[0]) for c in CATEGORICAL})
    ranges = {
        "age_max": int(df.age.max()), "km_p99": int(df.km_driven.quantile(0.99)),
        "year_min": int(df.year.min()), "year_max": int(df.year.max()),
    }
    info = {
        "model": best, "source": source, "demo": bool(demo), "trained_rows": int(len(df)),
        "ref_year": int(cleaning["ref_year"]), "cleaning": cleaning, "comparison": rows,
        "interval": {"level": INTERVAL_LEVEL, "low_ratio": float(lo), "high_ratio": float(hi), "test_coverage": coverage},
        "typical": typical, "ranges": ranges,
    }
    return {"model": final, "info": info, "options": category_options(df), "typical": typical, "ranges": ranges}


def save_artifact(artifact: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "carworth.joblib")
    joblib.dump(artifact, path)
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(artifact["info"], f, indent=2)
    return path
