# credence

Credence measures how far you can trust a model's extraction of typed fields from a document. The name is the point: credence is the degree of belief you are entitled to have in a claim, and this project earns it for a model's output by measuring it against a labelled set.

**Status:** the evaluation set exists; the extraction does not yet. The log at the end says what exists.

## What it does

The service takes a PDF, asks a Claude model for a typed record of its fields using structured output, and stores the record with the model, prompt version, token usage, cost and latency. An evaluation set of labelled documents, run by pytest, reports per-field accuracy and fails when it drops below a threshold. The first document type is certificates: issuer, holder, certificate number, issue date, expiry date, scope and signatory.

## Why this project

To learn to ship a model-backed feature with evidence behind it: a schema chosen on purpose, a set labelled by hand, a test that says what the model gets wrong and a cost per document that was measured rather than guessed. It is not a machine-learning project. Nothing is trained or fine-tuned.

## Design

To be written at checkpoint 2, when the extraction call exists.

## Results

To be written at checkpoint 3, when the evaluation runner exists.

## What went wrong and what changed

To be written as the evaluation produces failures.

## How the eval works

To be written at checkpoint 3, when the runner exists. The set it will run on is already here: eighteen documents under `eval/cases/`, each with a `gold.json` beside it, described case by case in [eval/README.md](eval/README.md). Sixteen are certificates generated from specifications so the labels are known by construction, five of those rendered as image-only scans, and two are documents that are not certificates at all.

## Running it locally

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Those are the four checks CI runs on every push.

To regenerate the evaluation documents from their specifications:

```sh
uv run python -m credence.synth
```

## Not done, and why

- **A front end.** The API and a CLI are enough. The point is the backend and the measurement behind it.
- **Authentication beyond a single API key for the service.** Anything more would be scaffolding around a feature that is not the subject.
- **Training or fine-tuning.** The project measures a hosted model's output. It does not change the model.
- **Documents from any employer.** The evaluation set is synthetic plus public documents only. Nothing in this repository comes from a workplace.

## Log

- 2026-11-03, checkpoint 1: the document generator and eighteen labelled cases under `eval/cases/`, with tests that hold the committed files to their specifications.
- 2026-11-03, checkpoint 0: repository skeleton. uv, ruff, mypy strict, pytest and a GitHub Actions workflow that runs them on one smoke test.
