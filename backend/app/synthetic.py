"""Made-up listings so the app can run before you download the real CarDekho file.

The numbers follow simple rules I wrote down, so they are NOT real prices. Anything trained on this
is labelled "demo data" in the interface.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BASE_PRICE = {
    "Maruti": 450_000, "Hyundai": 600_000, "Honda": 850_000, "Toyota": 1_200_000,
    "Mahindra": 950_000, "Tata": 550_000, "BMW": 3_000_000, "Ford": 700_000,
}


def make_synthetic_cars(n: int = 2500, seed: int = 7, messy: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    brands = rng.choice(list(BASE_PRICE), n, p=[0.28, 0.18, 0.1, 0.1, 0.1, 0.1, 0.04, 0.1])
    age = rng.integers(1, 15, n)
    km = (age * rng.lognormal(np.log(11_000), 0.35, n)).astype(int)
    fuel = rng.choice(["Petrol", "Diesel", "CNG"], n, p=[0.5, 0.42, 0.08])
    trans = rng.choice(["Manual", "Automatic"], n, p=[0.85, 0.15])
    seller = rng.choice(["Individual", "Dealer"], n, p=[0.8, 0.2])
    owner = rng.choice(["First Owner", "Second Owner", "Third Owner", "Fourth & Above Owner"], n, p=[0.6, 0.28, 0.09, 0.03])

    base = np.array([BASE_PRICE[b] for b in brands], dtype=float)
    owner_n = np.array([["First Owner", "Second Owner", "Third Owner", "Fourth & Above Owner"].index(o) for o in owner])
    price = (
        base * np.exp(-0.11 * age) * np.exp(-km / 450_000)
        * np.where(fuel == "Diesel", 1.15, 1.0) * np.where(trans == "Automatic", 1.1, 1.0)
        * np.where(seller == "Dealer", 1.05, 1.0) * 0.94 ** owner_n * rng.lognormal(0, 0.12, n)
    )
    df = pd.DataFrame({
        "name": [f"{b} Model{k} Variant" for b, k in zip(brands, rng.integers(1, 6, n))],
        "year": 2020 - age, "selling_price": price.round(-3), "km_driven": km,
        "fuel": fuel, "seller_type": seller, "transmission": trans, "owner": owner,
    })
    if messy:  # a few bad rows, so the cleaning step has something to do
        dirt = df.head(30).copy()
        bad = df.iloc[30:34].copy()
        bad.iloc[0, bad.columns.get_loc("km_driven")] = -5
        bad.iloc[1, bad.columns.get_loc("selling_price")] = 0
        bad.iloc[2, bad.columns.get_loc("km_driven")] = np.nan
        bad.iloc[3, bad.columns.get_loc("year")] = np.nan
        df = pd.concat([df, dirt, bad], ignore_index=True)
    return df
