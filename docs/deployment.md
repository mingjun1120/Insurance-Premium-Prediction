# Deployment

`Guide 5 of 5` · [Getting started](getting-started.md) →
[Architecture](architecture.md) → [Model development](model-development.md) →
[Operations](operations.md) → **Deployment**

The model is served by FastAPI, packaged with Docker, and deployed by GitHub
Actions to Azure Container Apps.

![Deployment flow](diagrams/deployment-flow.svg)

## Run the serving image locally

The model must exist before the build because the Dockerfile copies it into the
image.

```bash
uv run dvc pull
docker build -t insurance-premium .
docker run --rm -p 8000:8000 insurance-premium
```

Open <http://127.0.0.1:8000/docs>.

The Dockerfile has two stages:

- **Builder:** creates `.venv` with serving dependencies only.
- **Runtime:** installs `libgomp1`, copies the environment, API code, config,
  steps, and model bundle, then starts Uvicorn on port 8000.

Training tools such as DVC, MLflow, Jupyter, Evidently, and SHAP are not inside
the serving image. The three boosting libraries remain because any one of their
models may be stored in `model.pkl`.

## CI and CD are separate

| Workflow | Trigger | Credentials | Work |
| --- | --- | --- | --- |
| `.github/workflows/ci.yml` | Push to `master`, any pull request | None | Frozen install, Ruff, fast tests. |
| `.github/workflows/cd.yml` | Push to `master`, manual dispatch | Azure OIDC | DVC pull, fast and slow tests, build, push, deploy, smoke test. |

A push to another branch does not start either push workflow. A pull request
still starts CI.

## The deployment gate

CD stops before image creation if any of these fail:

1. Azure OIDC login;
2. dependency installation from `uv.lock`;
3. DVC data and model pull;
4. fast tests;
5. slow real-data golden test.

After deployment, the workflow asks the live service for:

- `GET /` until it returns HTTP 200;
- one `POST /predict` result;
- a premium between `$1,000` and `$200,000`.

The last range is a simple guard against accidentally returning log-space
values. It is not a business rule.

## Image traceability

Every build is pushed with two tags:

```text
insurancemlops.azurecr.io/insurance-api:<git-commit-sha>
insurancemlops.azurecr.io/insurance-api:latest
```

Azure Container Apps is updated with the commit-SHA tag. This makes the running
revision traceable even when `latest` later moves.

## Azure resources expected by the workflow

The committed CD file names these resources:

| Setting | Current value |
| --- | --- |
| Registry | `insurancemlops.azurecr.io` |
| Image | `insurance-api` |
| Resource group | `rg-insurance-mlops` |
| Container app | `insurance-premium-api` |
| DVC storage account | `insurancedvc` |
| DVC blob container | `dvcstore` |

The temporary portfolio endpoint is
[Swagger UI](https://insurance-premium-api.ambitiousgrass-8ecc70a2.malaysiawest.azurecontainerapps.io/docs).
It uses an Azure trial expected to end around 25 September 2026. Use the local
instructions when it is offline.

## Identity and access

GitHub uses OpenID Connect. No long-lived Azure client secret is stored in the
repository.

The GitHub deployment identity needs:

| Role | Scope | Used for |
| --- | --- | --- |
| `AcrPush` | Container registry | Push images. |
| `Storage Blob Data Reader` | DVC storage account | Pull data and model files. |
| `Container Apps Contributor` | Container app | Update the image. |

The container app’s own managed identity needs `AcrPull` on the registry.

Three GitHub repository variables feed `azure/login`:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
```

They are variables, not passwords. Store them under **Settings → Secrets and
variables → Actions → Variables**.

## Use the workflow in a fork

This is a checklist, not a full Azure tutorial:

1. Create your registry, resource group, container app, and DVC storage.
2. Create an Entra application and service principal.
3. Add a federated credential restricted to your repository and `master`
   branch.
4. Assign the three roles in the table above to that service principal, and
   give the container app’s managed identity `AcrPull` on the registry.
5. Add the three repository variables.
6. Replace the hard-coded resource names in `.github/workflows/cd.yml` and the
   storage account in `.dvc/config`.
7. Push to `master` or run CD manually.

Azure and GitHub identity formats can change. If login fails, compare the
subject in the error with the federated credential rather than guessing.

## Rollback

Each deployment creates a Container Apps revision. A previous revision can be
reactivated in Azure, but the repository does not automate that action.

Before rollback, record:

- the bad commit SHA;
- the last healthy image SHA;
- whether DVC pointers changed;
- whether the API or the model-quality gate failed.

That is the end of the path. For any command, config key, API field, or file,
use the [Reference](reference.md).
