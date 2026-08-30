# The saved artefact is a bundle, not a model

Most training scripts end on one line:

```python
joblib.dump(model, "model.pkl")
```

Write that line here, and the web service built on top of the file answers about
**9.7** for a person whose premium is about **$16,000**. Wrong by a factor of
roughly 1,600.

Nothing crashes. Nothing warns. `9.7` is a perfectly good number, the response
is valid JSON — the text format requests and replies travel in — and the status
code is 200. The only way to catch it is to already know what a premium looks
like.

joblib is the library that writes a fitted Python object to disk and reads it
back later. Delete it and the model exists only inside the process that trained
it: there is nothing for the service to load, and every restart means training
from scratch.

The reason for 9.7 is that the model was fitted on `log1p(charges)` — see
[the-log-transform.md](the-log-transform.md) for why that is the right thing to
do. The prediction is correct. It is simply not in dollars, and nothing about a
float carrying the value 9.7 says which of the two it is.

That is the actual problem. A bare pickle does not carry the one fact you need
in order to read its own output.

## What the file holds instead

`steps/train.py:279-285` hands `joblib.dump` a dictionary of six keys rather
than the model. `steps/predict.py:31-36` unpacks all six back out. The full
table — every key, its type, an example value, the line that writes it and the
line that reads it — lives in
[reference/artefact-bundle.md](../reference/artefact-bundle.md). What matters
here is what those keys stop from happening.

### `use_log_target`

`steps/predict.py:72` reads:

```python
return np.expm1(predicted) if self.use_log_target else predicted
```

`np.expm1` is numpy's exact inverse of `log1p`. The line is a conditional, and
the condition arrives from the artefact rather than from `config.yml`.

That distinction is the point. Set `use_log_target: false`, retrain, and the new
artefact says so about itself; the same unchanged `steps/predict.py` stops
inverting. No edit to `app.py`, no redeploy of anything except the model file. A
prediction is always interpreted the way *its own* model was fitted, not the way
the config file happens to read on the day someone loads it.

### `feature_order` and `categorical_features`

`app.py` is the web service — FastAPI, the library that turns Python functions
into HTTP endpoints (HTTP being the protocol a browser speaks) and
validates incoming JSON against a schema before any project code runs. Delete
FastAPI and the model has no door: predictions are available only to whoever can
run Python inside the repository.

What `app.py` conspicuously does not do is state the model's column order.
`steps/predict.py:74` builds the frame with `columns=self.feature_order`, read
straight out of the artefact. The order is not written down twice, so the two
copies cannot disagree.

`categorical_features` then names the columns that must carry pandas' `category`
dtype. pandas is the library that gives Python a table of named, typed columns —
the DataFrame — and without it there is no object to hand a fitted pipeline at
all. The dtype is not decoration: LightGBM, XGBoost and CatBoost, the three
gradient-boosting libraries this project can train instead of the random forest,
read category columns natively and require it. Delete all three and
`config.yml:22` drops from five model choices to two, and this key has almost
nothing left to do.

Key one is a scikit-learn `Pipeline` — a single fitted object holding
preprocessing and estimator together. That is what lets one serving path cover
every model: without scikit-learn's pipeline, the preprocessing would have to be
repeated by hand in `app.py`, which is exactly the drift these keys exist to
prevent.

So one `app.py` serves all five models. Change `config.yml:22` from
`RandomForestRegressor` to `CatBoostRegressor`, retrain, and the serving code
needs no edit whatsoever: the new artefact brings its own name, its own column
order, its own categorical list, and its own answer to whether the output still
needs `expm1`.

## A flag is a promise, not a check

All of that still depends on people. `use_log_target` prevents the error only
for as long as nobody deletes the conditional at `steps/predict.py:72` — and
that deletion would break nothing that raises, pass every type check, and return
a plausible float. Something has to be watching for it on purpose.

Something is. `tests/conftest.py:109-145` builds `fake_bundle`: a five-tree
forest, trained and saved as a genuine six-key bundle into a temporary
directory, which is how the prediction tests exercise the log-transform logic on
a fresh clone with no access to the real artefact. See
[the-test-suite.md](the-test-suite.md).

And then the same question gets asked once more, after everything has been
built, pushed and deployed — this time to the running service rather than to a
fixture.

## The last check

`cd.yml` is the continuous-deployment workflow, run by GitHub Actions, the
service that executes these workflow files automatically when a branch moves.
Delete it and nothing between a merge and the public service happens without
someone typing it.

Its final step sends the sample person to the deployed URL and reads
`predicted_premium` back out of the response. Then, at `cd.yml:117-119`:

```yaml
# log1p dollars would come back around 9.8 rather than five figures
ok=$(python -c "p=float('$premium'); print(1 if 1000 < p < 200000 else 0)")
[ "$ok" = "1" ] || { echo "::error::$premium is not dollars - has the expm1 been lost?"; exit 1; }
```

The comment says 9.8 where this page has been saying 9.7; the exact figure
depends on which person you price. Neither of them is dollars, which is the only
thing the check cares about.

The window from 1,000 to 200,000 is deliberately enormous. It is not measuring
accuracy — a thoroughly bad model sails through it, and
[deploy-gates.md](deploy-gates.md) covers the gate that does check accuracy. It
is measuring units. A deploy that reports success while quietly serving log
dollars is worse than one that fails outright, so the run does not go green
until the live service has returned a number that could plausibly be money.
