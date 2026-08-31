# Pull the data and the models

You already have `uv sync` done — and a key to the `insurancedvc` storage account.

That second half is the real precondition. The remote is private. If you cannot
open that storage account in the Azure portal, nothing in this guide will work,
and no edit to `.dvc/config` will change that. The other road is longer and ends
in the same place: a Kaggle download to `data/insurance.csv`, then
`notebooks/01_load_data.ipynb`, then `uv run main.py`. Why the project is split
this way is in [data-outside-git.md](../explanation/data-outside-git.md).

## 1. Copy the connection string out of the portal

Azure portal → storage account **`insurancedvc`** → **Security + networking** →
**Access keys** → **Show** → **Connection string**.

One long line, starting `DefaultEndpointsProtocol=https;AccountName=insurancedvc;AccountKey=`.
It is a password. Do not paste it into a file git can see.

## 2. Write it to the local config

```bash
uv run dvc remote modify --local azureremote connection_string "<paste it here>"
```

Nothing is printed. Exit code 0. It writes `.dvc/config.local`:

```ini
['remote "azureremote"']
    connection_string = DefaultEndpointsProtocol=https;AccountName=insurancedvc;AccountKey=...
```

`--local` is the flag that matters. Drop it and the string lands in `.dvc/config`,
which git tracks. Keep it and the string lands in `.dvc/config.local`, which
`.dvc/.gitignore` excludes by name.

## 3. Pull

```bash
uv run dvc pull
```

```
A       data\
A       models\
8 files fetched and 6 files added
```

Around four seconds for 5.6 MB. The six files added are the four CSVs under
`data/` and the two pickles under `models/`. The two extra objects fetched are
the directory listings behind `data.dvc` and `models.dvc`.

Run it again on a machine that is already current and it says
`Everything is up to date.` instead.

## 4. Check the remote agrees

```bash
uv run dvc status --cloud
```

```
Cache and remote 'azureremote' are in sync.
```

That sentence is the check. Anything else is a list of what is missing.

## If it fails

**`AuthorizationPermissionMismatch`.** Step 2 did not take, or the key is stale.

```
ERROR: failed to connect to azure (dvcstore/files/md5) - Operation returned an invalid status 'This request is not authorized to perform this operation using this permission.'
ErrorCode:AuthorizationPermissionMismatch
ERROR: failed to pull data from the cloud - 8 files failed to download
```

With no connection string in `.dvc/config.local`, DVC falls back to
`DefaultAzureCredential` and uses whatever `az login` left behind. That identity
can reach the account and still be refused the blobs, which is what the message
above is. Re-run step 2.

**`getaddrinfo failed`.** The account name in `.dvc/config` does not resolve. See
the box below.

> **What went wrong**
>
> **Symptom** — `uv run dvc pull` dies on DNS, naming an account that was never
> created:
>
> ```
> ERROR: failed to connect to azure (dvcstore/files/md5) - Cannot connect to host insurancedvc1120.blob.core.windows.net:443 ssl:default [getaddrinfo failed]: [Errno 11001] getaddrinfo failed
> ERROR: failed to pull data from the cloud - 8 files failed to download
> ```
>
> Commit `e2477ad` records the fix but no error text. The message above was
> reproduced by putting the old name back — and it only appears when
> `.dvc/config.local` is absent. With a connection string in place, DVC reads
> the account name out of that string and never consults `account_name` at all,
> so the wrong value sits there working perfectly. That is how it survived to be
> committed.
>
> **Cause** — `insurancedvc1120` was written into `.dvc/config` as a placeholder
> before anyone checked the name was free. Storage account names are globally
> unique across all of Azure, so the name you plan for is often not the name you
> get. The account that actually got created is `insurancedvc`.
>
> **Fix** — one line in `.dvc/config`, and the same string again in the README's
> portal instructions. The name lives in more than one place. The region was
> wrong too (`malaysiawest`, not `southeastasia`), but region appears nowhere in
> DVC's config, so nothing needed changing there.
>
> **Cost** — two string edits in two files. No data moved and no published number
> shifted.
>
> **The lesson** — provision first, then write the config from what exists. Not
> the other way round.

## The account has an expiry date

The storage account sits on a free trial with $200 of credit, valid 30 days from
sign-up — around **2026-09-25**, and the portal has the exact date. When it
lapses, Azure decommissions the resources and every command on this page stops
working, for everyone including the author. Upgrading to pay-as-you-go before
then costs a fraction of a cent per month at 5.5 MB.

## Done when

`uv run dvc status --cloud` prints `Cache and remote 'azureremote' are in sync.`,
and `ls data models` shows four CSVs and two pickles.

Recording a model you have just trained is the other direction —
[record-a-new-model-version.md](record-a-new-model-version.md). Every DVC command
the project uses is tabulated in [reference/commands.md](../reference/commands.md).
