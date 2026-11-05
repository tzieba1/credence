# Practice log

Who wrote each instance of each pattern, and one line of review feedback per practice step. The rule is in [WORKING.md](WORKING.md): the assistant writes the first instance of a pattern, the developer writes the second by hand from a short spec, and from the third on it is the developer's choice each time.

Checkpoints 0 to 4 were built before this protocol existed, so every first instance below is the assistant's. The second instances start with checkpoint 5.

| pattern | first instance | second instance | third and later |
|---|---|---|---|
| Prompt version | `src/credence/prompts/v1.md`, assistant | | |
| Pydantic schema | `Certificate` in `src/credence/schema.py`, assistant | | |
| API request or response model | `DocumentOut` in `src/credence/api/schemas.py`, assistant | | |
| HTTP endpoint | `upload_document` in `src/credence/api/routes.py`, assistant | | |
| API test | `test_upload_stores_the_document_and_its_metadata` in `tests/test_api.py`, assistant | | |
| SQLAlchemy model | `Document` in `src/credence/db/models.py`, assistant | | |
| Alembic migration | `migrations/versions/0001_documents_and_extractions.py`, assistant | | |
| Generator case | the first `CaseSpec` in `src/credence/synth/cases.py`, assistant | | |
| Evaluation metric | `FieldMetrics` and `summarise` in `src/credence/evaluation/metrics.py`, assistant | | |
| Settings field | `extraction_model` in `src/credence/config.py`, assistant | | |
| CLI subcommand | `extract` in `src/credence/cli.py`, assistant | | |

## Review notes

One line per practice step, newest first. What was right, what was wrong, what was merely different.

*None yet.*
