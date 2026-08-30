# Why the target is log-transformed

Two people ask for a quote. One should be charged $1,200 a year and the model
says $2,400. The other should be charged $40,000 and the model says $38,000.
Both predictions are wrong. Which one does the training punish harder?

Root mean squared error — RMSE, the first column of every results table in this
project — squares each miss in dollars and then averages. The cheap customer's
$1,200 miss squares to 1,440,000. The expensive customer's $2,000 miss squares
to 4,000,000. RMSE therefore calls the second prediction nearly three times
worse, even though it is off by 5% and the first is off by 100%.

That is not a rounding quirk. It is what training on raw dollars asks for.

`charges` is heavily right-skewed: most people in this dataset cost very little,
and a small group costs an enormous amount — and that group is kept in the
training data on purpose, which makes the skew worse rather than better (see
[keeping-the-outliers.md](keeping-the-outliers.md)). A model minimising squared
error in dollars will spend its capacity where the large squared numbers live,
which is the tail. It will accept being 100% wrong about a cheap customer if
that buys a few percent on an expensive one, because that trade lowers the
number it is being scored on.

## What `log1p` changes

`log1p(x)` is `log(1 + x)` — the natural logarithm, with the 1 added so the
function stays defined and well behaved down at zero. It comes from numpy, the
array library the rest of the stack is built on top of; delete numpy and there
is no project left to discuss, since every table and every fitted model in it is
numpy arrays underneath. Its exact inverse is `np.expm1`.

The useful property is that a fixed distance in log space is a fixed *ratio* in
dollars. The gap from $1,000 to $2,000 is the same size as the gap from $20,000
to $40,000, because both are a doubling. Squaring errors in that space is
therefore roughly squaring errors in percent, and a 20% miss counts the same
whether the customer costs $1,200 or $40,000.

The cheap majority stops being invisible.

## It was measured, not assumed

Notebook 03 section 4.3 decided this by cross-validating on the training split
only, and `config.yml:15-18` cites that section by name as the reason
`use_log_target` is `true`.

The check was worth running, because the transform is not automatically a win.
It helps when the target is skewed and you care about relative error. If your
target is roughly symmetric, or if a $2,000 miss genuinely is as bad at $1,200
as at $40,000 because there is a hard budget line at stake rather than a
customer's sense of fairness, then fitting in log space optimises for the wrong
thing and you have added a step that has to be undone for nothing in return.

Here it is measured, so it stays. Every dollar figure in
[reference/results.md](../reference/results.md) — RMSE, MAE or mean absolute
error, and the percent view, MAPE or mean absolute percentage error — is
reported in dollars because
the pipeline reverses the transform before it scores anything.

## The two lines

Only two lines in the pipeline touch the transform.

`steps/train.py:217`, which applies it:

```python
y_fit = np.log1p(y_train) if self.use_log_target else y_train
```

`steps/predict.py:72`, which undoes it:

```python
return np.expm1(predicted) if self.use_log_target else predicted
```

These are the only two. One goes in, one comes out, and both are conditional on
the same flag — but they do not read it from the same place. `steps/train.py:57`
takes it from `config.yml`, because at training time the config *is* the
decision. `steps/predict.py:34` takes it from the saved artefact, because by
prediction time the config may have moved on.

That last detail is the whole reason this stays safe. Forget the first line and
the model is obviously bad; the metrics collapse and you find out immediately.
Forget the second and the model is quietly, expensively wrong, and nothing
anywhere raises a word about it. Which is
[the bundle's job](the-bundle.md).
