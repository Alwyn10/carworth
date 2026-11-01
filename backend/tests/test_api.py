from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import CAR


def test_health_and_options(client):
    assert client.get("/api/health").json() == {"status": "ok", "model_loaded": True}
    options = client.get("/api/options").json()
    assert "Maruti" in options["brand"] and "Petrol" in options["fuel"] and "typical" in options


def test_estimate_returns_everything_the_interface_needs(client):
    r = client.post("/api/estimate", json=dict(CAR, asking_price=500_000))
    assert r.status_code == 200
    body = r.json()
    for key in ("price", "range", "verdict", "factors", "forecast", "retained", "annual_km", "warnings"):
        assert key in body
    assert body["verdict"]["label"] in {"good_deal", "fair", "overpriced"}


def test_estimate_without_asking_price_has_no_verdict(client):
    assert client.post("/api/estimate", json=CAR).json()["verdict"] is None


def test_estimate_rejects_bad_input(client):
    assert client.post("/api/estimate", json=dict(CAR, year=2999)).status_code == 422
    assert client.post("/api/estimate", json=dict(CAR, km_driven=-1)).status_code == 422
    assert client.post("/api/estimate", json={"brand": "Maruti"}).status_code == 422


def test_clear_message_when_model_is_missing(tmp_path):
    with TestClient(create_app(str(tmp_path / "nope.joblib"))) as c:
        assert c.get("/api/health").json()["model_loaded"] is False
        r = c.post("/api/estimate", json=CAR)
        assert r.status_code == 503 and "trained" in r.json()["detail"]


def test_model_info_is_transparent(client):
    info = client.get("/api/model-info").json()
    assert info["demo"] is True and len(info["comparison"]) == 4 and "cleaning" in info


def test_the_page_itself_is_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "CarWorth" in page.text
    assert client.get("/app.js").status_code == 200 and client.get("/styles.css").status_code == 200
