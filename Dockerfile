# Serving image for the FastAPI app. Training, MLflow and DVC are deliberately
# left out - see the `dev` group in pyproject.toml.
#
# Build with:   docker build -t insurance-premium .
# Run with:     docker run --rm -p 8000:8000 insurance-premium
#
# models/model.pkl must exist on disk before building. It is DVC-tracked and
# gitignored, so on a fresh clone run `uv run dvc pull` first. The alternative -
# running `dvc pull` inside the build - would bake the Azure connection string
# into an image layer, where anyone with the image can read it.

# ---------------------------------------------------------------------------
# Stage 1: build the virtualenv.
#
# Split in two so that uv itself (58 MB) never reaches the final image. Only
# the finished .venv is copied across.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# uv comes from its own published image rather than a pip install, so the
# version is pinned and no extra Python packages are pulled in to get it.
COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /usr/local/bin/uv

# Write .pyc files at build time so the first request is not slowed by
# compiling, and copy rather than hardlink because the cache mount and the
# target live on different filesystems.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./

# --no-dev drops 217 of the 257 packages: MLflow, DVC, SHAP, seaborn, sweetviz
# and JupyterLab. None of them are used to answer a request.
#
# The uninstall removes 288 MB of NVIDIA CUDA libraries. XGBoost's Linux wheel
# declares nvidia-nccl-cu13 as a dependency, but NCCL only does multi-GPU
# communication - this container has no GPU. Verified: XGBoost trains and
# predicts normally without it. It has to happen in this same RUN, otherwise
# the files stay in the layer below and nothing is reclaimed.
RUN uv sync --frozen --no-dev \
    && uv pip uninstall --python /app/.venv/bin/python nvidia-nccl-cu13

# ---------------------------------------------------------------------------
# Stage 2: the image that actually ships.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# LightGBM, XGBoost and CatBoost all link against the OpenMP runtime. The full
# python image ships it; slim does not, and the import fails with a bare
# "libgomp.so.1: cannot open shared object file" that says nothing about why.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY app.py config.yml ./
COPY steps/ ./steps/
COPY models/ ./models/

# Put the virtualenv first on PATH so `uvicorn` resolves without `uv run`.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
