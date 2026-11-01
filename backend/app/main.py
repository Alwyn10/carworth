import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .predict import Estimator

NOT_TRAINED = (
    "The model has not been trained yet. Run the training command from the README, then restart the server."
)


class EstimateIn(BaseModel):
    brand: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=1990)
    km_driven: int = Field(ge=0, le=1_000_000)
    fuel: str = Field(min_length=1, max_length=30)
    seller_type: str = Field(min_length=1, max_length=40)
    transmission: str = Field(min_length=1, max_length=30)
    owner: str = Field(min_length=1, max_length=40)
    asking_price: int | None = Field(default=None, ge=0, le=1_000_000_000)

    @field_validator("brand", "fuel", "seller_type", "transmission", "owner")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()

    @field_validator("year")
    @classmethod
    def not_in_future(cls, v: int) -> int:
        if v > date.today().year + 1:
            raise ValueError("The model year cannot be in the future.")
        return v


def create_app(model_path: str | None = None) -> FastAPI:
    path = model_path or os.getenv("CARWORTH_MODEL", "models/carworth.joblib")
    app = FastAPI(title="CarWorth")
    app.state.estimator = Estimator.load(path) if os.path.exists(path) else None

    def need_model() -> Estimator:
        if app.state.estimator is None:
            raise HTTPException(503, NOT_TRAINED)
        return app.state.estimator

    @app.get("/api/health")
    def health():
        return {"status": "ok", "model_loaded": app.state.estimator is not None}

    @app.get("/api/options")
    def options():
        est = need_model()
        return {**est.options, "typical": est.typical, "ranges": est.ranges}

    @app.get("/api/model-info")
    def model_info():
        return need_model().info

    @app.post("/api/estimate")
    def estimate(body: EstimateIn):
        est = need_model()
        car = body.model_dump(exclude={"asking_price"})
        return est.estimate(car, current_year=date.today().year, asking_price=body.asking_price)

    static = Path(__file__).parent / "static"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    return app


app = create_app()
