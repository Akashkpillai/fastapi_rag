import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db.repository import count_chunks, delete_document, get_document, list_documents, save_document
from app.db.session import get_session
from app.schemas.document import DocumentInfo, UploadSummary
from app.services.chunker import chunk_pages
from app.services.embeddings import embed_texts
from app.services.pdf_parser import InvalidPDFError, parse_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document", tags=["documents"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

@router.get("/{document_id}", response_model=DocumentInfo)
def one_document(document_id: str, session: Annotated[Session, Depends(get_session)]):
    document = get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentInfo(
        document_id=document.id,
        filename=document.filename,
        page_count=document.page_count,
        chunk_count=count_chunks(session, document_id),
    )

@router.get("/", response_model=list[DocumentInfo])
def all_documents(session: Annotated[Session, Depends(get_session)]):
    return [
        DocumentInfo(
            document_id=document.id,
            filename=document.filename,
            page_count=document.page_count,
            chunk_count=chunk_count,
        )
        for document, chunk_count in list_documents(session)
    ]


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: str, session: Annotated[Session, Depends(get_session)]):
    document = get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document(session, document)

@router.post("/upload", response_model=UploadSummary, status_code=201)
async def upload(file: UploadFile, session: Annotated[Session, Depends(get_session)]):
    # Check 1: what the client *says* the file is (easy to fake)
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    data = await file.read()

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 20 MB")

    # Check 2: what the file actually *is*: real PDFs start with "%PDF-"
    if b"%PDF-" not in data[:1024]:
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    document_id = uuid.uuid4().hex

    # Check 3: can it really be opened? (done inside parse_pdf)
    try:
        pages = await run_in_threadpool(parse_pdf, data, document_id)
    except InvalidPDFError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    usable_pages = [page for page in pages if page.text]
    empty_pages = [page.page_number for page in pages if not page.text]

    if not usable_pages:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found. This PDF appears to be scanned or "
                "image-only, so it needs OCR before it can be used.",
        )

    filename = file.filename or "unnamed.pdf"
    chunks = chunk_pages(document_id, usable_pages)
    embeddings = await run_in_threadpool(embed_texts, [chunk.text for chunk in chunks])
    save_document(session, document_id, filename, len(pages), chunks, embeddings)

    # Report what the database actually holds, not what we meant to save
    stored = count_chunks(session, document_id)
    if stored != len(chunks):
        logger.error("Document %s: created %d chunks but stored %d", document_id, len(chunks), stored)
        raise HTTPException(status_code=500, detail="The document was not fully saved")

    return UploadSummary(
        document_id=document_id,
        filename=filename,
        page_count=len(pages),
        pages_with_text=len(usable_pages),
        empty_pages=empty_pages,
        chunk_count=stored,
    )
