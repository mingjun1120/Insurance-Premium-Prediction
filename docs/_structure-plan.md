# Phase 3 — document structure

Plan only. No document is written here.

Sources: `docs/_facts.md` (gathered at `13ed746`), `docs/_tutorial-plan.md`,
`README.md` at 583 lines, and the 41-commit history on `dev`.

**Reader assumed throughout:** has trained a model in a notebook. Has never met
DVC, MLflow, OIDC or drift. Can read Python. Has never deployed anything.

---

## Part A — the two "what went wrong" sidebars

Both get the same six-line shape, so a reader learns to recognise the box:

```
> **What went wrong**
>
> **Symptom** — what you would actually see. No jargon.
> **Cause** — the mechanism, one paragraph.
> **Fix** — the change, as a diff or a single line.
> **Cost** — what had to be redone, and which published numbers moved.
> **The lesson** — one sentence a reader can carry to another project.
```

### Sidebar 1 — CatBoost test-set leak (`f7c61f8`)

**Home:** tutorial Chapter 3b (already placed by the phase 2 plan). One canonical
telling, here and nowhere else.

**Must contain**

- **Symptom:** nothing raised, nothing warned, the notebook ran clean. The only
  tell was a train/test gap of **-$4** — the test set scoring *better* than the
  training set.
- **Cause:** CatBoost sets `use_best_model=True` by default whenever an
  `eval_set` is passed. It kept **167 of 300 trees** — and the iteration it
  stopped at was chosen by the test split. Section 4.8.3 of the notebook claimed
  the eval set was for monitoring only. It was not.
- **Fix:** `use_best_model=False`.
- **Cost:** the gap went from -$4 to **+$156**, and the notebook was re-run, so
  every output below section 4.8 moved with it.
- **Lesson:** a test score better than the training score is not good news. It is
  evidence that the test set touched training.

**Must NOT contain**

- A taxonomy of leakage types. One concrete instance beats a category list.
- A tour of CatBoost's API or its other parameters.
- The log-transform argument or the model comparison — those are 3a and 3c.
- Any suggestion the reader did something wrong. The default did it.

**Cross-referenced from:** `explanation/the-test-suite.md`, in one sentence, as
the bug class the golden-number test exists to catch. That doc links here; it
does not retell the story.

### Sidebar 2 — wrong Azure storage account (`e2477ad`)

**Problem: this sidebar has no chapter to live in.** The phase 2 plan runs seven
chapters and stops at Docker (`6ac9a5e`). Every DVC commit — `516a031`,
`a950eba`, `e2477ad`, `e99766f` — falls outside it. See Part E, gap 1.

**Recommended home:** `how-to/pull-data-and-models.md`, as a boxed aside beside
the step that sets `account_name`. Not inside the imperative steps — a how-to is
a recipe, and a war story interrupts a recipe.

**Must contain**

- **Cause:** the account name was written into `.dvc/config` as a placeholder,
  `insurancedvc1120`, before anyone checked the name was available. The account
  that actually got created is `insurancedvc`. Storage account names are globally
  unique across all of Azure; the name you plan for is often not the name you get.
- **Fix:** one line in `.dvc/config`, plus the same string in the README's portal
  instructions — the name lives in more than one place.
- **Also true, and worth a clause:** the region differed too (`malaysiawest`, not
  `southeastasia`), but region appears nowhere in DVC's config, so nothing needed
  changing there.
- **Lesson:** provision first, then write the config from what exists. Not the
  other way round.

**Must NOT contain**

- **A symptom, unless you supply one.** The commit message records no error text.
  Do not invent the failure mode — a wrong account name could surface as a DNS
  failure, a 403, or a hang, and which one it was is not in the record. Either
  reproduce it and write down the real message, or open on Cause and skip the
  Symptom line. Flagged as an open question in Part F.
- Azure portal navigation. That belongs in the numbered steps above it.
- Anything about the trial expiry — different problem, different box.

### The other fix commits — deliberately not sidebars

`e97d024` (project root from cwd) is already absorbed as a phase 2 correction and
becomes ordinary Chapter 2 code. `f68ca4f` (pin `setup-uv`) is routine. Three
"what went wrong" boxes in seven chapters trains the reader to skip them; two,
spaced far apart, keep their weight.

---

## Part B — diagnosis of the current README

583 lines, all four Diátaxis modes interleaved, sometimes inside one section.

The clearest symptom: **Getting started** (lines 41-99) tells a first-time reader
to run `uv run dvc pull` against a **private storage account they have no
credentials for**, then offers the working path as a fallback paragraph. The
document's happy path is reachable by exactly one person.

Full line-by-line destination map:

| README | Content | Mode today | Goes to |
|---|---|---|---|
| 1-18 | Title, framing, badges, live URL, trial warning | landing | **stays** (hub) |
| 19-40 | Pipeline ASCII diagram | orientation | **stays** + full version in `explanation/architecture.md` |
| 41-50 | `uv sync` | tutorial/how-to | tutorial Ch1; one line in hub quickstart |
| 51-70 | `dvc pull`, Kaggle fallback | how-to + tutorial | `how-to/pull-data-and-models.md`; fallback becomes the hub's *primary* path |
| 71-88 | `main.py`, the commented-out entry point | tutorial + reference | tutorial Ch5/Ch6; `reference/commands.md` |
| 89-99 | `mlflow ui` | how-to | `how-to/inspect-mlflow-runs.md` |
| 100-128 | uvicorn, endpoint table, curl, `samples.json` | how-to + reference | `how-to/run-the-api-locally.md` + `reference/api.md` |
| 129-145 | Validation bounds table + why refusing is honest | reference + explanation | table → `reference/api.md`; the argument → `explanation/architecture.md` |
| 146-156 | API and pipeline share one path | explanation | `explanation/the-bundle.md` |
| 157-181 | Docker build, image size, three savings | how-to + explanation | `how-to/build-the-container.md` + `explanation/the-serving-image.md` |
| 182-196 | What DVC is, why, config vs config.local | explanation + reference | `explanation/data-outside-git.md` + `reference/project-layout.md` |
| 197-205 | Credential setup | how-to | `how-to/pull-data-and-models.md` |
| 206-215 | Five everyday DVC commands | reference | `reference/commands.md` |
| 216-249 | After every training run, the skipped-push trap | how-to + explanation | `how-to/record-a-new-model-version.md`; trap stays as a warning callout |
| 250-269 | What drift is, run the notebook, report table | explanation + how-to + reference | split three ways |
| 270-280 | The production data is simulated | explanation | `explanation/drift-monitoring.md` |
| 281-303 | What it found, the two surprises | explanation | `explanation/drift-monitoring.md` |
| 304-310 | Evidently 0.7 API, `plotly<6` | reference | `reference/configuration.md` (dependency pins) |
| 311-327 | `pytest`, the file-to-guards table | how-to + reference | `how-to/run-the-tests.md` + `reference/test-suite.md` |
| 328-345 | Skip markers, 108 / 80+28 | explanation | `explanation/the-test-suite.md` |
| 346-352 | Cleaning tests use invented data | explanation | `explanation/the-test-suite.md` |
| 353-366 | The golden-number test | explanation + how-to | why → `explanation/the-test-suite.md`; the update procedure → `how-to/run-the-tests.md` |
| 367-375 | Two workflows, trigger table | reference | `reference/workflows.md` |
| 376-388 | CI needs no credentials | explanation | `explanation/deploying-without-secrets.md` |
| 389-414 | OIDC, federated credential, three vars | explanation | `explanation/deploying-without-secrets.md` |
| 415-431 | Three narrow roles, the data-plane 403 | explanation + reference | argument → same doc; role table → `reference/workflows.md` |
| 432-449 | The two deploy gates | explanation | `explanation/deploy-gates.md` |
| 450-458 | sha tags, not `latest` | explanation | `explanation/deploying-without-secrets.md` |
| 459-482 | Switching models, preprocessing table | how-to + reference | `how-to/switch-models.md` + `reference/configuration.md` |
| 483-488 | Tuning, 44x | how-to + reference | same two |
| 489-503 | Five-model results table | reference | `reference/results.md` |
| 504-514 | Why the target is log-transformed | explanation | `explanation/the-log-transform.md` |
| 515-533 | The bundle's six keys | explanation + reference | argument → `explanation/the-bundle.md`; key table → `reference/artefact-bundle.md` |
| 534-573 | Layout tree | reference | `reference/project-layout.md` |
| 574-583 | Not built yet | roadmap | **stays** (hub) |

---

## Part C — the document set

### The four quadrant rules, stated once so they need not be repeated

| Quadrant | Never contains |
|---|---|
| **Tutorial** | Alternatives. "You could also". Reference tables. Any error the reader will not actually hit. More than one sentence of rationale before a link. |
| **How-to** | Teaching. Definitions. First-principles reasoning. Anything the reader must understand rather than do. Assumes the install already works. |
| **Reference** | Instructions. Persuasion. Narrative. Opinions about what is good. It describes the machinery and stops. |
| **Explanation** | Steps the reader is expected to type. Complete parameter lists. It may argue, admit doubt, and discuss the road not taken. |

---

### 1. Tutorial — `docs/tutorial/`

Eleven written units, exactly as scoped in `docs/_tutorial-plan.md`. Phase 3
changes nothing about them except to add one file:

**`docs/tutorial/index.md`** — new.

- Must contain: what the reader will have built by the end (a trained model, a
  running container, a prediction over HTTP); the eleven units listed with their
  tags; the hard prerequisite that this path needs **no Azure account and no
  DVC**; the total time.
- Must NOT contain: any part of the finished project's design. The tutorial earns
  each idea when the reader needs it. Explanations are linked *after* the step
  that motivates them, never before.

**One structural note to carry forward:** the tutorial stops at Docker. DVC,
tests, CI and CD are documented only as how-to and explanation. That is a
defensible line — those are operational concerns, not learning-to-build ones —
but state it in `index.md` so the reader does not go looking for Chapter 8.

---

### 2. How-to — `docs/how-to/`

Eight guides. Each opens with a one-line "you already have…" precondition and
ends with a verifiable result.

**`pull-data-and-models.md`**

- From: README 51-70, 197-205.
- Contains: obtaining the connection string from the portal (storage account
  `insurancedvc` → Security + networking → Access keys); `dvc remote modify
  --local`; `uv run dvc pull`; verifying with `dvc status --cloud` and the exact
  success string `Cache and remote 'azureremote' are in sync.`; **Sidebar 2**.
- Must NOT contain: what DVC is (link `explanation/data-outside-git.md`); why the
  connection string is not committed; the after-training workflow.
- **Must open with a blunt precondition:** this guide works only for someone with
  access to *this* storage account. Everyone else goes to the tutorial.

**`record-a-new-model-version.md`**

- From: README 216-249.
- Contains: the three ordered steps (`dvc add` → `git add`/`commit` →
  `dvc push`); the warning that skipping step 3 leaves a pointer to a file on one
  machine only; `dvc status --cloud` as the check.
- Must NOT contain: the argument for DVC over git, or how to train.

**`switch-models.md`**

- From: README 459-488.
- Contains: change `model.name` in `config.yml`, the five valid names, re-run,
  what to expect. `tune: true` and the ~44x cost as a second, optional step.
- Must NOT contain: the preprocessing table (reference), the argument for
  preprocessing not being configurable (explanation), or model comparison numbers.

**`run-the-api-locally.md`**

- From: README 100-128.
- Contains: `uv run uvicorn app:app --reload`, `/docs`, the curl, the expected
  JSON, `samples.json` as paste-able input.
- Must NOT contain: the endpoint schema table or the validation bounds — link
  `reference/api.md`. Not the log-transform argument.
- **Precondition to state loudly:** `models/model.pkl` must exist, because
  `app.py` builds its `Predictor` at import time. A missing file fails the import,
  not the first request.

**`build-the-container.md`**

- From: README 157-181.
- Contains: `docker build`, `docker run -p 8000:8000`, the same curl against the
  container; the fact that `models/model.pkl` must be on disk *before* the build,
  because `COPY models/ ./models/` is the only way it enters the image.
- Must NOT contain: the 1.02 GB analysis, the nccl reasoning, the `--no-dev`
  reasoning — all link to `explanation/the-serving-image.md`.
- **Add one troubleshooting line the README lacks:** if the container dies with
  `libgomp.so.1: cannot open shared object file`, the `libgomp1` apt step is
  missing. See Part E, gap 2.

**`run-the-tests.md`**

- From: README 311-327, 353-366.
- Contains: `uv run pytest`; `uv run pytest -m slow`; what each of the two
  outcomes (108 passed vs 80 passed 28 skipped) means about your machine; and the
  procedure for a legitimately-moved golden number — update the expected values
  **in the same commit** that moved them, and say why in the message.
- Must NOT contain: why the tests skip rather than fail; why the cleaning tests
  use invented data. Both are `explanation/the-test-suite.md`.

**`check-for-drift.md`**

- From: README 250-269.
- Contains: `uv run jupyter lab notebooks/04_monitoring.ipynb`; the two HTML
  reports written to `reports/`; how to read the dataset-level share rather than
  a single column.
- Must NOT contain: what drift is; the simulation argument; the findings.

**`deploy-to-your-own-azure.md`**

- From: README 389-431, plus `cd.yml`.
- Contains: creating the app registration, the federated credential pinned to
  repo and branch, the four role assignments as a checklist, the three repository
  **variables** to set.
- Must NOT contain: the OIDC explanation, the case against `Contributor`.
- **Highest-risk guide in the set.** It is the only one whose steps cannot be
  re-run cheaply to verify. Mark it clearly as written-from-configuration rather
  than re-walked, or walk it once on a fresh subscription.

---

### 3. Reference — `docs/reference/`

Eight files. Austere, complete, scannable. No prose that could be cut.

**`configuration.md`** — every key in `config.yml`'s 128 lines: name, type,
default, effect, and the `file:line` that reads it. Includes the per-model
`params` and `tuning_params` blocks and the CatBoost naming divergence
(`random_seed` / `depth` / `iterations` against `random_state` / `max_depth` /
`n_estimators`). Includes the dependency pins that are constraints rather than
preferences — `plotly<6` because Evidently 0.7.x pins it, and the pandas pin that
mlflow 3.x forces.
*Not:* why preprocessing is absent from the file. One cross-reference line only.

**`api.md`** — both endpoints, request and response schemas, all six field bounds
with their provenance, the 422 shape, the 200 shape. Sourced from `app.py:30-56`.
*Not:* curl walkthroughs, or the honesty argument for refusing out-of-range input.

**`artefact-bundle.md`** — the six keys, each with type, an example value, the
line that writes it (`steps/train.py:279-285`) and the line that reads it
(`steps/predict.py:31-36`).
*Not:* the thousand-fold-error argument. That is the explanation's job and it is
the strongest page in the whole set — do not dilute it by half-telling it here.

**`commands.md`** — every command the project accepts, in one table: `uv sync`,
`uv run main.py`, the five DVC commands, `pytest` and `pytest -m slow`,
`mlflow ui`, `uvicorn`, `docker build` / `run`. Each with what must exist first
and what it changes on disk.
*Not:* ordering, workflow, or advice.

**`test-suite.md`** — the six files and what each guards; the two skip markers and
their exact reasons; the `slow` marker and `addopts = "-m 'not slow'"`; the
fixtures (`tidy_frame`, `fake_training_data`, `fake_bundle`) with their shapes.
State the counts precisely: **109 collected, 1 deselected, 108 run, 28 of those
skipped without the DVC artefacts.** The README's "109 tests" beside a block
reading "108 passed" reads as an error.
*Not:* the design argument for skipping.

**`workflows.md`** — `ci.yml` and `cd.yml`: triggers, jobs, steps, the three
repository variables, the four role assignments as a table, the image tag format.
**Must state the `dev`-branch consequence**, which appears nowhere in the README:
CI fires on pull requests and pushes to `master`, so **a direct push to `dev` runs
no workflow at all**. On `dev` the safety net is the pull request, not the push.
*Not:* the OIDC argument, or the least-privilege argument.

**`results.md`** — the five-model table (RMSE, MAE, R², MAPE), the split, what each
metric means in one line, and the fact that every figure is in dollars because the
pipeline inverts the transform before scoring.
*Not:* why the target is transformed.

**`project-layout.md`** — the tree from README 534-573, corrected. Three
corrections are required, all from `_facts.md` §11: `models/` holds **two**
pickles and only `model.pkl` is ever loaded — say plainly the other is a dead
artefact from notebook 03; `data/` holds **four** CSVs and the pipeline reads only
`merged_data.csv` — say `cleaned_data.csv` is *not* the pipeline's input; and
`samples.json` is referenced by no code and no test.

---

### 4. Explanation — `docs/explanation/`

Ten discussions. This quadrant is where the project's actual value sits: the
README's best paragraphs are all explanation, and they are currently buried under
commands.

**`architecture.md`** — traces A and B from `_facts.md` §3 and §4. One prediction
from HTTP in to dollars out; one training run end to end. The pipeline diagram at
full size. The argument for validating input against the training range: a model
asked about a 90-year-old has never seen one and will answer confidently anyway.
*Not:* any command the reader should run.

**`the-log-transform.md`** — `charges` is right-skewed; RMSE squares error in
dollars, so raw-dollar training chases the expensive few and neglects the many
cheap ones; `log1p` turns that into roughly squared error in percent, so a 20%
miss counts the same at every price. Notebook 03 §4.3 measured this rather than
assuming it. Names the two lines that apply and undo it —
`steps/train.py:217` and `steps/predict.py:72` — and says these are the only two.
*Not:* the bundle. Link it.

**`the-bundle.md`** — the strongest page. A model fitted on `log1p(charges)`
returns about **9.7** where the answer is about **$16,000**. It does not crash. It
does not warn. `use_log_target` travelling inside the artefact is what prevents
it; `feature_order` and `categorical_features` are what stop `app.py` drifting
from how the model was fitted. Ends on `cd.yml:117-119`, which asserts the live
prediction lands between 1,000 and 200,000.
*Not:* the six-key table. Link `reference/artefact-bundle.md`.

**`preprocessing-is-not-configurable.md`** — the tutorial default is to put every
knob in the YAML. Here it is derived from the model name, because the three
boosting libraries read `category` columns natively, the forest needs one-hot, and
the linear model needs one-hot plus scaling plus term expansion. Exposing that as
configuration would mean hand-maintaining a rule you cannot get right without
reading `train.py` anyway.

**`keeping-the-outliers.md`** — `remove_outliers` logs the IQR-flagged rows and
removes none. They are high-cost smokers: roughly 10% of the data and about half
of all smokers. Not measurement errors — the expensive customers the model exists
to price. Dropping them trains a model that has never seen the cases that matter
most.

**`data-outside-git.md`** — what DVC is, in one paragraph, for someone who has
never met it. Then the actual reason: `models/model.pkl` is 2.7 MB of binary
rewritten on **every** training run, and git cannot forget. `data/` rides along
for consistency, though at 168 KB it would have been fine in git. The two-file
split — `.dvc/config` committed, `.dvc/config.local` never.

**`the-test-suite.md`** — three arguments in one place. Why the suite skips rather
than fails on a fresh clone, and what that buys: CI green with no Azure
subscription, and a suite that outlives the storage account. Why the cleaning
tests use twelve invented rows with one planted problem rather than the real data,
which triggers almost none of the rules. Why a golden-number test exists — and
this is where **Sidebar 1 is cross-referenced in one sentence**: it guards the
class of bug the CatBoost leak was, a silent behaviour change that raises nothing
and is visible only against a number written down earlier.

**`deploying-without-secrets.md`** — merges README 376-388, 389-414, 415-431 and
450-458. What OIDC is, for someone who has never met it: GitHub mints a
short-lived token per run, and Entra trades it only if it matches a federated
credential pinned to this repository and this branch. Why the three values are
**variables, not secrets** — identifiers, not passwords. Why `dvc pull` needs no
credential on the runner (`account_name` only, so DVC falls through to
`DefaultAzureCredential`, which picks up the `az login` that just happened). The
case against `Contributor`, and the trap that `Owner` and `Contributor` on a
storage account do **not** grant access to the blobs inside — a separate
data-plane role family whose absence is a 403 that looks like an authentication
bug. Sha tags rather than `latest`.
*Not:* the setup steps. Link `how-to/deploy-to-your-own-azure.md`.

**`deploy-gates.md`** — what makes this a model pipeline rather than a deploy
script. `pytest -m slow` recomputes RMSE against the real data on the runner
before anything is built or pushed. The closing step asks the deployed URL for a
real prediction and rejects an answer that is not in dollars. A deploy that
reports success while the app returns 502, or quietly serves `log1p` dollars, is
worse than one that fails.

**`drift-monitoring.md`** — what drift is, for someone who has never met the word.
Then the honest parts: the production data is *simulated*, so the drift found is
drift we put there. `charges` is withheld on purpose, because in production you
get the features when someone applies and the real costs months later — that gap
is the central difficulty of monitoring a live model. The healthy baseline was
**not** perfectly clean: 3 of 8 columns crossed 0.1 on two halves of the same
shuffle, which is why the dataset-level share is the number to watch. And
Evidently nearly missed a change made on purpose — `smoker` moved 20.5% to 32%
and scored **0.0969, marked `ok`**, while `bmi` nudged 3 points scored 0.45. A
drift score is evidence, not a verdict.

**`the-serving-image.md`** — the four Docker decisions from `_facts.md` §8, one of
which the README omits. `--no-dev` drops 217 of 257 packages. The
`nvidia-nccl-cu13` uninstall reclaims 288 MB **and must be in the same `RUN`**, or
the files survive in the layer below and nothing is reclaimed. `libgomp1` must be
installed because all three boosting libraries link OpenMP and `python:3.12-slim`
does not ship it. `dvc pull` stays outside the build because it would bake the
connection string into an image layer. Plus why all five model libraries stay in:
any of them could be the one inside `model.pkl`, and unpickling needs the library
it came from.

---

## Part D — what the README keeps

Target: **90 lines, down from 583.** It becomes a hub, not a manual.

**Keeps**

1. Title and the three-sentence framing (lines 1-9).
2. Both badges and the live URL with its expiry warning (10-17).
3. The pipeline ASCII diagram (19-40) — the one picture that orients everyone.
4. A quickstart of at most six commands that **works without an Azure account**.
   This is the single most important change in Phase 3: the current README's first
   instruction is unreachable for every reader but one.
5. A documentation index — four headings, one line each, linked.
6. A one-line results headline: Random Forest, RMSE $4,193 on the test split.
7. "Not built yet" (574-583), unchanged.

**Must NOT stay**

DVC credential setup · the after-training workflow · the OIDC and role tables ·
the Evidently findings · the test-suite anatomy · the layout tree · the config
surface · the log-transform argument · the Docker size analysis · the bundle's six
keys. All of it is good writing. None of it belongs on a landing page.

**One sentence the README must gain, high up:** a fresh clone cannot run the API,
the full test suite, or a Docker build. All three need `models/model.pkl`, which
is DVC-tracked, git-ignored, and sitting behind a private Azure remote. Say it
before the reader discovers it.

---

## Part E — gaps the split exposes

Nine items with no correct home in the current README, ordered by the cost of
leaving them alone.

1. **DVC, tests, CI and CD have no tutorial chapter.** Eleven commits
   (`5774aee` through `4a536c3`) sit outside the seven-chapter scope. Decide
   explicitly: either extend to Chapters 8-11, or state in `tutorial/index.md`
   that these are operational and live in how-to. Sidebar 2's placement depends on
   this answer.
2. **`libgomp1` is missing from the README's Docker section**, which promises
   "three things" and lists three savings. It is the fourth decision, and the only
   one whose absence produces a bare `libgomp.so.1: cannot open shared object
   file`.
3. **A direct push to `dev` runs no workflow.** Nowhere in the README. Belongs in
   `reference/workflows.md`.
4. **MLflow's `Personal%20Project` path bug and the `cloudpickle` choice** appear
   in `main.py`'s comments and in tutorial Ch6, but nowhere in the README.
   `explanation/` needs a short section, or Ch6 stays their only record.
5. **Two model pickles**, one never loaded. The layout tree currently says "the
   notebook's winning model", which reads as though it is used.
6. **Four CSVs, one read.** `cleaned_data.csv` is written by notebook 02 and is
   *not* the pipeline's input, because `steps/clean.py` re-cleans from
   `merged_data.csv`. Intentional, but it reads as a bug.
7. **`samples.json` is referenced by no code and no test**, while the README
   describes it twice (lines 126 and 544).
8. **The entry point is toggled by commenting out a line** (`main.py:200-203`).
   Documented neutrally today. Flag it once as a known wart, not a pattern to copy.
9. **Test counts.** Resolve the 109/108 ambiguity in `reference/test-suite.md`.

**And a deadline.** The Azure trial expires around **2026-09-25** — about four
weeks from today. When it lapses, the live URL stops answering and `dvc pull`
stops working. Three consequences for this plan: the live URL must carry its
expiry wherever it is cited; `how-to/pull-data-and-models.md` becomes unusable for
everyone including the author; and `how-to/deploy-to-your-own-azure.md` should be
walked once **before** the subscription is gone, while it can still be verified.

---

## Part F — three questions before Phase 4

1. **Does the tutorial stop at Docker?** (Gap 1.) It decides Sidebar 2's home and
   whether four more chapters exist.
2. **What did the wrong storage account actually look like when it failed?** If it
   can be reproduced, Sidebar 2 gets a Symptom line. If not, it opens on Cause and
   says so. Do not guess.
3. **Write order.** Recommended: `explanation/the-bundle.md` and
   `explanation/the-log-transform.md` first — every other document links to them,
   and both are already 80% written inside the README. Then the trimmed README, so
   the project has a working front door. Then reference, which is mechanical. How-to
   and the tutorial last, since they are the largest and depend on the rest being
   linkable.
