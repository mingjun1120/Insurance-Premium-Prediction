# The two gates on the deploy

Every step in `cd.yml` can succeed while the service ends up wrong.

The image builds. The push works. `az containerapp update` returns zero, the
container starts, and the app answers. Every step is green — and the model
inside is scoring several hundred dollars worse than the one the results table
claims, or the endpoint is returning about 9.8 for a person whose premium is
$18,095.88, because the line that undoes a logarithm went missing. No exit code
in that run has anything to say about either.

So two steps in the file build nothing and ship nothing. They only ask
questions, and either answer can stop the run.

## Gate 1 — the model still scores what it scored

`cd.yml:64-70` runs the test suite twice.

```yaml
- name: Test
  run: uv run pytest

# The guard that makes this a model pipeline rather than a deploy script:
# recompute RMSE against the real data and refuse to ship if it moved.
- name: Check the model still scores what the README claims
  run: uv run pytest -m slow
```

That comment is the file's own, and it is accurate. The first command runs the
suite the way it runs everywhere. The second asks for the one test that is
excluded by default: it cleans the real data, splits it the way training splits
it, scores the shipped model on the test half, and holds four numbers up
against four numbers written down earlier. What that test asserts, and why the
numbers are allowed to move, is [the-test-suite.md](the-test-suite.md).

Two things about where the step sits.

It runs after `uv run dvc pull` (`cd.yml:62`), which makes this the one place
in the project where the real artefacts are guaranteed to be on disk. On a
laptop without them, 28 tests skip and say so. Here nothing skips, so the run
that matters most is the run with the fewest holes in it.

And it runs before `az acr login` (`cd.yml:73`). If a number moved, nothing has
been built, nothing has been pushed, and nothing is pointing anywhere new. The
failure costs a red run and no cleanup whatsoever. That is the cheap half of
this design.

## Gate 2 — the live URL has to answer in money

The other question cannot be asked on the runner at all. Everything Gate 1
establishes, it establishes about a Python process on a GitHub machine: the
artefact is right, the code around it is right, the numbers hold. None of that
is evidence that the image was built from that artefact, that the registry
received it, that the container app was repointed, or that the thing now
serving traffic in Azure is any of the above.

So the last step of the workflow (`cd.yml:95-120`) goes and asks the URL.

It waits first — ten attempts at `GET /`, fifteen seconds apart, each with a
sixty-second timeout, until one of them comes back 200 (`cd.yml:104-109`). Only
then does it POST the sample person, age 19, female, BMI 27.9, no children,
smoker, southwest, and read `predicted_premium` out of the reply.

One line of arithmetic then decides the run:

```bash
# log1p dollars would come back around 9.8 rather than five figures
ok=$(python -c "p=float('$premium'); print(1 if 1000 < p < 200000 else 0)")
```

The window is enormous on purpose. It is not measuring accuracy; it is
measuring units, and [the-bundle.md](the-bundle.md) is the page about how a
model returns the right number in the wrong ones without anything raising a
word. When the check passes, the step says so and writes the figure into the
run summary:

```
predicted premium 18095.88 - looks like dollars
```

## The second gate fails late, and that is not free

Read the file in order and the asymmetry is plain. The build and push are
`cd.yml:77-84`. The repoint is `cd.yml:86-91`. The smoke test is `cd.yml:95`.
By the time Gate 2 has an opinion, the image is in the registry and the app is
already serving it.

A red run undoes none of that. What it buys is who finds out first: a workflow
step, inside the run that caused the problem, rather than whoever calls
`/predict` next. That is a smaller claim than "the gate prevents a bad deploy",
and it is the true one. Recovery is available rather than automatic — every
image carries its commit sha as a tag (`cd.yml:79-84`), so the one before it is
still in the registry under a name that says exactly which commit produced it.

The retry loop is doing more work than it looks like it is doing. A container
app takes a while to bring a new revision up, and a smoke test that fired
immediately would fail on timing rather than on correctness. A check that goes
red for reasons unrelated to the change gets re-run out of habit, then
eventually switched off, and a switched-off gate is worse than no gate because
the workflow still lists it. Ten attempts at fifteen seconds is the difference
between a check people believe and a check people route around. If your deploy
target came up instantly and predictably you would not need the loop. This one
does.

One thing the step does not do: nothing in it compares the revision that
answered against `github.sha`. It asks the URL a question and believes the
reply. A 200 and a sensible premium are also what the previous revision would
return if it were still the one answering, so Gate 2 is evidence that the
service is healthy and speaking dollars — not proof that the commit which just
ran is the commit being served.

The same worry shows up in the concurrency block at `cd.yml:24-28`, which sets
`cancel-in-progress: false` and gives its reason: a cancelled `containerapp
update` can leave the app pointing at an image that was never pushed. Two
overlapping deploys queue rather than race. That is not a gate, but it comes
from the same place — the live thing should never be left in a state nobody
chose.

## Why both, and why neither is spare

The two gates ask questions that do not overlap and cannot be merged into one.

Gate 1 knows what a good model looks like and has no idea whether anything was
deployed. Gate 2 can see the deployed service and cannot tell a good model from
a terrible one: a model scoring twice the RMSE returns a perfectly plausible
five-figure premium and sails straight through. Drop the first and the pipeline
will ship a model that quietly got worse. Drop the second and it will report
success for an app returning 502, or one serving logarithms — and a deploy that
reports success while the service is wrong is worse than one that fails,
because the failure gets fixed today.

That is the whole difference between a deploy script and a model pipeline. A
deploy script's last question is whether the container started. This one's last
question is whether the number coming out of it is money.
