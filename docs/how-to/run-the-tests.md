# Run the tests

You already have `uv sync` done. Nothing else — the suite runs on a fresh clone.

## 1. Run the default suite

```bash
uv run pytest
```

```
============== 108 passed, 1 deselected, 2836 warnings in 5.79s ===============
```

The one deselected test is the golden-number test, held back by
`addopts = "-m 'not slow'"` in `pyproject.toml`. Step 3 runs it.

## 2. Read which of the two outcomes you got

The tail line tells you what your machine has on disk.

| Tail line | What it means |
| --- | --- |
| `108 passed, 1 deselected` | `models/model.pkl` and `data/merged_data.csv` are both present. Everything ran. |
| `80 passed, 28 skipped, 1 deselected` | One or both artefacts are missing. The 28 that need them skipped; the other 80 still ran. |

Twenty-eight skips is not a failure and not a broken install. Add `-rs` to print
each skip with its reason:

```
=========================== short test summary info ===========================
SKIPPED [1] tests\test_api.py:34: models/model.pkl is DVC-tracked and absent here - run `uv run dvc pull`
SKIPPED [1] tests\test_api.py:40: models/model.pkl is DVC-tracked and absent here - run `uv run dvc pull`
```

Every skip names the file it wanted. Nothing goes quietly missing.

To turn 28 skips into 28 passes, fetch the artefacts —
[pull-data-and-models.md](pull-data-and-models.md). Why the suite skips instead
of failing is in [the-test-suite.md](../explanation/the-test-suite.md).

## 3. Run the golden-number test

```bash
uv run pytest -m slow
```

```
=============== 1 passed, 108 deselected, 900 warnings in 3.62s ===============
```

This one runs the whole pipeline against the real data, so it needs both
artefacts. Without them it skips rather than passes.

`tests/test_predict.py:173-176` holds the four numbers it checks:

```python
assert rmse == pytest.approx(4193, abs=1)
assert mae == pytest.approx(1974, abs=1)
assert r2 == pytest.approx(0.9043, abs=0.0001)
assert mape == pytest.approx(0.1655, abs=0.0001)
```

Run it after changing anything about training, cleaning or the artefact format.

## 4. When the golden number moves

A failure looks like this:

```
FAILED tests/test_predict.py::test_golden_rmse_has_not_moved - assert 4350.84... == 4193 ± 1
```

Two cases, and you have to decide which one you are in before touching the file.

**You did not mean to change the model's behaviour.** The number moving is the
finding. Do not update the assertion — find what moved it.

**You did mean to.** Retuned parameters, a changed cleaning rule, a different
model in `config.yml`. Then:

1. Read the four numbers off the failure output.
2. Edit `tests/test_predict.py:173-176` to the new values.
3. Commit the assertion change **in the same commit** as the change that moved
   it, and say in the message why the number moved.

Split across two commits, the history stops being able to answer *when did RMSE
change, and what did it*. That is the only question a golden number exists to
answer.

Switching models in `config.yml` will trip this test — see
[switch-models.md](switch-models.md).

## Done when

`uv run pytest` ends in `108 passed, 1 deselected` (or `80 passed, 28 skipped`
if you have not pulled the artefacts), and `uv run pytest -m slow` ends in
`1 passed`.

The full inventory of files, markers and fixtures is in
[reference/test-suite.md](../reference/test-suite.md).
