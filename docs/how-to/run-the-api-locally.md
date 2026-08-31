# Run the API locally

You already have `models/model.pkl` on disk and `uv sync` done.

> **`models/model.pkl` is not optional and not lazy.** `app.py:27` builds its
> `Predictor` at module level, so the model loads when the module is imported,
> not on the first request. Without the file the server never starts:
>
> ```
> FileNotFoundError: No model at ...\models\model.pkl. Run main.py to train one first.
> ```
>
> The traceback ends at `steps/predict.py:50`. If you see it, get the artefact
> first — [pull-data-and-models.md](pull-data-and-models.md), or train one with
> `uv run main.py`.

## 1. Start the server

```bash
uv run uvicorn app:app --reload
```

```
INFO:     Will watch for changes in these directories: ['...\Insurance Premium Prediction']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [24764] using WatchFiles
INFO:     Started server process [8048]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

`--reload` restarts the process when a file changes. Drop it if you only want to
send a request.

## 2. Check it is holding a model

```bash
curl http://127.0.0.1:8000/
```

```json
{"status":"ok","model":"RandomForestRegressor","log_target":true}
```

`model` is the name that came out of the artefact, not out of `config.yml`. If
you have switched models and this still says `RandomForestRegressor`, the file on
disk is the old one.

## 3. Send a prediction

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":19,"sex":"female","bmi":27.9,"children":0,"smoker":"yes","region":"southwest"}'
```

```json
{"predicted_premium":18095.88,"currency":"USD","model":"RandomForestRegressor"}
```

Or open <http://127.0.0.1:8000/docs> and use the form. Same endpoints, no curl
quoting.

## 4. Paste in a real row

`samples.json` holds three rows from the dataset — the cheapest customer, the
median, and the dearest. Nothing in the code reads the file; it is there so you
always have valid input to hand.

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":18,"sex":"male","bmi":23.21,"children":0,"smoker":"no","region":"southeast"}'
```

```json
{"predicted_premium":1563.9,"currency":"USD","model":"RandomForestRegressor"}
```

The third row — 54, smoker, BMI 47.41 — comes back at `47034.44`. A thirty-fold
spread across three rows is the signal the model was built to price.

## When a request is refused

Out-of-range input returns `422` and never reaches the model. `age: 90` is
refused; so is `bmi: 60`, and `region: "central"`. The bounds and the exact
error shape are in [reference/api.md](../reference/api.md).

## Done when

`GET /` returns `"status":"ok"`, and the `POST /predict` above returns
`18095.88` — a four- or five-figure dollar amount, not a number near 9.8. Why
9.8 is the shape a broken answer takes is in
[the-bundle.md](../explanation/the-bundle.md).

Stop the server with `Ctrl+C`.
