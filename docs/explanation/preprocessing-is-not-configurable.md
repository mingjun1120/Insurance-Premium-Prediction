# Preprocessing is not in the config file

`config.yml` is 128 lines and it holds every knob the pipeline has: the input
path, the target column, the split, the seed, whether the target is
log-transformed, which model runs, and a full parameter block for each of the
five models. One thing is deliberately absent, and the file says so in the
middle of itself (`config.yml:41-44`):

```yaml
# Preprocessing is NOT configured here. The Trainer derives it from the model
# name: the three boosting libraries read category columns natively, the forest
# needs one-hot encoding, and the linear model needs one-hot, scaling and term
# expansion. See steps/train.py.
```

Change line 22 from `RandomForestRegressor` to `CatBoostRegressor` and the
pipeline that gets built is a different shape. The one-hot encoder disappears. A
list of categorical column names appears as a fit-time argument that was not
there before. Nothing in `config.yml` records either fact, and nothing needs to.

## What the five models actually need

`MODEL_REGISTRY` (`steps/train.py:39-45`) maps each name to a class and a single
word, and `create_pipeline` (`steps/train.py:79`) turns that word into a
pipeline.

| `model.name` | word | what gets built |
| --- | --- | --- |
| `LGBMRegressor`, `XGBRegressor`, `CatBoostRegressor` | `native` | the model, alone — one step |
| `RandomForestRegressor` | `onehot` | one-hot the category columns, then the model |
| `LinearRegression` | `linear` | one-hot and scale, expand to degree-2 terms, scale again, then the model |

The differences are not stylistic. scikit-learn's forest cannot read a pandas
`category` column at all, so without the encoder there is no run. The three
boosting libraries can read one, so the encoder would be work done to throw
information away. And the linear model needs the interaction written out for it,
because a straight line through `smoker` and a straight line through `bmi`
cannot between them express *smoking is much worse if you are also heavy* —
notebook 03 section 4.12.2 is where degree 2 won, and `config.yml:105-107` cites
it.

The columns are selected by dtype rather than by name
(`make_column_selector(dtype_include="category")`, `steps/train.py:134-139`), so
a column that `steps/clean.py` drops does not take the pipeline down with it.

## "Native" is three different things

This is where a configuration key would start telling lies.

`LGBMRegressor` needs nothing. Hand it a frame with category columns and it
reads them.

`XGBRegressor` needs two parameters set before it will accept the same frame,
and they live in its own params block (`config.yml:78-80`):

```yaml
      # Both of these are required before XGBoost will accept a category column
      enable_categorical: true
      tree_method: hist
```

`CatBoostRegressor` needs neither of those and refuses the frame anyway unless
it is told which columns are categorical. That list cannot be written down in
advance, because it depends on what survived cleaning, so `_fit_kwargs`
(`steps/train.py:180-195`) computes it from the fitted frame's dtypes and passes
it as `model__cat_features` at fit time. It is the only model that needs
anything there; the method returns an empty dict for the other four.

So one word, `native`, stands for three different sets of requirements, met in
two different places — one in YAML, one in Python, at two different moments.

## What the knob would have to be

There are two honest ways to expose preprocessing in the config, and both are
worse than not doing it.

The first is an enum: `preprocessing: onehot | native | linear`. It buys the
ability to pick a combination nobody has tested. Some of those fail loudly —
`native` on the forest hits scikit-learn's refusal to read a category column and
the run stops. The dangerous ones are quiet. `onehot` on LightGBM fits without
complaint, saves a normal-looking bundle, and serves normal-looking predictions,
having switched off the one behaviour the library was chosen for. Nothing raises
and nothing warns; the only symptom is a model slightly worse than it should
have been.

The second is a step list — transformers and their arguments, composed in YAML.
That is a programming language with no editor, no type checking and no tests,
written in a file format designed for settings.

The module docstring at `steps/train.py:1-19` puts the objection in one line:
putting that in `config.yml` would mean the user hand-maintaining a rule they
cannot get right without reading `train.py` anyway. A knob you can only set
correctly by reading the code it replaces is not configuration. It is a second
copy of a decision, with a way to disagree with the first.

## Where the seam still shows

The boundary is not perfectly clean, and it is worth saying so rather than
claiming a tidiness the file does not have.

`tuning_params` name pipeline steps directly. Every model's grid uses the
`model__` prefix, which works across all five because the final step is always
named `model` — `create_pipeline`'s docstring states that as its reason, and its
`Examples` block asserts it. But `LinearRegression`'s grid uses `expand__degree`
and `expand__interaction_only` (`config.yml:112-113`), and the `expand` step
exists only in the linear pipeline.

The same block has a second oddity. `LinearRegression`'s `params` are not the
model's parameters at all: `degree` and `interaction_only` configure
`PolynomialFeatures`, and the regressor is constructed with no arguments
(`steps/train.py:96-103`). Plain least squares has nothing to tune. The comment
above the block says exactly that, which is the right way to handle a wart —
name it where somebody will read it.

So the config does know a little about the shape of the pipeline. What it does
not do is decide that shape.

## The line the file draws

`config.yml` holds choices. It does not hold the consequences of choices.

Which model runs is a choice, and so are the split, the seed, the log transform
and every hyperparameter — a person can change any of them and the change means
something on its own. Which preprocessing runs is not a choice; it is what the
model choice already implies. A value completely determined by another value is
not a setting. It is a duplicate that can drift out of step with the thing it
duplicates.

The project applies the same reasoning to the artefact. `feature_order` is not
written down in `app.py` and again in the bundle; it lives in one place and is
read from there ([the-bundle.md](the-bundle.md)). One decision, one home, in
both cases.

A config file is meant to be edited by somebody who has not read the source. A
`preprocessing:` key would be the one line in this file that such a person
cannot set safely, and the failure would not announce itself. Leaving it out
makes the file shorter and the set of things that can silently go wrong smaller
at the same time, which is not a trade that comes up often.
