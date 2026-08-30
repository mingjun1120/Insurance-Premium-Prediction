# Watching for the world to move

Hand the shipped model a book of business where the customers are five years
older, nearly three BMI points heavier and half again as likely to smoke, and it
prices every one of them without hesitating. The mean prediction goes from
$12,449 on the data it was trained on to $18,139 on the new file. No error, no
warning, nothing in a log. The model has no way to notice that the population
moved. Answering is the only thing it knows how to do.

**Data drift** is the name for that movement: the inputs arriving now no longer
look like the inputs the model learned from.
`notebooks/04_monitoring.ipynb` uses [Evidently](https://docs.evidentlyai.com)
to look for it. The interesting part of that notebook is not that it finds
drift. It is the two places the tool gets it wrong.

## Drift is a comparison, so it needs two datasets

There is nothing to find in a single dataset. Evidently takes a **reference** —
the world the model knows — and a **current** one, and reports column by column
where the two distributions have separated.

The notebook builds three, using the pipeline's own `Cleaner` and `Trainer`
rather than re-writing the split, so the reference really is the data the model
was fitted on:

| set | what it is | rows |
| --- | --- | --- |
| reference | the training split | 1,069 |
| current | the test split | 268 |
| production | a simulated future book of business | 400 |

That gives two comparisons. Reference against current, where nothing should have
moved. Reference against production, where things were moved on purpose.

## Running only the alarm would be a trap

A report full of red tells you nothing until you have seen the same report come
back green on data you know is fine. So the healthy comparison runs first.

It did not come back clean.

| column | method | score | verdict |
| --- | --- | --- | --- |
| `prediction` | Wasserstein (normed) | 0.1287 | DRIFT |
| `bmi` | Wasserstein (normed) | 0.1181 | DRIFT |
| `charges` | Wasserstein (normed) | 0.1103 | DRIFT |
| `children` | Wasserstein (normed) | 0.0494 | ok |
| `age` | Wasserstein (normed) | 0.0392 | ok |
| `sex` | Jensen-Shannon | 0.0340 | ok |
| `region` | Jensen-Shannon | 0.0339 | ok |
| `smoker` | Jensen-Shannon | 0.0205 | ok |

Three of eight columns crossed the 0.10 threshold, none of them by as much as
three hundredths. Nothing happened to those columns. They are two halves of one
shuffle of one file, and the difference between them is what 268 rows of
sampling noise looks like.

Which is the finding the healthy run exists to produce. A fixed per-column
threshold on a small current set will raise false alarms, so the number to watch
is the dataset-level share: 37.5% sits under the 50% line and Evidently
correctly declares no dataset drift. Run only the alarm case and that threshold
would have looked entirely trustworthy.

## The drift is ours

The production file is not real traffic. This project is built on a static
Kaggle file, and section 5.3 of the notebook invents `data/production.csv` from
it: 400 rows sampled with replacement from `merged_data.csv`, then four changes
that are each something that genuinely happens to an insurance book — the book
ages, weight rises, the smoking mix worsens, the company expands into one
region. It is seeded, so the file reproduces.

Measured against the training split, here is what the file on disk actually
contains:

| | reference | production |
| --- | --- | --- |
| `age`, mean | 39.20 | 44.41 |
| `bmi`, mean | 30.54 | 33.26 |
| `smoker`, share yes | 20.0% | 32.0% |
| `southeast`, share | 26.8% | 45.0% |

The shifts are clipped to the range the model was trained on — age to 18–64, bmi
to 15.96–53.13 — which is why the realised means land a little under the shift
that was asked for. That is deliberate: a value outside the training range would
register as drift without being a change in distribution, and it would be a
different problem wearing the same alarm.

All of which is worth saying once, plainly: the drift found in this report is
drift somebody put there. It is honest material for learning the tool. It is not
evidence about the world.

## `charges` is not in the file

The production set has six columns. The target was dropped on purpose, and this
is the part of the notebook that transfers to any real system.

In production you get the features the moment somebody applies. You do not find
out what they actually cost until the year is over, often much later. So the
alarm report can compare inputs and predictions, and nothing else —
`RegressionPreset` is absent from it because without the true charges there is
nothing to be right or wrong about.

That makes drift a proxy. It says the world changed. It does not say the model
got worse, and those are different claims. The only place this project measures
real error is where it still has the answers: the slow test that recomputes RMSE
against the labelled data before a deploy is allowed through
([deploy-gates.md](deploy-gates.md)).

## What the scores are measuring

| column | method | score | verdict |
| --- | --- | --- | --- |
| `prediction` | Wasserstein (normed) | 0.5153 | DRIFT |
| `bmi` | Wasserstein (normed) | 0.4499 | DRIFT |
| `age` | Wasserstein (normed) | 0.3721 | DRIFT |
| `region` | Jensen-Shannon | 0.1374 | DRIFT |
| `smoker` | Jensen-Shannon | 0.0969 | ok |
| `children` | Wasserstein (normed) | 0.0517 | ok |
| `sex` | Jensen-Shannon | 0.0120 | ok |

Four of seven, a share of 57.1%, and dataset drift is declared.

Two different methods share one threshold. Evidently uses Wasserstein distance
for numeric columns and Jensen-Shannon distance for categorical ones, and judges
both against 0.10. The scores are only comparable to that threshold, never to
each other.

"Normed" is where the numeric scores come from. For these columns the score is
the shift measured in the reference's own standard deviations:

- `age` moved 5.21 on a spread of 14.00 — 0.372, against a reported 0.3721
- `bmi` moved 2.72 on a spread of 6.05 — 0.450, against a reported 0.4499

So `bmi` outranks `age` while moving less than half as far in the units a person
would use. That is the metric working correctly, and it is not what the word
"drift" suggests on its own. The question it answers is not *how far did this
column move*. It is *how far did it move compared with how much it varies
anyway*.

## The one it missed

`smoker` went from 20.0% to 32.0% — a large, deliberate change to the field that
moves this price harder than any other — and scored **0.0969**. Under the
threshold. Verdict `ok`.

Jensen-Shannon distance on a two-value column is blunt: it takes a great deal of
movement before it registers. `region`, also moved on purpose and much further
in share terms, only scraped over at 0.1374.

Of the four columns that were changed deliberately, one was missed outright and
one barely registered. The highest score in the report belongs to a column
nobody touched.

That is not a broken tool, and the lesson is not to distrust it. It is that the
default method is weak on a shape of column this particular dataset cares about
most, and that is knowable in advance. For a binary field with this much price
attached to it, watching the raw rate is one line of pandas, and it catches what
the distance metric shrugs at. A drift score is evidence, not a verdict.

## The column nobody touched

`prediction` scored 0.5153, the highest in the run. Nothing in section 5.3
altered it. It moved because the inputs moved and the model followed them
faithfully, from $12,449 on the reference to $18,139 on production.

In a system where ground truth is months behind, that is often the earliest
warning available, and it has a property the input columns do not: it is a
function of all of them at once, so a shift too small to trip any single feature
can still show up there.

## Finding drift is not a reason to retrain

The report says the world moved. It does not say the model is now wrong, and
acting as though it did is how a monitoring setup turns into a retraining
treadmill.

The notebook's closing section puts two things before retraining, and both are
about not trusting the alarm on its own. Check that the shift is real — a
`region` mix that jumps might be one large new client rather than a change in
the population. And wait for ground truth wherever waiting is possible, because
once real charges arrive for some of those rows, the healthy report's setup can
be run on them and produce an actual RMSE, which is a measurement rather than a
proxy.

A drift report is not the measurement. It is the thing that tells you which
measurement is now worth making.
