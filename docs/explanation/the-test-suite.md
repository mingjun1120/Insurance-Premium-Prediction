# A suite that skips instead of failing

Clone this repository onto a machine with no Azure account, install the
dependencies and run the tests. This comes back:

```
80 passed, 28 skipped, 1 deselected, 135 warnings in 3.96s
```

Twenty-eight skips looks like a broken checkout. On the machine this page was
written on, where `models/model.pkl` and `data/merged_data.csv` are both sitting
on disk, the same command reports something else:

```
108 passed, 1 deselected, 2836 warnings in 6.07s
```

Same commit, same suite, two answers, and neither one is a failure. The
`1 deselected` is the same single test in both runs, and it has a section to
itself at the end.

## Two kinds of test in one directory

pytest — the tool that finds these files and runs them — reports three outcomes
rather than two. Passed, failed, and skipped, where skipped means the test
declined to run and said why.

The suite is 812 lines across six files, and the split that matters does not
follow the file boundaries. `tests/conftest.py:1-17` states it in the module's
own docstring.

**Self-contained tests** build whatever they need — a small table, or a model
fitted on fifty invented rows — and run anywhere.

**Artefact tests** need the real `models/model.pkl` or `data/merged_data.csv`.
Both are DVC-tracked and git-ignored, so on a fresh checkout neither one is
there at all. For why they live outside git, see
[data-outside-git.md](data-outside-git.md).

The mechanism is two lines, at `tests/conftest.py:33-40`:

```python
requires_model = pytest.mark.skipif(
    not MODEL_FILE.exists(),
    reason="models/model.pkl is DVC-tracked and absent here - run `uv run dvc pull`",
)
```

The reason string is not decoration. pytest prints it, so the 28 skips are not
28 silences: each one names the file it wanted and the command that fetches it.

`tests/test_api.py` skips as a whole file rather than test by test —
`pytestmark = requires_model`, applied at module level. That is not tidiness.
`app.py:27` builds its `Predictor` when the module is imported, so importing the
module is itself the operation that needs the artefact. There is no smaller unit
left to skip.

## What the split buys

The alternative is to let those 28 fail.

Then a pull request from a fork is red before anybody reads it, and red for a
reason that has nothing to do with the change in it. `ci.yml` was written so
that cannot happen (`ci.yml:3-6`). The workflow holds no credential and pulls
nothing, and it still gets 80 real results out of a runner with no subscription
attached to it.

The second thing the split buys takes longer to become visible. The Azure trial
behind this project expires around 2026-09-25. After that `dvc pull` stops
answering, and 28 tests skip on every machine, including the one this page was
written on. The suite still runs. It still means something. A suite wired to
fail without the storage account would become 28 permanent red marks, and then
somebody would delete it.

## What it costs

A skip is not a pass. Twenty-eight tests that did not run tell you nothing, and
a suite reporting 80 green on a laptop is not evidence that the artefact tests
would have passed there.

What makes that survivable is one guaranteed run. `cd.yml:62` pulls the
artefacts before `cd.yml:65` runs the suite, so on the path between a merge and
the live service nothing is skipped. That is a property of the deploy pipeline
rather than of the tests — [deploy-gates.md](deploy-gates.md) is about the two
gates that enforce it.

That is the condition the whole design rests on, and it is worth stating as one.
If a project has no such stage, nowhere the real artefacts are certain to be
present, then this design quietly halves the coverage and nothing announces it
at all. Fail loudly instead. The
skip earns its place here only because something downstream is guaranteed to run
the same tests with the files on disk.

## Twelve rows that are wrong on purpose

`steps/clean.py` runs seven cleaning rules. The tests for them use none of the
real data, and that is the second decision worth arguing over.

The real insurance data is clean. `tests/test_clean.py:1-10` says so outright:
it arrives with no gaps, no constant columns and no high-cardinality columns.
Point the seven rules at that file and almost none of them fire. The suite goes
green having proved that the code runs, which is a different claim from the code
works.

So the cleaning tests start from `tidy_frame` (`tests/conftest.py:46-67`):
twelve hand-written rows in the project's real schema, ages 19 to 61 and charges
from 1,725.60 to 38,711.00, picked so that nothing trips. Each test then plants
exactly one problem in that frame and checks that exactly one rule fires.

When one of those tests fails, there is one thing it can mean.

The cost lands in the same place as the benefit. `tidy_frame` proves that
`remove_low_variance_constant_features` removes a constant column. It proves
nothing whatsoever about `merged_data.csv`. If the real file grew a column of
nulls tomorrow, no test in `test_clean.py` would notice, because twelve invented
rows do not change when the data does. Catching that is the job of the artefact
tests and of the slow test below, which is why both of them exist rather than
the cleaning tests being the whole story.

Two larger fixtures follow the same principle. `fake_training_data`
(`tests/conftest.py:70-106`) generates fifty rows from a seeded random number
generator, with a crude relationship baked into the charges — 250 per year of
age, 300 per BMI point, a flat 22,000 for smoking, plus noise — so a model
fitted on them has some signal to find instead of pure noise. `fake_bundle`
(`tests/conftest.py:109-145`) fits a five-tree forest on those rows and saves it
as a genuine six-key bundle into a temporary folder.

That last one is why the most expensive mistake in the project is testable on a
laptop that has never seen the real artefact. The prediction tests exercise the
log-transform logic against a bundle they built themselves, with no `dvc pull`
anywhere. See [the-bundle.md](the-bundle.md).

## The one number written down

Everything above tests behaviour: given this input, does the code do what it
says. `tests/test_predict.py:149` asks something else.

```python
assert rmse == pytest.approx(4193, abs=1)
assert mae == pytest.approx(1974, abs=1)
assert r2 == pytest.approx(0.9043, abs=0.0001)
assert mape == pytest.approx(0.1655, abs=0.0001)
```

It cleans the real data, splits it the way training splits it, scores the
shipped model on the test half, and holds four numbers up against four numbers
recorded earlier. No behaviour is being checked. The question is whether the
model still scores what it scored.

The first kind of test cannot answer that one. A change that leaves every other
assertion green and moves RMSE by several hundred dollars is invisible to all of
them, and that is the class of bug this test exists to catch: a silent change in
behaviour that raises nothing, breaks nothing, and shows up only against a
number somebody wrote down before it happened. The project has had one of those,
and the tutorial's Chapter 3b tells that story.

This test is the `1 deselected`. It carries the `slow` marker, and
`pyproject.toml:57` carries `addopts = "-m 'not slow'"`, so it does not run
unless it is asked for by name. It gets asked on the deploy path, at
`cd.yml:69-70`, before anything is built or pushed.

The four numbers are allowed to move. Point `config.yml:22` at a different
model, or turn tuning on, and RMSE moves for a good reason. The test then fails,
correctly, and the expected values are edited as part of the same commit that
moved them — the procedure is in
[../how-to/run-the-tests.md](../how-to/run-the-tests.md). The tolerance is
`abs=1`, so nothing here demands that a floating-point number reproduce bit for
bit. It demands that the model has not become a different model without anybody
saying so.

A number that can never change is not measuring anything. This one is allowed to
change. It is not allowed to change quietly.
