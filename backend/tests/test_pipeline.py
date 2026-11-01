import pandas as pd
import pytest

from app.data import brand_from_name, clean_data
from app.modeling import BASELINE
from app.synthetic import make_synthetic_cars
from tests.conftest import CAR


def test_brand_from_name():
    assert brand_from_name("Maruti Swift Dzire VDI") == "Maruti"
    assert brand_from_name("Land Rover Discovery") == "Land Rover"


def test_cleaning_drops_bad_rows_and_duplicates():
    raw = make_synthetic_cars(n=500)
    df, report = clean_data(raw)
    assert report["dropped_duplicates"] >= 30      # the synthetic data repeats 30 listings on purpose
    assert report["dropped_missing"] >= 2           # two rows with a missing number
    assert report["dropped_implausible"] >= 2       # negative km, price of zero
    assert df.duplicated().sum() == 0 and (df.km_driven >= 0).all() and (df.selling_price > 0).all()
    assert report["rows_out"] == len(df) and (df.age >= 0).all()


def test_cleaning_explains_missing_columns():
    with pytest.raises(ValueError, match="missing these columns"):
        clean_data(pd.DataFrame({"name": ["a"], "year": [2015]}))


def test_training_compares_four_models_and_beats_the_baseline(trained):
    info = trained["artifact"]["info"]
    assert len(info["comparison"]) == 4 and info["model"] != BASELINE
    by_name = {r["model"]: r for r in info["comparison"]}
    assert by_name[info["model"]]["test_mdape"] < by_name[BASELINE]["test_mdape"] / 2


def test_price_range_is_sensible_and_holds_on_unseen_cars(trained):
    iv = trained["artifact"]["info"]["interval"]
    assert iv["low_ratio"] < 1 < iv["high_ratio"]
    assert 0.6 <= iv["test_coverage"] <= 0.95      # aimed at 80%, checked on cars the range never saw


def test_older_and_higher_mileage_cars_cost_less(estimator):
    young = estimator.estimate(dict(CAR, year=2018, km_driven=30_000), 2020)["price"]
    old = estimator.estimate(dict(CAR, year=2008, km_driven=150_000), 2020)["price"]
    assert old < young * 0.6


def test_verdict_follows_the_price_range(estimator):
    base = estimator.estimate(CAR, 2020)
    low, high = base["range"]["low"], base["range"]["high"]
    assert estimator.estimate(CAR, 2020, int(low * 0.8))["verdict"]["label"] == "good_deal"
    assert estimator.estimate(CAR, 2020, int(base["price"]))["verdict"]["label"] == "fair"
    assert estimator.estimate(CAR, 2020, int(high * 1.3))["verdict"]["label"] == "overpriced"
    assert base["verdict"] is None


def test_forecast_declines_and_factors_are_explained(estimator):
    out = estimator.estimate(dict(CAR, brand="BMW", year=2019), 2020)
    prices = [p["price"] for p in out["forecast"]]
    assert [p["years"] for p in out["forecast"]] == [0, 1, 2, 3] and prices == sorted(prices, reverse=True)
    assert 0.3 < out["retained"] < 1
    assert 1 <= len(out["factors"]) <= 4
    brand = next(f for f in out["factors"] if f["feature"] == "brand")
    assert brand["effect"] > 0                       # a BMW costs more than the typical car


def test_warnings_for_cars_outside_the_training_data(estimator):
    assert estimator.estimate(CAR, 2020)["warnings"] == []
    far = estimator.estimate(dict(CAR, year=1995, km_driven=900_000, brand="Tesla"), 2020)
    assert len(far["warnings"]) == 3
