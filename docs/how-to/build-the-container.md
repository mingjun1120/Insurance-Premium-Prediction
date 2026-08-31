# Build the container

You already have `models/model.pkl` on disk and a Docker daemon running.

> **The artefact must exist before you build.** `Dockerfile:63` is
> `COPY models/ ./models/`, and that copy is the only route the model has into
> the image. `dvc pull` is not run during the build, on purpose. So a build
> started without the file produces an image whose server dies at start-up
> rather than a build that fails — get the artefact first, with
> [pull-data-and-models.md](pull-data-and-models.md) or `uv run main.py`.

## 1. Build

```bash
docker build -t insurance-premium .
```

Two stages, so the last lines you see are the runtime stage assembling:

```
#16 [runtime 5/7] COPY app.py config.yml ./
#17 [runtime 6/7] COPY steps/ ./steps/
#18 [runtime 7/7] COPY models/ ./models/
#19 exporting to image
#19 naming to docker.io/library/insurance-premium 0.0s done
```

The first build pulls `python:3.12-slim` and syncs the whole locked environment.
Later builds reuse both layers and redo only the three `COPY` steps above, which
is why a rebuild after editing `app.py` or `steps/` finishes in seconds.

Why the image is the size it is — the `--no-dev` sync, the CUDA uninstall, why
all five model libraries stay in — is in
[the-serving-image.md](../explanation/the-serving-image.md).

## 2. Run it

```bash
docker run --rm -p 8000:8000 insurance-premium
```

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

The container binds `0.0.0.0` rather than `127.0.0.1`, because a server
listening on loopback inside a container is unreachable from the host. `--rm`
deletes the container when you stop it.

Port 8000 must be free. If `uv run uvicorn` is still running from
[run-the-api-locally.md](run-the-api-locally.md), stop it, or map a different
host port with `-p 8001:8000`.

## 3. Ask the container for a prediction

The same request that works against the local server:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"age":19,"sex":"female","bmi":27.9,"children":0,"smoker":"yes","region":"southwest"}'
```

```json
{"predicted_premium":18095.88,"currency":"USD","model":"RandomForestRegressor"}
```

## If the container exits immediately

Read `docker logs` on it. Two failures account for most of them.

`FileNotFoundError: No model at /app/models/model.pkl` — the file was absent
when you built. Fetch it and rebuild; the `COPY` layer will not be reused.

`libgomp.so.1: cannot open shared object file: No such file or directory` — the
OpenMP runtime is missing. LightGBM, XGBoost and CatBoost all link against it
and `python:3.12-slim` does not ship it. `Dockerfile:53-55` installs `libgomp1`
for exactly this; if you see the error, that apt step has been removed or the
runtime stage has changed base image.

## Done when

The `curl` in step 3 returns `18095.88` against the container — the same figure
the local server gives for the same input. Stop it with `Ctrl+C`.
