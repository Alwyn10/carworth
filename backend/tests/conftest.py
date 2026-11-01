import pytest
from fastapi.testclient import TestClient

from app.data import clean_data
from app.main import create_app
from app.modeling import save_artifact, train_model
from app.predict import Estimator
from app.synthetic import make_synthetic_cars


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    """Train once on made-up data (small models) and reuse for every test."""
    df, report = clean_data(make_synthetic_cars())
    artifact = train_model(df, report, "synthetic demo data", demo=True, quick=True)
    path = save_artifact(artifact, str(tmp_path_factory.mktemp("models")))
    return {"artifact": artifact, "path": path, "report": report}


@pytest.fixture(scope="session")
def estimator(trained):
    return Estimator(trained["artifact"])


@pytest.fixture()
def client(trained):
    with TestClient(create_app(trained["path"])) as c:
        yield c


CAR = {"brand": "Maruti", "year": 2016, "km_driven": 60_000, "fuel": "Petrol",
       "seller_type": "Individual", "transmission": "Manual", "owner": "First Owner"}
