# Deploy to your own Azure

You already have a container registry, a resource group, a container app and the
storage account your DVC remote uses, plus a fork of this repository.

> **Written from configuration, not re-walked.** Every name, role and variable
> below is read out of `.github/workflows/cd.yml` and the README's role table.
> The steps have not been run again on a fresh subscription. Treat the Azure CLI
> lines as the shape of the work, not as a transcript, and expect to correct a
> name or two as you go.

This guide creates the identity the deploy runs as. Why that identity needs no
stored secret, and why its roles are narrow rather than `Contributor`, are in
[deploying-without-secrets.md](../explanation/deploying-without-secrets.md).

## 1. Create the app registration

```bash
az ad app create --display-name insurance-premium-cd --query appId -o tsv
```

Keep the `appId` it prints. Steps 2, 3 and 4 all need it.

Give the registration a service principal in your tenant:

```bash
az ad sp create --id <appId>
```

## 2. Pin a federated credential to your repository and branch

Put the credential in a file, `credential.json`:

```json
{
  "name": "github-master",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<owner>@<owner-id>/<repository>@<repository-id>:ref:refs/heads/master",
  "audiences": ["api://AzureADTokenExchange"]
}
```

```bash
az ad app federated-credential create --id <appId> --parameters @credential.json
```

A file rather than inline JSON, because the quoting rules differ between bash
and PowerShell.

`<owner>` and `<repository>` are your fork's, spelled exactly as GitHub spells
them. The two numeric IDs come from the API:

```bash
gh api users/<owner> --jq .id
gh api repos/<owner>/<repository> --jq .id
```

This is the immutable subject format, which GitHub gives new repositories by
default. `README.md:396` records this project's own subject in that shape. A
repository created before July 2026 may still present the older
`repo:<owner>/<repository>:ref:...` form, with no IDs. Use whichever one your
repository actually sends.

The branch is `master` because `cd.yml:17` deploys from `master` and from
nowhere else. Another branch, a pull request, or a fork of your fork presents a
different subject, and Entra refuses it. If the login step fails later, its
error names the subject GitHub actually presented. Copy that string into the
credential.

## 3. Assign the four roles

Three go to the app registration. The fourth goes to the container app, which
reads its own image at start-up.

- [ ] `AcrPush` on the registry, to `<appId>`
- [ ] `Storage Blob Data Reader` on the storage account, to `<appId>`
- [ ] `Container Apps Contributor` on the container app, to `<appId>`
- [ ] `AcrPull` on the registry, to the container app's own identity

Collect the three scope IDs:

```bash
az acr show --name <registry> --query id -o tsv
az storage account show --name <storage-account> --query id -o tsv
az containerapp show --name <container-app> --resource-group <resource-group> \
  --query id -o tsv
```

Assign the first three:

```bash
az role assignment create --assignee <appId> \
  --role "AcrPush" --scope <registry-id>
az role assignment create --assignee <appId> \
  --role "Storage Blob Data Reader" --scope <storage-id>
az role assignment create --assignee <appId> \
  --role "Container Apps Contributor" --scope <container-app-id>
```

The fourth needs the container app's principal:

```bash
az containerapp show --name <container-app> --resource-group <resource-group> \
  --query identity.principalId -o tsv
```

An empty answer means the app has no managed identity yet. Give it one:

```bash
az containerapp identity assign --name <container-app> \
  --resource-group <resource-group> --system-assigned
```

Then:

```bash
az role assignment create --assignee <principalId> \
  --role "AcrPull" --scope <registry-id>
```

A `403` from `dvc pull` on the runner means row two of the checklist is missing,
even when the same identity is `Owner` on the storage account. The reason is in
[deploying-without-secrets.md](../explanation/deploying-without-secrets.md).

## 4. Set the three repository variables

These are variables, not secrets. In your fork, open **Settings → Secrets and
variables → Actions**, choose the **Variables** tab, and add three:

| Variable | Value |
| --- | --- |
| `AZURE_CLIENT_ID` | the `appId` from step 1 |
| `AZURE_TENANT_ID` | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | `az account show --query id -o tsv` |

`cd.yml:47-49` reads all three as `vars.*`. A value stored on the Secrets tab is
not read there, and `azure/login` receives an empty string instead.

## 5. Point the workflow at your own resources

`cd.yml:31-34` hard-codes four names:

```yaml
REGISTRY: insurancemlops.azurecr.io
IMAGE: insurance-api
RESOURCE_GROUP: rg-insurance-mlops
CONTAINER_APP: insurance-premium-api
```

Replace all four with yours. The registry name occurs a second time at
`cd.yml:73`, inside `az acr login --name insurancemlops`, where the `REGISTRY`
variable does not reach. Change that one too.

`.dvc/config` still names the storage account `insurancedvc`. Set `account_name`
to yours, or `dvc pull` at `cd.yml:62` asks for a remote your identity holds no
role on.

## 6. Run the deploy

Push to `master`, or start the workflow by hand — `cd.yml:18` accepts
`workflow_dispatch`.

Watch the smoke test at `cd.yml:95-120`. The run goes green only after the live
service returns a number, and the log's last line has this shape:

```
predicted premium 18095.88 - looks like dollars
```

The job summary then carries the URL:

```
### Deployed :rocket:

https://<your-app>.<region>.azurecontainerapps.io/docs

Sample prediction: **$18095.88**
```

Open that `/docs` page and send one prediction. An answer in dollars, out of
your own subscription, means the credential, the four roles and the three
variables are all correct.
