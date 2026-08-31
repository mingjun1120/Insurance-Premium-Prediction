# Check for drift

You already have `models/model.pkl` and `data/merged_data.csv` on disk. The
notebook trains nothing, but cell 5.2 builds a `Predictor` and an `Ingestion`,
so both artefacts have to be there —
[pull-data-and-models.md](pull-data-and-models.md).

## 1. Open the notebook

```bash
uv run jupyter lab notebooks/04_monitoring.ipynb
```

Run it top to bottom. Nothing prompts and nothing needs editing. About 20
seconds end to end, most of it inside Evidently building the two HTML files.

## 2. Watch for three checkpoints

The first cell tells you where its output is going:

```
Project root : ...\Insurance Premium Prediction
Reports go to: ...\Insurance Premium Prediction\reports
```

Section 5.3 writes the file it compares against:

```
Wrote ...\data\production.csv  (400 rows, charges withheld)
```

`SEED = 42` is pinned, so this file comes out identical every run.
`uv run dvc status` stays on `Data and pipelines are up to date.` afterwards —
running the notebook does not put you out of sync.

Sections 5.5 and 5.6 each save a report:

```
Saved baseline_drift.html  (4.2 MB)
Saved production_drift.html  (4.1 MB)
```

Both land in `reports/`, which is gitignored and overwritten on every run.

| Report | Compares |
| --- | --- |
| `baseline_drift.html` | train split against test split |
| `production_drift.html` | train split against `data/production.csv` |

Open them in a browser. They do not render inline — section 5.5 has a note on
why.

## 3. Read the share, not the column

Section 5.7 prints a summary for each report before its table:

```
=== A: reference vs current (expect no drift) ===
  3 of 8 columns drifted (share 37.5%; dataset drift is declared at 50%)
  9 of 75 tests failed
```

**The share on that line is the number to act on.** One column crossing its
threshold is not a result — at a few hundred rows, single columns cross on noise
alone. Compare the share against 50% first.

Each summary is followed by its own table, for diagnosis once the share has told
you something moved. Comparison B's:

```
       column                         method   score  threshold verdict
0  prediction  Wasserstein distance (normed)  0.5153        0.1   DRIFT
1         bmi  Wasserstein distance (normed)  0.4499        0.1   DRIFT
2         age  Wasserstein distance (normed)  0.3721        0.1   DRIFT
3      region        Jensen-Shannon distance  0.1374        0.1   DRIFT
4      smoker        Jensen-Shannon distance  0.0969        0.1      ok
5    children  Wasserstein distance (normed)  0.0517        0.1      ok
6         sex        Jensen-Shannon distance  0.0120        0.1      ok
```

Read each score against its own threshold and nothing else. The `method` column
is there for a reason: Evidently picks Wasserstein distance for numeric columns
and Jensen-Shannon for categorical ones. Two scores from different methods are
not on the same scale. Do not rank them against each other.

## Done when

`reports/` holds two HTML files timestamped from this run, and section 5.7 has
printed a drifted-columns share for both comparisons.

What the numbers mean, why the production file is invented, and what to do when
the share does cross 50% are all in
[drift-monitoring.md](../explanation/drift-monitoring.md).
