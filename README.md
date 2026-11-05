# credence

Credence measures how far you can trust a model's extraction of typed fields from a document. The name is the point: credence is the degree of belief you are entitled to have in a claim, and this project earns it for a model's output by measuring it against a labelled set.

**Status:** the HTTP API, Postgres storage and the evaluation runner are built and tested, and the first live run of both models is recorded below. The log at the end says what exists.

## What it does

The service takes a PDF, asks a Claude model for a typed record of its fields using structured output, and stores the record with the model, prompt version, token usage, cost and latency. An evaluation set of labelled documents, run by pytest, reports per-field accuracy and fails when it drops below a threshold. The first document type is certificates: issuer, holder, certificate number, issue date, expiry date, scope and signatory.

## Why this project

To learn to ship a model-backed feature with evidence behind it: a schema chosen on purpose, a set labelled by hand, a test that says what the model gets wrong and a cost per document that was measured rather than guessed. It is not a machine-learning project. Nothing is trained or fine-tuned.

## Design

```
CLI / HTTP  ->  FastAPI  ->  extraction service  ->  Claude API
                   |              |
                Postgres      eval runner (pytest)
```

One process. An extraction takes seconds, so the API runs it inline; there is no queue and no worker. The handlers are ordinary functions, so FastAPI runs each one in a worker thread and a call to the model blocks that thread, not the event loop. If the service ever had to absorb bursts, a queue would sit between the API and the extraction service, with the extraction row created first in a `pending` state. It is not there because nothing in the project needs it yet, and a queue that nothing needs is a liability to explain, not an asset.

The LangGraph variant is not built yet.

### The API

| method and path | what it does |
|---|---|
| `POST /documents` | Upload a PDF. Rejects anything that is not a PDF, is larger than the configured size, or has more pages than the limit. The same bytes uploaded twice are one document: the second upload answers 200 with the existing row. |
| `GET /documents/{id}` | The document's hash, name, size, page count and upload time. |
| `POST /documents/{id}/extractions` | Run the model on the document, with an optional `model` and `prompt_version` in the body, and store the result. A refusal or a truncated output is still a stored row, with `record` null and `failure` set. Only an API that cannot be reached is an error, 503 with the reason. |
| `GET /extractions/{id}` | One extraction, as stored. |
| `GET /extractions` | Newest first, filterable by `document_id`, `model` and `prompt_version`, paged with `limit` and `offset`. |
| `GET /health` | Whether Postgres answers and whether a model API key is configured. 503 and `degraded` if either is missing. |

Everything but `/health` requires the service's single API key in `X-API-Key` when `CREDENCE_API_KEY` is set. Unset, the service is open, which is only acceptable on a laptop. The OpenAPI document is at `/docs`.

### The data model

Two tables, created by a hand-written Alembic migration that a test compares against the SQLAlchemy models so the two cannot drift.

`documents` holds the file's sha256 (unique), filename, size, page count, upload time and the path where the bytes are stored. The PDF itself goes on disk under `data/documents/`, named by its hash, never into the database.

`extractions` is one call against one document: the model the API reported, the prompt version, the implementation, the validated fields as JSONB with the free-text `notes` in its own column, the failure reason and stop reason, input, output and cache tokens, cost in USD to six decimals, latency, the request id and the time. A row is kept whether or not there is a record, because a refusal that cost money is part of the measurement.

### The call

The PDF goes to the model as a base64 document block, ahead of a one-line instruction. The system prompt is a file in the repository, `src/credence/prompts/v1.md`, and its version string is recorded on every extraction. The SDK's `messages.parse` sends the JSON schema of the `Certificate` Pydantic model as the required output format and validates the reply against it, so the service never parses JSON by hand. Every field of the schema is required and nullable, which forces the model to say null rather than leave a key out.

Thinking is on, as it always is on Opus 5.5, at the default `medium` effort. The request timeout is two minutes and the SDK retries rate limits and server errors twice before the service gives up.

### What is recorded

For every call: the model the API reports it used, the prompt version, the implementation (`direct` now, `langgraph` later), input and output tokens, cache tokens, cost in USD from a price table in `src/credence/pricing.py`, latency, the stop reason, the request id, and the model's raw text output for the evaluation fixtures.

| model | input | output | cache read | cache write |
|---|---|---|---|---|
| claude-opus-5-5 | $4.00 | $20.00 | $0.20 | $5.00 |
| claude-haiku-5-5 | $0.10 | $0.50 | $0.01 | $0.125 |

USD per million tokens, Claude API list prices as of November 2026.

### Failure handling

The stop reason is checked before the record is trusted. `end_turn` with a parsed record is a success. Everything else is a recorded failure with its usage and cost still attached: a `refusal` (with the category the API gives), `max_tokens` even when the truncated output happened to be valid JSON, or any stop reason this code does not know. One path loses the usage: when the output is cut off mid-JSON, the SDK's validation fails before the response is visible, and the extraction is recorded as `invalid_output` with no tokens. The 16,000-token output ceiling makes that path unlikely for an eight-field record, and the evaluation will show whether it ever happens.

The service does not use the API's server-side fallback, which would re-run a refused request on another model inside the same call. The point of this project is to measure one model's output, and a row that says `claude-opus-5-5` must have come from that model.

If the API cannot be reached, times out, keeps rate limiting, or answers with a server error, the service raises one exception, `ModelUnavailable`, which the HTTP layer turns into a 503 with a reason. A missing `ANTHROPIC_API_KEY` is reported the same way, instead of as the SDK's error on the first request. A 4xx other than 429 is a bug in this code and is allowed to surface.

Logs carry the document's hash prefix, sizes, timings, stop reasons and cost. They never carry the document's content or the model's output; a test asserts that.

## Results

Per-field accuracy is exact match after normalisation (Unicode composed, whitespace collapsed, case ignored; dates compared as ISO strings). Document accuracy is all seven fields right. Cost is from the usage the API reported, priced from the table above. Latency is the median wall-clock time of the call.

| model | prompt | impl | issuer | holder | number | issue | expiry | scope | signatory | doc | $/doc | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | v1 | direct | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.83 | 0.94 | 0.78 | 0.0183 | 3578 |
| claude-haiku-5-5 | v1 | direct | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.89 | 0.94 | 0.83 | 0.0005 | 2202 |

Each row comes from a file under `eval/results/`, which also holds, per run, the null-handling precision and recall per field and every wrong case with what was predicted and what the gold says. Both runs were recorded on 2026-11-05 over eighteen cases; the Opus run cost 33 cents in total and the Haiku run under a cent. The floors in `eval/thresholds.json` sit just under these numbers, so a later run that does worse fails the eval.

## What went wrong and what changed

To be written as the evaluation produces failures.

## How the eval works

The set is eighteen documents under `eval/cases/`, each with a `gold.json` beside it, described case by case in [eval/README.md](eval/README.md). Sixteen are certificates generated from specifications so the labels are known by construction, five of those rendered as image-only scans, and two are documents that are not certificates at all.

`pytest -m eval` runs it, in one of two modes.

**Recorded**, the default and what CI runs on every push. For each model that has fixtures under `eval/fixtures/<prompt version>/<model>/`, the saved API response for every case is fed back through the real SDK client by way of a fake HTTP transport, so the request is built, the schema is sent, the reply is validated and the record is scored by exactly the code that runs live. Only the network is replaced. This is free and deterministic, and it still catches a change to the schema, the parsing, the normalisation or the price table. The test fails if any field's accuracy, or the document accuracy, falls below the floor in `eval/thresholds.json` for that model. With nothing recorded it skips rather than passes.

**Live**, run by hand when the prompt or the model changes:

```sh
uv run pytest -m eval --live --model claude-opus-5-5 --prompt v1
```

That calls the API once per case, overwrites the fixtures for that prompt and model, writes `eval/results/<timestamp>-<model>-<prompt>-<implementation>.json` and a Markdown summary beside it, and prints the summary. A full run on Opus 5.5 is expected to cost about a dollar. `uv run credence report` prints the same summary from the fixtures without calling anything.

The split matters because a model's output is not deterministic and every live call costs money. CI should answer "did my code change break the measurement" for free, and only a person decides to spend on "did the model's behaviour change".

## Running it locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and, for the API and its tests, Docker for Postgres. To call the model, put an API key in the environment:

```sh
export ANTHROPIC_API_KEY=...
uv run credence extract eval/cases/g01-classic-en-iso/document.pdf
uv run credence extract eval/cases/g12-scan-table-es/document.pdf --model claude-haiku-5-5 --json
```

Every `credence extract` is a live call and costs money, about five cents on Opus 5.5 for a one-page certificate before measurement says otherwise. Settings such as the default model, prompt version and effort are read from `CREDENCE_*` environment variables or a `.env` file; `.env.example` lists them.

To run the service:

```sh
docker compose up -d          # Postgres on localhost:5432, matching the default CREDENCE_DATABASE_URL
uv run alembic upgrade head   # create the tables
uv run credence serve         # http://127.0.0.1:8000, OpenAPI at /docs
```

Then, from another shell:

```sh
curl -F file=@eval/cases/g01-classic-en-iso/document.pdf localhost:8000/documents
curl -X POST -H 'content-type: application/json' -d '{}' localhost:8000/documents/1/extractions
curl 'localhost:8000/extractions?document_id=1'
```

The checks CI runs on every push:

```sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

The API and migration tests need Postgres. They use a `credence_test` database on the Compose instance, creating it if needed, and skip with a message when it is not running. CI runs them against a Postgres service and sets `CREDENCE_TEST_DATABASE_URL` explicitly, which turns that skip into a failure, so a missing database cannot make CI green by accident.

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

- 2026-11-04, checkpoint 4: the HTTP API with upload, extraction, read-back and listing; `documents` and `extractions` in Postgres through SQLAlchemy, with an Alembic migration tested against the models; Docker Compose for Postgres; `credence serve`. The API tests run the real extractor over a fake transport against a real database, in CI as well.
- 2026-11-03, checkpoint 3: the evaluation runner with per-field accuracy, null precision and recall, cost and latency; recorded fixtures replayed through the real SDK client; `pytest -m eval` in CI with `--live` by hand; results files and the table above. First live run pending.
- 2026-11-03, checkpoint 2: the `Certificate` schema, the extraction service around `messages.parse` with cost, latency and stop-reason bookkeeping, and `credence extract`. Tests drive the real SDK against a fake API.
- 2026-11-03, checkpoint 1: the document generator and eighteen labelled cases under `eval/cases/`, with tests that hold the committed files to their specifications.
- 2026-11-03, checkpoint 0: repository skeleton. uv, ruff, mypy strict, pytest and a GitHub Actions workflow that runs them on one smoke test.
