# The cleaning step that removes nothing

`data/merged_data.csv` holds 1,338 rows. Apply the standard interquartile rule
to `charges` and 139 of them are outliers — 10.4% of the file. Of those 139,
136 are smokers, and the file contains 274 smokers in total.

So the tidy-up deletes half the smokers.

A rule that removes half of one group is not cleaning. It is a decision about
who the model is for, and the fourth of the seven cleaning rules in
`steps/clean.py` declines to make it.

## What the rule is measuring

The interquartile range is the middle half of the data. Sort `charges`, take the
value a quarter of the way up ($4,740.29 here) and the value three quarters of
the way up ($16,639.91), and the distance between them is the IQR. The
convention is to call anything more than one and a half IQRs past either end an
outlier, which in this file means anything above $34,489.35. Charges run to
$63,770.43.

That is a distance measurement, and distance is all it is. The rule has nothing
to say about whether a far-away row is real. A typo that adds a zero to a
premium and a genuine $60,000 claim look the same to it, because to it they are
the same: both are far from the middle.

Telling those two apart needs somebody to look at the rows. Notebook 02 looked.

## The rows are the product

The 139 are not scattered. 136 of them smoke, which is 49.6% of every smoker in
the file, and only 3 of the flagged rows belong to somebody who does not.

Smoking is the largest thing this dataset knows about what it costs to insure
someone. An expensive smoker is not a measurement failure — it is the case the
model was commissioned to price. A model that has never seen one will still
answer questions about one, in the same confident tone it uses for everything
else, and it will be wrong in the direction that costs the most money.

`app.py` already refuses questions it has no business answering: the bounds at
`app.py:49-56` are drawn from this file's own ranges, so a request about a
90-year-old comes back as a 422 rather than as a guess (see
[architecture.md](architecture.md)). There is no matching guard on the way out.
Nothing in the service declines to price a customer whose real premium is
$60,000. It just prices them, using whatever it was shown.

## The step that reports and returns

`steps/clean.py:230` says what it is for in its own docstring:

```python
"""Report outliers without removing any (notebook 02, 3.2.3).

This step deliberately removes nothing. Notebook 02 examined the rows an
IQR rule would flag and found they are high-cost smokers - roughly 10% of
the data and about half of all smokers. They are not measurement errors;
they are the expensive customers the model exists to price. Deleting them
would train a model that has never seen the cases that matter most.
"""
```

Roughly 10% of the data and about half of all smokers: 10.4% and 49.6%. The
claim recorded in the notebook still holds against the file as it sits on disk.

The method itself walks the numeric columns, counts what the rule would flag,
logs each count and returns the frame it was handed, unchanged. The last thing
it writes to the log is a sentence rather than a number:

```
- Every row is retained, by the decision recorded in notebook 02.
```

Counting without deleting is not a wasted pass. The docstring gives the reason
in one line — a sudden jump in flagged rows is worth noticing even when nothing
is dropped. Rule 4 is a monitor living inside a cleaning pipeline, and it is the
only one of the seven that changes no data at all.

## What the loop actually counts

One detail is worth knowing before you go looking for those 139 rows in a
training log, because they are not in it.

```python
for column in data.select_dtypes(include="number").columns:
    if column == self.target:
        continue
```

The loop skips the target. `charges` is the target, so the column the entire
argument is about is the one column the method never counts. What it counts is
the numeric features, and on this data they are quiet: `age` flags nothing,
`children` flags nothing, and `bmi` flags 9 rows, 0.7% of the file. All 9 sit
inside the 15 to 55 band `app.py` accepts, because that band was measured from
this same file.

So the log reports 9 while the reasoning behind it concerns 139. Both numbers
are real and the outcome is the same either way, since nothing is removed
regardless. But the argument lives in the docstring and in notebook 02, and
reading the log will not lead anybody to it.

Skipping the target is also the safer half of the behaviour. Dropping rows
because a *feature* is unusual is a judgement about which people the model has
seen. Dropping rows because the *outcome* is unusual is a judgement about which
answers it is allowed to learn, and that one changes what the model is without
announcing that anything changed.

## Keeping them is not free

The tail stays, so the skew stays, and the skew becomes the next problem.
Squared error in dollars is dominated by the expensive rows, so a model fitted
on raw `charges` will give up accuracy on the cheap majority to shave a little
off the tail. Fitting in log space is the answer to that, and
[the-log-transform.md](the-log-transform.md) is the argument for it — an
argument that exists because this decision was taken first. The two are a pair.
Keep the outliers and something has to be done about the scale they live on.

There is also a number that would move the wrong way. The RMSE in
[reference/results.md](../reference/results.md) was measured with these rows in
both halves of the split. Delete them and they leave the test set as well, so
the figure would drop: the model would be worse at the job and the page would
report a better number. A test set with the hard cases taken out is not a test.

## When the opposite is correct

None of this becomes "never drop outliers".

If the flagged rows carried a BMI of 900, an age of 300, or a premium of one
dollar, they would be broken records, and keeping them would teach the model
from noise. The IQR rule would be pointing straight at real corruption and
deleting them would be the right move. The question that decides it is not how
far a row sits from the middle. It is whether the row happened.

These happened. 136 smokers really were charged more than $34,489, and whoever
prices policies with this model will meet more of them. The rule found them and
the method kept its conventional name, which is how the pipeline ends up with
one step called `remove_outliers` that promises the opposite of what it does.
