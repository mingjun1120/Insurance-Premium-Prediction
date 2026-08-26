"""FastAPI service that serves the trained model over HTTP.

The model is loaded once, when the process starts, and never reloaded. If
`models/model.pkl` is missing the import fails immediately and loudly - which is
what you want in a container, because a server that starts without a model would
only fail later, on a real request.

All the work of turning features into dollars belongs to `steps.predict`, not to
this file. That includes undoing the log transform, ordering the columns and
setting the `category` dtype. Keeping it there means this API cannot disagree
with what `main.py` reports.
"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from steps.predict import Predictor

app = FastAPI(
    title="Insurance Premium Prediction",
    description="Predicts annual medical insurance charges in US dollars.",
    version="1.0.0",
)

predictor = Predictor()


class Person(BaseModel):
    """One person to price.

    Every limit below comes from the training data, not from a guess. A model
    asked about a 90 year old has never seen one, and would answer confidently
    anyway - rejecting the request is more honest than returning a number nobody
    should trust.

    Attributes:
        age (int): Years. Training data covers 18 to 64.
        sex (str): "female" or "male".
        bmi (float): Body mass index. Training data covers 15.96 to 53.13,
            widened slightly to 15-55 so values a hair outside are not rejected
            on a technicality.
        children (int): Dependants covered. Training data covers 0 to 5.
        smoker (str): "yes" or "no". By far the strongest driver of the premium.
        region (str): One of the four US regions in the data.
    """

    age: int = Field(ge=18, le=64, examples=[19])
    sex: Literal["female", "male"] = Field(examples=["female"])
    bmi: float = Field(ge=15, le=55, examples=[27.9])
    children: int = Field(ge=0, le=5, examples=[0])
    smoker: Literal["yes", "no"] = Field(examples=["yes"])
    region: Literal["northeast", "northwest", "southeast", "southwest"] = Field(
        examples=["southwest"]
    )


class Prediction(BaseModel):
    """What the service sends back.

    Attributes:
        predicted_premium (float): Annual charges, in dollars.
        currency (str): Always "USD"; the dataset is American.
        model (str): Which of the five models produced this, taken from the
            saved artefact rather than hardcoded, so it stays true after a
            retrain with a different `config.yml`.
    """

    predicted_premium: float
    currency: str
    model: str


@app.get("/")
async def health():
    """Report that the service is up and say what it is serving.

    Returns:
        dict: `status`, the model name, and whether the model was fitted on
        log-transformed charges.
    """
    return {
        "status": "ok",
        "model": predictor.model_name,
        "log_target": predictor.use_log_target,
    }


@app.post("/predict", response_model=Prediction)
async def predict(person: Person):
    """Predict one person's annual insurance charges.

    Args:
        person (Person): The six features. FastAPI rejects anything outside the
            ranges above with a 422 before this function runs.

    Returns:
        Prediction: The predicted premium in dollars, plus the model that made
        it.

    Examples:
        >>> # curl -X POST http://127.0.0.1:8000/predict \\
        >>> #   -H "Content-Type: application/json" \\
        >>> #   -d '{"age":19,"sex":"female","bmi":27.9,
        >>> #        "children":0,"smoker":"yes","region":"southwest"}'
        {"predicted_premium": 18095.88, "currency": "USD",
         "model": "RandomForestRegressor"}
    """
    premium = predictor.predict_records([person.model_dump()])[0]

    return Prediction(
        predicted_premium=round(premium, 2),
        currency="USD",
        model=predictor.model_name,
    )
