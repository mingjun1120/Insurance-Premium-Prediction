[README](../README.md) / Presentation plan

# MLOps Presentation Plan

The storyline and demo format are approved. This document is the content brief
for slide design; it is not a slide deck. Presentation terminology is recorded
in the [project glossary](../CONTEXT.md).

## Audience and purpose

The audience is a team of Data Scientists at a bank in Malaysia. Their familiar
tools include company-hosted Jupyter Notebook, Hue/Hive SQL, SAS and other
on-premises systems. They understand data preparation, model development and
validation, but have limited practical exposure to MLOps.

The session should explain what MLOps is, why it matters and how its pieces fit
together. Use familiar problems before introducing concepts, and introduce tools
only when they illustrate those concepts. Connect the ideas to existing internal
workflows as well as possible future platforms.

## Agreed session format

| Part | Duration |
| --- | --- |
| Slides 1-9: concepts and project introduction | 14 minutes |
| Demo: existing results plus a live API prediction | 10 minutes |
| Slide 10: closing takeaway | 1 minute |
| Questions | 5 minutes |
| Total | 30 minutes |

The presenter will use the project laptop with internet and cloud access.
The demo will use existing MLflow runs, a completed deployment workflow and
saved drift reports. Its live action is an API prediction. Live training and
deployment are outside the agreed demo format.

## Storyline

The central question is: **Your model works today. Can someone else run it
reliably next month?**

Follow one project as its responsibilities grow:

1. We develop a model using a familiar workflow.
2. Someone must repeat the work and explain an earlier result.
3. We need reliable records, repeatable steps and checks.
4. Other people need to use the model for predictions.
5. We must review the system and its predictions after release.
6. A small project demonstrates how these practices connect.

The presentation should respect the audience's current workflow. MLOps practices
can improve on-premises work; cloud deployment is one implementation example.

## Slide skeleton

### 1. Your model works. What happens next month?

**Duration:** 1 minute.

**Purpose:** Establish a situation the audience recognises.

**Key message:** A successful model run creates further responsibilities.

**Talking points:** Imagine that new monthly data arrives, a colleague takes over
the project, and someone requests the exact model used last quarter. Getting a
good validation score was only one part of that work.

**Visual:** A notebook with a good score, followed by three small illustrations:
next month's calendar, another colleague and an old result.

**Transition:** "Let's start with the workflow we already know."

### 2. Our familiar Data Science workflow

**Duration:** 1 minute.

**Purpose:** Connect the talk to the audience's current tools and experience.

**Key message:** MLOps builds on familiar Data Science work.

**Talking points:** Retrieve data through Hue/Hive; prepare it in notebooks or
SAS; train and validate; save results and hand over the work. The question is how
we connect and repeat these stages reliably.

**Visual:** Data -> Preparation -> Training -> Validation -> Handover. Place
familiar tools underneath the relevant stages.

**Transition:** "When we repeat this process, three questions become harder to
answer."

### 3. Three questions a saved model cannot answer

**Duration:** 1.5 minutes.

**Purpose:** Give the audience a reason to learn the upcoming concepts.

**Key message:** The model file alone does not explain its history or how to
operate it.

**Talking points:** Which data, code and settings produced this result? Can
someone else rerun it and release changes safely? How will we know whether it
still performs well?

**Visual:** A saved model file surrounded by three question cards: Explain it.
Repeat it. Maintain it.

**Transition:** "MLOps connects the practices that help us answer these questions."

### 4. MLOps connects development with ongoing use

**Duration:** 1.5 minutes.

**Purpose:** Define MLOps and introduce the lifecycle.

**Key message:** MLOps combines people, processes and tools to develop, release
and maintain ML systems reliably.

**Talking points:** Extend the familiar workflow through deployment and
monitoring. Add records, checks and ownership across the lifecycle. Feedback
may lead to investigation, data fixes or retraining.

**Visual:** Prepare -> Train -> Evaluate -> Release -> Predict -> Monitor, with
a return arrow labelled Review and improve. Reuse this layout later.

**Transition:** "First, let's make each training result traceable."

### 5. Keep the recipe and the result together

**Duration:** 2 minutes.

**Purpose:** Explain reproducibility, versioning and experiment tracking.

**Key message:** To rebuild a result, we need the original inputs and
instructions as well as the saved output.

**Talking points:** Record the code version, data snapshot, settings and software
environment. Connect those to the training run, metrics and model. Versioning
preserves identifiable versions; experiment tracking records what happened in
a run. Then introduce Git, DVC and MLflow as the project's examples.

**Visual:** Four input cards, Code, Data, Settings and Environment, feeding a
training run that produces Model + Metrics.

**Transition:** "Good records explain a run. Next, we make the process easier to
repeat."

### 6. Turn a manual rerun into a repeatable process

**Duration:** 1.5 minutes.

**Purpose:** Explain pipelines and automated checks.

**Key message:** A defined sequence reduces the number of steps someone must
remember.

**Talking points:** Move established notebook work into reusable Python steps.
Keep notebooks for exploration and explanation. Check inputs and expected
behaviour. Introduce CI as automatically running checks when code changes.
Scheduling the process is a separate capability.

**Visual:** Load -> Clean -> Train -> Evaluate, with checkmarks between stages
and an optional notebook reference beside the flow.

**Transition:** "Once we have a model and its checks, how do other people use it?"

### 7. Release a model people can use

**Duration:** 2 minutes.

**Purpose:** Explain model registration, deployment and prediction.

**Key message:** Saving or registering a model is different from putting it into
use.

**Talking points:** A registry organises named model versions and their records.
A release process selects and checks what will run. Predictions can come from a
monthly batch job or an API request. Introduce Docker as packaging the application
and dependencies, and CD as preparing or deploying releases through a defined
process. Predicting new rows does not retrain the model.

**Visual:** Candidate model -> Checks / approval -> Release, branching into
Batch predictions and API predictions. These are conceptual alternatives; the
project demo uses an API.

**Transition:** "A working service tells us predictions are available. It does
not tell us they remain useful."

### 8. Keep checking after release

**Duration:** 2 minutes.

**Purpose:** Explain monitoring and the feedback loop.

**Key message:** Check both whether the system works and whether its predictions
remain useful.

**Talking points:** Monitor service errors, input changes, prediction changes
and model performance once actual outcomes arrive. Relate delayed outcomes to
banking examples. A drift signal prompts investigation; it does not prove
accuracy has fallen or mean retraining should happen automatically. Any
replacement model still needs evaluation.

**Visual:** Three panels: Service health, Data and predictions, and Actual
outcomes. Follow them with Investigate -> Evaluate a response.

**Transition:** "Now let's see how a small project implements some of these
practices."

### 9. Insurance Premium Prediction: follow one model

**Duration:** 1.5 minutes.

**Purpose:** Introduce the project and prepare the demo.

**Key message:** A small learning project can make the lifecycle tangible.

**Talking points:** Briefly explain the prediction task and public dataset.
Clarify that the target is US medical charges. Map the project to the concepts
already introduced: Python pipeline, Git/DVC, MLflow, tests, Docker/FastAPI,
Azure deployment and a drift-report demonstration.

**Visual:** A simplified project map using slide 4's lifecycle layout. Label
Implemented, Manual and Demonstration stages explicitly. Keep notebooks in a
separate Learning and exploration area. Show prepared data as the input to
model development, with source preparation upstream.

**Transition into the demo:** "We've seen the questions MLOps helps us answer.
Now I'll follow one model through this project: its training record, the release
checks, a prediction, and the report that helps us investigate changing data."

### 10. Make the next handover easier

**Duration:** 1 minute, after the demo.

**Purpose:** Bring the learning back to the audience's work.

**Key message:** Start by making one existing workflow easier to explain,
repeat and maintain.

**Talking points:** Preserve the query and data snapshot behind a run; record
settings and metrics together; give the next person a clear rerun procedure;
identify who reviews performance after release. These are useful starting points
within approved internal systems.

**Visual:** Revisit slide 3's cards, now labelled Traceable result, Repeatable
process and Ongoing review.

**Transition to questions:** "Which part of our own workflow would benefit most
from this?"

## Demo sequence

| Elapsed demo time | Show | What it demonstrates |
| --- | --- | --- |
| 0-2 minutes | Configuration and Python pipeline entry point | Established notebook work becomes an explicit, repeatable sequence. |
| 2-4 minutes | Existing MLflow runs and registered model versions | A model result has settings, metrics and a history. |
| 4-6 minutes | A completed deployment workflow and its checks | Releasing a model involves checks and packaging. |
| 6-8 minutes | One live API prediction; optionally one invalid input | Another application can request a prediction through a defined interface. |
| 8-10 minutes | Existing drift reports | Changed inputs deserve investigation; actual outcomes are needed to assess accuracy. |

Before the session, open the relevant tabs and verify that the chosen service
responds. Keep the local prediction service and saved results available as
fallbacks. Preparing and checking those demo surfaces is a later execution task,
not a completed preflight implied by this plan.

## Technical boundaries for slide design and narration

| Topic | Accurate project description |
| --- | --- |
| Prediction target | The learning project predicts US medical charges in USD. Its title does not make it a validated insurance-pricing system. |
| Notebook role | Notebooks support exploration and teaching. The Python training pipeline does not require executing them. |
| Dataset preparation | Source preparation sits upstream of model ingestion. The model pipeline starts from a prepared dataset. |
| Model registry | Basic registration creates named versions. The serving application loads the saved bundle; registry registration is not deployment selection. |
| Reproducibility | Preserve code, data, settings and environment. Logging a DVC pointer hash alone does not verify the bytes consumed by that run. |
| CI and CD | The workflows run independently. CD performs its own checks and restores DVC artifacts. |
| Model quality gate | The golden test evaluates the existing saved model; the deployment workflow does not retrain it. |
| Prediction | The demo API handles individual requests. A scheduled batch-scoring workflow is a conceptual alternative, not an implemented integration with Hive or SAS. |
| Drift | The saved reports are an offline demonstration, including simulated production data. They are not live production monitoring. |
| Accuracy after release | The simulated production data lacks actual charges, so its drift report cannot measure prediction error. |
| Retraining and response | There is no automatic retraining schedule, drift alert job or automated rollback loop. |

Use the same conceptual distinctions throughout:

- Training learns a model from historical examples.
- Prediction or scoring applies an existing model to new records.
- Registration records a named model version and its history.
- Deployment makes a selected model available for use.
- Monitoring reviews operational signals and model-related evidence over time.
- Retraining learns a new model, which still needs evaluation before replacement.

## Visual direction

Use the existing Canva presentation only as a visual reference. Its mixed MLOps
and older loan-project content is not a source of project claims.

Retain the white graph-paper background, yellow highlights, black
handwritten-style headings and simple drawings. Use readable body text and
consistent colours for lifecycle stages. Keep decorative elements away from
diagrams. Tool names should follow explanations of the problems they address.

The full repository architecture is useful as backup material. The main slides
need a simpler map that the audience can recognise from slide 4.

## Material to combine or leave for questions

- Keep feature stores, orchestration products and detailed maturity levels for
  optional questions.
- Combine batch versus API deployment into one visual.
- Omit individual slides for every tool, cloud setup instructions and long code
  listings.
- Omit detailed model comparisons, cleaning walkthroughs and SHAP analysis.
- Avoid unsupported numerical slogans about how much work model development
  represents.
- Keep ownership and review visible in the lifecycle instead of adding a broad
  compliance lecture or claims about bank-specific policy.

## References

- [MLOps Notes](https://app.notion.com/p/3d2721e1becc8023864bfe0cd2862cb9): main conceptual reference; select the material appropriate for this introductory session.
- [Existing Canva presentation](https://www.canva.com/d/KqcYYO-uei5ayXS): visual reference only.
- [Google's MLOps guidance](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning?hl=en): development, operations and lifecycle concepts.
- [Training and registration implementation](../main.py): pipeline execution, experiment tracking and model registration.
- [Prediction implementation](../steps/predict.py): serving bundle and prediction behaviour.
- [API implementation](../app.py): request validation and prediction endpoint.
- [CD workflow](../.github/workflows/cd.yml): deployment stages and checks.
- [Operations guide](operations.md): drift demonstration and manual work that remains.
- [Monitoring notebook](../notebooks/04_monitoring.ipynb): offline report generation and simulated production data.
