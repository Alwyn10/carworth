"""Loading and cleaning the used-car listings, and defining the model's features."""
from __future__ import annotations

import pandas as pd

REQUIRED = ["name", "year", "selling_price", "km_driven", "fuel", "seller_type", "transmission", "owner"]
NUMERIC = ["age", "km_driven"]
CATEGORICAL = ["brand", "fuel", "seller_type", "transmission", "owner"]
FEATURES = NUMERIC + CATEGORICAL
BRAND_FIXES = {"Land": "Land Rover"}  # the listing names split "Land Rover" into two words


def brand_from_name(name: str) -> str:
    first = str(name).strip().split(" ")[0]
    return BRAND_FIXES.get(first, first)


def clean_data(raw: pd.DataFrame, max_km: int = 500_000, min_price: int = 10_000):
    """Return (clean dataframe with 'age' and 'brand', a report of what was dropped)."""
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"The CSV is missing these columns: {', '.join(missing)}")

    df = raw[REQUIRED].copy()
    report = {"rows_in": int(len(df))}
    for col in ("year", "selling_price", "km_driven"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before = len(df)
    df = df.dropna()
    report["dropped_missing"] = int(before - len(df))

    for col in ("name", "fuel", "seller_type", "transmission", "owner"):
        df[col] = df[col].astype(str).str.strip()

    # The public CarDekho file repeats many listings. Duplicates must go, or the same car
    # can land in both the training and the test set and make the results look better than they are.
    before = len(df)
    df = df.drop_duplicates()
    report["dropped_duplicates"] = int(before - len(df))

    plausible = (
        (df.selling_price >= min_price) & (df.km_driven >= 0) & (df.km_driven <= max_km) & (df.year >= 1990)
    )
    report["dropped_implausible"] = int((~plausible).sum())
    df = df[plausible].copy()
    if df.empty:
        raise ValueError("No usable rows are left after cleaning. Check that the CSV is the right file.")

    df["year"] = df["year"].astype(int)
    df["km_driven"] = df["km_driven"].astype(int)
    ref_year = int(df["year"].max())  # the year the listings were collected, as far as the data shows
    df["age"] = ref_year - df["year"]
    df["brand"] = df["name"].map(brand_from_name)
    report.update(ref_year=ref_year, rows_out=int(len(df)))
    return df.reset_index(drop=True), report
