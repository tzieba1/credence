"""Upload a document, run an extraction against it, read extractions back.

The handlers are plain functions, not coroutines, so FastAPI runs each in a
worker thread: an extraction blocks its thread for a few seconds while the
event loop keeps answering. That is the whole concurrency story, and it is
enough for one process; the README says where a queue would go.
"""

import hashlib
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from credence import pdfio, prompts
from credence.api.deps import (
    MakeExtractorDep,
    SessionDep,
    SettingsDep,
    StoreDep,
    require_api_key,
)
from credence.api.schemas import (
    DocumentOut,
    ExtractionList,
    ExtractionOut,
    ExtractionRequest,
    UsageOut,
)
from credence.db import Document, Extraction
from credence.extraction import Extraction as ExtractionResult
from credence.extraction import ModelUnavailable
from credence.pricing import PRICES
from credence.schema import Certificate

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/documents", status_code=201, response_model=DocumentOut)
def upload_document(
    file: UploadFile,
    response: Response,
    settings: SettingsDep,
    session: SessionDep,
    store: StoreDep,
) -> Document:
    """Store a PDF. The same bytes uploaded twice are one document, answered with 200."""
    pdf = file.file.read(settings.max_document_bytes + 1)
    if len(pdf) > settings.max_document_bytes:
        raise HTTPException(413, f"document is larger than {settings.max_document_bytes} bytes")
    if not pdf.startswith(b"%PDF-"):
        raise HTTPException(415, "only PDF documents are accepted")
    try:
        pages = pdfio.page_count(pdf)
    except pdfio.NotAPdf:
        raise HTTPException(422, "the file could not be read as a PDF") from None
    if pages > settings.max_document_pages:
        raise HTTPException(
            422, f"document has {pages} pages; the limit is {settings.max_document_pages}"
        )

    sha256 = hashlib.sha256(pdf).hexdigest()
    existing = _document_by_sha(session, sha256)
    if existing is not None:
        response.status_code = 200
        return existing

    path = store.save(sha256, pdf)
    document = Document(
        sha256=sha256,
        filename=(file.filename or "document.pdf")[:255],
        bytes_size=len(pdf),
        page_count=pages,
        stored_path=str(path),
    )
    session.add(document)
    try:
        session.commit()
    except IntegrityError:
        # The same document arrived twice at once and the other request won the unique index.
        session.rollback()
        existing = _document_by_sha(session, sha256)
        assert existing is not None
        response.status_code = 200
        return existing
    log.info(
        "document %d stored: sha=%s bytes=%d pages=%d", document.id, sha256[:12], len(pdf), pages
    )
    return document


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, session: SessionDep) -> Document:
    return _document(session, document_id)


@router.post("/documents/{document_id}/extractions", status_code=201, response_model=ExtractionOut)
def run_extraction(
    document_id: int,
    body: ExtractionRequest | None,
    settings: SettingsDep,
    session: SessionDep,
    store: StoreDep,
    make_extractor: MakeExtractorDep,
) -> ExtractionOut:
    """Call the model on a stored document and keep the result, success or recorded failure.

    A model that refuses or runs out of tokens still produces a row, with `record`
    null and `failure` set. Only an API that cannot be reached is an error: 503.
    """
    document = _document(session, document_id)
    body = body or ExtractionRequest()
    model = body.model or settings.extraction_model
    prompt_version = body.prompt_version or settings.prompt_version
    if model not in PRICES:
        raise HTTPException(422, f"no price is known for model {model!r}")
    if prompt_version not in prompts.available():
        raise HTTPException(422, f"unknown prompt version {prompt_version!r}")

    pdf = store.read(document.stored_path)
    try:
        result = make_extractor(model, prompt_version).extract(pdf)
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    row = _row_from(result, document.id)
    session.add(row)
    session.commit()
    session.refresh(row)  # answer from the stored row, so POST and GET agree to the digit
    log.info(
        "extraction %d stored for document %d: model=%s prompt=%s failure=%s",
        row.id,
        document.id,
        row.model,
        row.prompt_version,
        row.failure,
    )
    return _out(row)


@router.get("/extractions/{extraction_id}", response_model=ExtractionOut)
def get_extraction(extraction_id: int, session: SessionDep) -> ExtractionOut:
    row = session.get(Extraction, extraction_id)
    if row is None:
        raise HTTPException(404, f"no extraction {extraction_id}")
    return _out(row)


@router.get("/extractions", response_model=ExtractionList)
def list_extractions(
    session: SessionDep,
    document_id: int | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExtractionList:
    """Newest first, with the filters the results table is built from."""
    query = select(Extraction)
    if document_id is not None:
        query = query.where(Extraction.document_id == document_id)
    if model is not None:
        query = query.where(Extraction.model == model)
    if prompt_version is not None:
        query = query.where(Extraction.prompt_version == prompt_version)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Extraction.created_at.desc(), Extraction.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ExtractionList(items=[_out(r) for r in rows], total=total, limit=limit, offset=offset)


def _document_by_sha(session: Session, sha256: str) -> Document | None:
    return session.scalar(select(Document).where(Document.sha256 == sha256))


def _document(session: Session, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(404, f"no document {document_id}")
    return document


def _row_from(result: ExtractionResult, document_id: int) -> Extraction:
    fields: dict[str, Any] | None = None
    notes: str | None = None
    if result.record is not None:
        fields = result.record.model_dump(mode="json", exclude={"notes"})
        notes = result.record.notes
    return Extraction(
        document_id=document_id,
        model=result.model,
        prompt_version=result.prompt_version,
        implementation=result.implementation,
        fields=fields,
        raw_notes=notes,
        failure=result.failure,
        stop_reason=result.stop_reason,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cache_read_input_tokens=result.usage.cache_read_input_tokens,
        cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        request_id=result.request_id,
    )


def _out(row: Extraction) -> ExtractionOut:
    record = Certificate(**row.fields, notes=row.raw_notes) if row.fields is not None else None
    return ExtractionOut(
        id=row.id,
        document_id=row.document_id,
        model=row.model,
        prompt_version=row.prompt_version,
        implementation=row.implementation,
        record=record,
        failure=row.failure,
        stop_reason=row.stop_reason,
        usage=UsageOut(
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cache_read_input_tokens=row.cache_read_input_tokens,
            cache_creation_input_tokens=row.cache_creation_input_tokens,
        ),
        cost_usd=row.cost_usd,
        latency_ms=row.latency_ms,
        request_id=row.request_id,
        created_at=row.created_at,
    )
