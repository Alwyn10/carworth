"""Turn a trained model into something a person can use: a price, a range, reasons, and a forecast."""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .data import CATEGORICAL, FEATURES


class Estimator:
    def __init__(self, artifact: dict):
        self.model = artifact["model"]
        self.info = artifact["info"]
        self.options = artifact["options"]
        self.typical = artifact["typical"]
        self.ranges = artifact["ranges"]

    @classmethod
    def load(cls, path: str) -> "Estimator":
        return cls(joblib.load(path))

    def _predict(self, rows: list[dict]) -> np.ndarray:
        return self.model.predict(pd.DataFrame(rows, columns=FEATURES))

    def estimate(self, car: dict, current_year: int, asking_price: int | None = None) -> dict:
        age = max(0, current_year - int(car["year"]))
        base = {
            "age": age, "km_driven": int(car["km_driven"]), "brand": car["brand"], "fuel": car["fuel"],
            "seller_type": car["seller_type"], "transmission": car["transmission"], "owner": car["owner"],
        }
        # For the forecast, assume the car keeps being driven at its own average pace (within sensible limits).
        annual_km = float(np.clip(base["km_driven"] / max(age, 1), 4_000, 25_000))
        swaps = [dict(base, **{feat: self.typical[feat]}) for feat in FEATURES]
        future = [dict(base, age=age + t, km_driven=int(base["km_driven"] + t * annual_km)) for t in (1, 2, 3)]

        preds = self._predict([base] + swaps + future)  # one batch: the car, 7 "what if typical" cars, 3 future cars
        price = float(preds[0])
        swap_prices, future_prices = preds[1 : 1 + len(FEATURES)], preds[1 + len(FEATURES) :]

        # "Why this price": swap one detail for the typical value and see how far the price moves.
        factors = sorted(
            ({"feature": f, "value": base[f], "effect": float(price - p)} for f, p in zip(FEATURES, swap_prices)),
            key=lambda x: abs(x["effect"]), reverse=True,
        )
        shown = [f for f in factors if abs(f["effect"]) >= 0.005 * price][:4] or factors[:2]

        iv = self.info["interval"]
        low, high = price * iv["low_ratio"], price * iv["high_ratio"]
        verdict = None
        if asking_price:
            label = "good_deal" if asking_price < low else "overpriced" if asking_price > high else "fair"
            verdict = {"label": label, "asking": int(asking_price), "difference_pct": float((asking_price - price) / price)}

        forecast = [{"years": 0, "price": price}] + [{"years": t, "price": float(p)} for t, p in zip((1, 2, 3), future_prices)]
        return {
            "price": price,
            "range": {"low": float(low), "high": float(high), "level": iv["level"], "test_coverage": iv["test_coverage"]},
            "verdict": verdict, "factors": shown, "forecast": forecast,
            "retained": float(future_prices[-1] / price), "annual_km": annual_km,
            "warnings": self._warnings(base),
        }

    def _warnings(self, car: dict) -> list[str]:
        out = []
        if car["age"] > self.ranges["age_max"]:
            out.append(f"This car is older than any in the training data (oldest: {self.ranges['age_max']} years), so treat the estimate with extra caution.")
        if car["km_driven"] > self.ranges["km_p99"]:
            out.append("This car has driven more kilometres than almost every car in the training data, so the estimate is less reliable.")
        for col in CATEGORICAL:
            if car[col] not in self.options.get(col, []):
                out.append(f"“{car[col]}” is rare or missing in the training data, so it may not affect the estimate correctly.")
        return out
