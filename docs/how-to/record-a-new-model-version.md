# Record a new model version

You already have a training run behind you, so `models/model.pkl` on disk is
newer than the one Azure is holding.

Git will not notice. `/models` is in `.gitignore`, so `git status` stays clean
while the artefact underneath it changes. Recording the new version is three
commands, and they have to run in this order.

## 0. Confirm there is something to record

```bash
uv run dvc status
```

```
models.dvc:
	changed outs:
		modified:           models
```

`Data and pipelines are up to date.` means the run produced a byte-identical
model and there is nothing to do.

## 1. DVC — hash the new files

```bash
uv run dvc add data models
```

```
To track the changes with git, run:

	git add data.dvc models.dvc

To enable auto staging, run:

	dvc config core.autostage true
```

This rewrites `models.dvc` with the new md5 and copies the artefact into
`.dvc/cache/`. Nothing has left your machine yet.

`dvc add models` takes the **whole directory**, so anything sitting in it gets
versioned too. A stray backup file will show up as `nfiles: 3` in `models.dvc`
where you expected 2. Check that number if the size looks wrong.

## 2. Git — commit the new pointer

```bash
git add data.dvc models.dvc
git commit -m "..."
```

`git status` now has something to show, because the pointer file did change:

```
 M models.dvc
```

The commit is what ties this model to this revision of the code. Say in the
message what moved the model — a config change, new data, retuned parameters.

## 3. Azure — upload the file

```bash
uv run dvc push
```

Skip this one and everything still looks fine. The commit succeeded, `git
status` is clean, the tests pass. But `models.dvc` now points at a file that
exists on exactly one computer. The next person to run `dvc pull` gets an error,
and so do you on your next machine.

## 4. Check

```bash
uv run dvc status --cloud
```

Before the push, the remote tells you exactly what it is missing:

```
	new:                models
	new:                models\model.pkl
```

After it:

```
Cache and remote 'azureremote' are in sync.
```

Run `dvc push` again on a synced repository and it answers
`Everything is up to date.` — safe to repeat whenever you are unsure.

## Done when

`uv run dvc status --cloud` prints `Cache and remote 'azureremote' are in sync.`,
and `git log -1 --stat` lists `models.dvc` among the changed files.

Fetching in the other direction is
[pull-data-and-models.md](pull-data-and-models.md). Changing which model gets
trained is [switch-models.md](switch-models.md) — and note that a new model will
trip the golden-number test, which
[run-the-tests.md](run-the-tests.md) covers.
