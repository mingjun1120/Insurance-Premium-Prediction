# GitHub Actions workflows

Two files in `.github/workflows/`, split by whether the run needs an Azure
identity.

| Workflow | File | Triggers | Needs Azure | Typical run |
| --- | --- | --- | --- | --- |
| CI | `ci.yml`, 47 lines | push to `master`; any pull request | no | ~30s |
| CD | `cd.yml`, 128 lines | push to `master`; manual `workflow_dispatch` | yes | ~3.5 min |

Durations are the observed range over the last eight runs of each: 28-30s for
CI, 204-213s for CD.

## A push to `dev` runs nothing

`ci.yml:12-15` triggers on pushes to `master` and on pull requests.
`cd.yml:15-18` triggers on pushes to `master` and on manual dispatch. Neither
lists any other branch.

A direct push to `dev`, or to any other branch, therefore starts no workflow at
all. On those branches the checks run when a pull request is opened, not when a
commit lands.

---

## `ci.yml`

| | |
| --- | --- |
| Name | `CI` (`ci.yml:10`) |
| Job | `quality` — "Lint and test", `ubuntu-latest` (`ci.yml:22-25`) |
| Concurrency | group `ci-${{ github.ref }}`, `cancel-in-progress: true` (`ci.yml:18-20`) |
| Secrets used | none |

| # | Step | Command or action | Line |
| --- | --- | --- | --- |
| 1 | Checkout | `actions/checkout@v7` | 28 |
| 2 | Install uv | `astral-sh/setup-uv@v10.0.1`, `enable-cache: true` | 30-34 |
| 3 | Install dependencies | `uv sync --frozen` | 38-39 |
| 4 | Lint | `uv run ruff check .` | 41-42 |
| 5 | Test | `uv run pytest -v` | 46-47 |

Notes recorded in the file itself:

- The `setup-uv` version is pinned exactly because astral-sh stopped publishing
  a floating `v10` tag (`ci.yml:31`).
- `--frozen` fails if `uv.lock` disagrees with `pyproject.toml` (`ci.yml:36-37`).
- `-v` is passed to pytest so each skipped test and its reason appear in the log
  rather than as a count (`ci.yml:44-45`).

No `dvc pull` runs, so `models/` and `data/` are absent and the tests that need
them skip. See [test-suite.md](test-suite.md).

---

## `cd.yml`

| | |
| --- | --- |
| Name | `CD` (`cd.yml:13`) |
| Job | `deploy` — "Build, test and deploy", `ubuntu-latest` (`cd.yml:36-39`) |
| Permissions | `id-token: write`, `contents: read` (`cd.yml:20-22`) |
| Concurrency | group `cd-master`, `cancel-in-progress: false` (`cd.yml:26-28`) |
| Secrets used | none |

`cancel-in-progress` is false because a cancelled `containerapp update` can
leave the app pointing at an image that was never pushed (`cd.yml:24-25`).

### Environment

| Variable | Value | Line |
| --- | --- | --- |
| `REGISTRY` | `insurancemlops.azurecr.io` | 31 |
| `IMAGE` | `insurance-api` | 32 |
| `RESOURCE_GROUP` | `rg-insurance-mlops` | 33 |
| `CONTAINER_APP` | `insurance-premium-api` | 34 |

### Steps

| # | Step | Command or action | Line |
| --- | --- | --- | --- |
| 1 | Checkout | `actions/checkout@v7` | 42 |
| 2 | Log in to Azure | `azure/login@v3` with three `vars` | 44-49 |
| 3 | Install uv | `astral-sh/setup-uv@v10.0.1`, `enable-cache: true` | 51-54 |
| 4 | Install dependencies | `uv sync --frozen` | 56-57 |
| 5 | Fetch the model and data | `uv run dvc pull` | 61-62 |
| 6 | Test | `uv run pytest` | 64-65 |
| 7 | Check the model still scores | `uv run pytest -m slow` | 69-70 |
| 8 | Log in to the registry | `az acr login --name insurancemlops` | 72-73 |
| 9 | Build and push | `docker build`, then `docker push` for both tags | 77-84 |
| 10 | Point the app at the new image | `az containerapp update --image …:${{ github.sha }}` | 86-91 |
| 11 | Smoke test the deployed app | `curl` the live URL, check the premium | 95-120 |
| 12 | Write the run summary | appends to `$GITHUB_STEP_SUMMARY` | 122-128 |

Steps 7 and 11 can fail the run on the model rather than on the build. They are
described in [../explanation/deploy-gates.md](../explanation/deploy-gates.md).

### Repository variables

Three values are configured as repository **variables**, not secrets
(`cd.yml:47-49`):

```
AZURE_CLIENT_ID  AZURE_TENANT_ID  AZURE_SUBSCRIPTION_ID
```

No repository secret is referenced anywhere in either workflow. Why an identifier
is sufficient is
[../explanation/deploying-without-secrets.md](../explanation/deploying-without-secrets.md).

`dvc pull` at step 5 also runs without a credential: `.dvc/config` carries only
`account_name`, so DVC falls back to `DefaultAzureCredential`, which picks up the
`az login` from step 2 (`cd.yml:8-11`).

### Role assignments

Four assignments, three on the pipeline's identity and one on the app's.

| Identity | Role | Scope | Purpose |
| --- | --- | --- | --- |
| the pipeline | `AcrPush` | registry | upload the built image |
| the pipeline | `Storage Blob Data Reader` | storage account | let `dvc pull` read the model |
| the pipeline | `Container Apps Contributor` | the container app | point it at the new tag |
| the app | `AcrPull` | registry | read its own image at start-up |

`Owner` and `Contributor` on a storage account do not grant access to the blobs
inside it; blob access is a separate data-plane role family.

### Image tags

Every build is pushed under two tags (`cd.yml:79-84`):

| Tag | Form | Purpose |
| --- | --- | --- |
| commit sha | `${{ github.sha }}` | every running revision maps to exactly one commit |
| `latest` | `latest` | convenience for pulling by hand |

Step 10 updates the container app using the sha tag, never `latest`, so the
running revision is always traceable to the code that produced it. The full form:

```
insurancemlops.azurecr.io/insurance-api:4a536c32d99c5fcf15708b14da3d4a6b045e3425
```

### Smoke test details

| | |
| --- | --- |
| Readiness check | `GET /` until HTTP 200, 10 attempts, `sleep 15` between, `curl -m 60` (`cd.yml:104-109`) |
| Prediction check | `POST /predict` with the sample person, reads `predicted_premium` (`cd.yml:112-115`) |
| Accepted range | `1000 < p < 200000` (`cd.yml:118`) |
| On failure | `::error::the app never returned 200`, or `::error::<premium> is not dollars - has the expm1 been lost?` |
| On success | `predicted premium <value> - looks like dollars`, and the value is written to the run summary |
