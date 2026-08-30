# API reference

Two endpoints, defined in `app.py`. The service is FastAPI, served by uvicorn.
Interactive documentation is generated at `/docs`.

The application object is built at `app.py:21-25` with title
`Insurance Premium Prediction`, description
`Predicts annual medical insurance charges in US dollars.`, and version `1.0.0`.

`predictor = Predictor()` runs at module level (`app.py:27`). The model is loaded
once at import and never reloaded. A missing `models/model.pkl` fails the import
rather than the first request.

---

## `GET /`

Health check. No parameters, no request body.

**200 response**

```json
{"status": "ok", "model": "RandomForestRegressor", "log_target": true}
```

| Field | Type | Source |
| --- | --- | --- |
| `status` | string | Literal `"ok"` (`app.py:84`) |
| `model` | string | `predictor.model_name`, read from the artefact |
| `log_target` | boolean | `predictor.use_log_target`, read from the artefact |

Both non-literal fields come from the saved bundle, so they describe the model
actually loaded. See [artefact-bundle.md](artefact-bundle.md).

---

## `POST /predict`

One person in, one premium out. Request body is JSON, all six fields required.

### Request schema — `Person` (`app.py:30-56`)

| Field | Type | Constraint | Example |
| --- | --- | --- | --- |
| `age` | integer | `ge=18`, `le=64` | `19` |
| `sex` | string | `"female"` or `"male"` | `"female"` |
| `bmi` | float | `ge=15`, `le=55` | `27.9` |
| `children` | integer | `ge=0`, `le=5` | `0` |
| `smoker` | string | `"yes"` or `"no"` | `"yes"` |
| `region` | string | `"northeast"`, `"northwest"`, `"southeast"`, `"southwest"` | `"southwest"` |

`sex`, `smoker` and `region` are `typing.Literal` enums; `age`, `bmi` and
`children` are bounded by `pydantic.Field`.

### Where each limit comes from

| Field | Accepted | Provenance |
| --- | --- | --- |
| `age` | 18–64 | the exact range in the training data |
| `bmi` | 15–55 | training data covers 15.96–53.13, widened so values just outside are not rejected on a technicality |
| `children` | 0–5 | the exact range in the training data |
| `sex` | 2 values | the only values present |
| `smoker` | 2 values | the only values present |
| `region` | 4 values | the only values present |

Recorded in the `Person` docstring (`app.py:31-47`). The reasoning is in
[../explanation/architecture.md](../explanation/architecture.md).

### Request body

```json
{"age": 19, "sex": "female", "bmi": 27.9, "children": 0, "smoker": "yes", "region": "southwest"}
```

### 200 response — `Prediction` (`app.py:59-72`)

```json
{"predicted_premium": 18095.88, "currency": "USD", "model": "RandomForestRegressor"}
```

| Field | Type | Value |
| --- | --- | --- |
| `predicted_premium` | float | Annual charges in dollars, rounded to 2 decimal places (`app.py:113`) |
| `currency` | string | Always `"USD"` |
| `model` | string | `predictor.model_name`, from the artefact rather than hardcoded |

The dollar figure is produced by `Predictor.predict_records`
(`steps/predict.py:74`), which rebuilds the frame from the bundle's
`feature_order`, applies the `category` dtype to the bundle's
`categorical_features`, and inverts the log transform at
`steps/predict.py:72` before returning.

### 422 response

Validation failures are rejected by FastAPI before `predict()` runs. The body is
pydantic's standard error list.

Numeric bound, `age: 90`:

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "age"],
      "msg": "Input should be less than or equal to 64",
      "input": 90,
      "ctx": {"le": 64}
    }
  ]
}
```

Enum, `region: "scotland"`:

```json
{
  "detail": [
    {
      "type": "literal_error",
      "loc": ["body", "region"],
      "msg": "Input should be 'northeast', 'northwest', 'southeast' or 'southwest'",
      "input": "scotland",
      "ctx": {"expected": "'northeast', 'northwest', 'southeast' or 'southwest'"}
    }
  ]
}
```

`detail` is a list; one entry per failing field.

---

## Status codes

| Code | Condition |
| --- | --- |
| 200 | Request valid; prediction returned |
| 422 | One or more fields missing, wrong type, or outside the constraints above |

The service defines no other responses. A failure to load
`models/model.pkl` prevents the process from starting, so it surfaces as a
startup error rather than as an HTTP status.
