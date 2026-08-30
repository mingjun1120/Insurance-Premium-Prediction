# Why the data and the model live outside git

`models/model.pkl` is 2,710,118 bytes, and `uv run main.py` writes a new one
every time it finishes.

Commit that file and git keeps both copies. Then three, then twenty. Two
pickles from two training runs differ all the way through, so there is no small
diff to store and each commit adds close to the whole 2.7 MB. Deleting the file
later frees nothing, because the earlier versions are still in the history —
that is what a history is for. Getting them back out means rewriting every
commit that came after, which changes every commit id anybody has already
pulled.

Nothing about that repository is broken. It is just heavier after every
training run, and the weight is a file whose diff no human will ever read.

## What DVC puts there instead

DVC — Data Version Control — is a command-line tool that sits beside git and
takes those directories off its hands. It hashes the contents, keeps the actual
bytes somewhere else, and leaves a small text file behind. The text file is what
git commits. `data.dvc` is the whole of it:

```yaml
outs:
- md5: 322756809ac53695367784cbff6cd5b0.dir
  size: 179490
  nfiles: 4
  hash: md5
  path: data
```

Six lines, and they change only when the contents change. The md5 is a
fingerprint of the directory; `size` and `nfiles` describe what it should hold.
The bytes themselves go to the remote named in `.dvc/config`, which here is a
container called `dvcstore` in an Azure Blob Storage account called
`insurancedvc`. `dvc pull` reads the pointer, asks the remote for the matching
fingerprint, and writes the files back onto disk.

The useful consequence is that git still versions the model, at one remove.
Check out a commit from three weeks ago and `models.dvc` comes back with it,
naming the exact artefact that commit's numbers were measured on. Git holds the
version. DVC holds the bytes.

## Worth it for one directory, less so for the other

`models.dvc` records 5,420,143 bytes across two files. `models/model.pkl` is
one of them, and it is the only one anything loads — `steps/predict.py:29`
builds its path by name. The other, `random_forest_insurance_model.pkl`, is
2,710,025 bytes that no code and no test refers to, and looks like a leftover
from notebook 03. Half of what the remote carries is dead weight, and DVC will
carry it faithfully until somebody deletes it.

`data.dvc` records 179,490 bytes across four files. That is small. It would
have gone into git and nobody would have noticed: the CSVs are text, the
largest is 55 KB, and they change rarely.

It is in DVC anyway, for consistency — one remote and one command for
everything that is not source code. That is a defensible preference rather than
a requirement, and it is not free. Anyone who clones this repository now needs
access to a private storage account before they can read a 55 KB CSV. If your
data is small and stable, leaving it in git is the friendlier answer. The model
is the only file here that actually forced the decision.

## Two config files, and one of them is never committed

`.dvc/config` is five lines:

```ini
[core]
    remote = azureremote
['remote "azureremote"']
    url = azure://dvcstore
    account_name = insurancedvc
```

An address, and nothing else. The connection string that opens the account
lives in `.dvc/config.local`, and DVC wrote a `.gitignore` inside `.dvc/`
naming that file, so it cannot be committed by accident. Ask git what it tracks
in that directory and it answers with two paths: the `.gitignore` and `config`.

The split is worth stating plainly, because the instinct is to treat the whole
of `.dvc/` as sensitive. It is not. Reading this repository tells you the
account is called `insurancedvc` and the container `dvcstore`, and that gets a
stranger nowhere — Azure refuses them exactly as politely as it refuses
everyone else.

The omission does something less obvious as well. On a CI runner
`.dvc/config.local` does not exist at all, so DVC has an account name and no
credential, and rather than failing it goes looking for an identity elsewhere.
That is how the deploy workflow pulls a private model without a password
stored anywhere;
[deploying-without-secrets.md](deploying-without-secrets.md) follows that
thread.

## What a fresh clone gets

The pointers, and none of the bytes.

`/data` and `/models` are both listed in `.gitignore`, so a clone arrives with
neither directory. Three things then do not work, and they break in three
different ways. `app.py:27` builds its `Predictor` when the module is imported,
so the API fails at import rather than on the first request. The test suite
runs, and 28 of its tests skip with a reason naming the file they wanted —
which is deliberate, and [the-test-suite.md](the-test-suite.md) argues for it.
And `docker build` stops at `COPY models/ ./models/`, because the model enters
the image from the host's disk or not at all.

Someone with access to the storage account fixes all three with one command,
and [how-to/pull-data-and-models.md](../how-to/pull-data-and-models.md) is that
command. Everyone else trains their own model from the raw data — a Kaggle
account, the notebooks, and a full training run — which is a longer road that
ends in the same place: a real `models/model.pkl`, which the API, the tests and
the image are all equally satisfied by.

## The half that is rented

Git will keep `models.dvc` for as long as the repository exists. Its md5 will
always record which artefact belonged to which commit, and that record costs
nothing to store and cannot expire.

The bytes it names sit in a storage account on a free trial that runs out
around 2026-09-25. When it lapses, the pointer will still be perfectly
accurate, and there will be nothing at the other end of it.

That is the trade this arrangement actually makes, and it is easy to miss while
the account is alive. Git gives permanence away for free because it keeps
everything, which is the same property that made the model unwelcome in it.
Moving the model out buys a repository that stays small, and hands the
permanence question to whoever is paying the storage bill.
